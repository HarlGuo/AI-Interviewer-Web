from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict

from ..llm.deepseek import chat_with_tools, model_call_budget
from ..prompts.interview import INTERVIEW_AGENT_SYSTEM_PROMPT
from ..schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewReport, InterviewStartResponse, InterviewTurnRequest, InterviewTurnResponse, ReportRequest
from ..skills import interview as interview_specialists
from ..skills.runtime import AgentToolCall, ActivateSkillArguments, RUNTIME_SKILLS, RUNTIME_TOOLS, RuntimeSkill, activation_tool_manifest
from ..tools import interview as _interview_tools  # noqa: F401 - registers code tools

logger = logging.getLogger(__name__)

MAX_AGENT_STEPS = 14
MAX_TOTAL_MODEL_CALLS = 16
# Backward-compatible name for existing imports; it now means main-agent planning steps.
MAX_AGENT_TURNS = MAX_AGENT_STEPS
DELEGATE_EVALUATOR = "delegate_answer_evaluator"
DELEGATE_GENERATOR = "delegate_question_generator"


class AgentFinalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ready"]
    reason: str


@dataclass
class InterviewRunContext:
    phase: Literal["start", "turn"]
    request: InterviewAgentStartRequest | InterviewTurnRequest
    plan: list[str]
    latest_answer: str = ""
    decision: interview_specialists.AnswerDecision | None = None
    question: InterviewQuestion | None = None
    active_skill: RuntimeSkill | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    pending_call: AgentToolCall | None = None
    route: Literal["agent", "tool", "evaluator", "generator", "finish"] = "agent"
    agent_steps: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    final_output_corrections: int = 0
    confirmed_resume: list[dict[str, str]] | None = None
    job_context: dict[str, Any] | None = None
    interview_history: list[Any] | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    user_id: str | None = None
    report_request: ReportRequest | None = None
    report: InterviewReport | None = None
    completed_interview_loaded: bool = False
    delivery_metrics_loaded: bool = False
    report_save_attempted: bool = False
    report_persisted: bool = False
    report_correction_count: int = 0

    @property
    def next_main_index(self) -> int:
        if self.phase == "start":
            return 0
        assert isinstance(self.request, InterviewTurnRequest)
        return self.request.current_question.main_question_index + 1

    @property
    def completed(self) -> bool:
        return self.phase == "turn" and self.decision is not None and self.decision.action == "next_main" and self.next_main_index >= len(self.plan)


class InterviewGraphState(TypedDict):
    context: InterviewRunContext


def _delegation_manifest(name: str, description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    }


def _assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"role": "assistant", "content": message.get("content")}
    if message.get("tool_calls"):
        normalized["tool_calls"] = message["tool_calls"]
    return normalized


def _parse_tool_call(message: dict[str, Any]) -> AgentToolCall | None:
    raw_calls = message.get("tool_calls") or []
    if not raw_calls:
        return None
    if len(raw_calls) != 1:
        raise ValueError("面试 Agent 每一步只能调用一个能力，以便读取结果后重新规划")
    raw = raw_calls[0]
    function = raw.get("function") if isinstance(raw, dict) else None
    if not isinstance(function, dict):
        raise ValueError("Agent 返回了格式错误的调用")
    call = AgentToolCall(id=str(raw.get("id") or ""), name=str(function.get("name") or ""), arguments_json=str(function.get("arguments") or "{}"))
    if not call.id or not call.name:
        raise ValueError("Agent 返回了缺少标识或名称的调用")
    return call


def _initial_messages(context: InterviewRunContext) -> list[dict[str, Any]]:
    request = context.request
    task = {
        "event": "interview_started" if context.phase == "start" else "answer_submitted",
        "goal": "生成第一道主问题" if context.phase == "start" else "分析最新回答；若最后一道主问题完成，继续生成并保存证据型报告",
        "stage": context.plan[0] if context.phase == "start" else request.current_question.stage,
        "main_question_index": 0 if context.phase == "start" else request.current_question.main_question_index,
        "follow_up_count": 0 if context.phase == "start" else request.current_question.follow_up_count,
        "remaining_main_questions": len(context.plan) if context.phase == "start" else len(context.plan) - request.current_question.main_question_index - 1,
    }
    return [
        {"role": "system", "content": INTERVIEW_AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": "Skill目录与可信任务状态：\n" + json.dumps({"skills": RUNTIME_SKILLS.catalog(), "task": task}, ensure_ascii=False)},
    ]


def _available_capabilities(context: InterviewRunContext) -> list[dict[str, Any]]:
    if context.active_skill is None:
        return [activation_tool_manifest(RUNTIME_SKILLS)]
    manifests = RUNTIME_TOOLS.catalog(context.active_skill.tool_names)
    if context.active_skill.name == "conduct_resume_interviews":
        manifests.extend([
            _delegation_manifest(DELEGATE_EVALUATOR, "委派回答分析子Agent；仅在answer_submitted且上下文已加载后使用。"),
            _delegation_manifest(DELEGATE_GENERATOR, "委派问题生成子Agent；仅在开始面试或回答分析决定进入下一主问题后使用。"),
        ])
        if context.completed:
            manifests.append(activation_tool_manifest(RUNTIME_SKILLS))
    return manifests


def _ready_to_finish(context: InterviewRunContext) -> bool:
    if context.phase == "start":
        return context.question is not None
    if context.decision is None:
        return False
    if context.completed:
        return context.report is not None and context.report_save_attempted
    return context.decision.action == "follow_up" or context.question is not None


async def _main_agent_node(state: InterviewGraphState) -> dict[str, InterviewRunContext]:
    context = state["context"]
    if context.agent_steps >= MAX_AGENT_STEPS:
        raise RuntimeError(f"Agent 超过最多 {MAX_AGENT_STEPS} 个规划步骤仍未完成本轮任务")
    context.agent_steps += 1
    report_mode = context.active_skill is not None and context.active_skill.name == "generate_evidence_report"
    message = await chat_with_tools(
        messages=list(context.messages), tools=_available_capabilities(context),
        max_tokens=5000 if report_mode else 1200,
        purpose="report_generation" if report_mode else "agent_loop",
    )
    context.messages.append(_assistant_message(message))
    call = _parse_tool_call(message)
    context.pending_call = call
    context.trace.append({"node": "main_agent", "step": context.agent_steps, "action": call.name if call else "finish"})
    if call is not None:
        if context.active_skill is None:
            context.route = "tool"
        elif call.name == DELEGATE_EVALUATOR:
            context.route = "evaluator"
        elif call.name == DELEGATE_GENERATOR:
            context.route = "generator"
        else:
            context.route = "tool"
        return {"context": context}

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Agent 未返回能力调用或最终结果")
    if not _ready_to_finish(context):
        reminder = "当前结果不足以结束本轮，请继续加载必要上下文或委派专业子Agent。"
        if context.completed:
            reminder = "面试已完成但报告尚未通过校验并保存。必须激活generate_evidence_report Skill，执行其Tools后才能结束。"
        context.messages.append({"role": "user", "content": reminder})
        context.route = "agent"
        return {"context": context}
    try:
        AgentFinalOutput.model_validate_json(content)
    except ValueError as error:
        if context.final_output_corrections >= 1:
            raise ValueError("Agent 最终输出在一次纠正后仍不符合协议") from error
        context.final_output_corrections += 1
        context.messages.append({"role": "user", "content": '只返回纯JSON：{"status":"ready","reason":"为何可以结束本轮"}。'})
        context.route = "agent"
        return {"context": context}
    context.route = "finish"
    return {"context": context}


async def _tool_node(state: InterviewGraphState) -> dict[str, InterviewRunContext]:
    context = state["context"]
    call = context.pending_call
    if call is None:
        raise RuntimeError("Tool节点缺少调用")
    context.tool_calls += 1
    if call.name == "activate_skill":
        if context.active_skill is not None and not context.completed:
            raise ValueError("只能在当前面试Skill完成后切换Skill")
        if context.active_skill is not None and context.active_skill.name == "generate_evidence_report":
            raise ValueError("报告Skill已激活，不能重复激活")
        arguments = ActivateSkillArguments.model_validate_json(call.arguments_json or "{}")
        if context.active_skill is not None and arguments.skill_name != "generate_evidence_report":
            raise ValueError("面试完成后只能切换到generate_evidence_report Skill")
        event = "interview_completed" if context.completed else ("interview_started" if context.phase == "start" else "answer_submitted")
        context.active_skill = RUNTIME_SKILLS.activate(arguments.skill_name, event=event)
        result: Any = context.active_skill.activation_result()
    elif context.active_skill is None:
        if call.name != "activate_skill":
            raise ValueError("必须先调用 activate_skill 加载产品 Skill")
    else:
        try:
            result = await RUNTIME_TOOLS.execute(call, context, allowed_tools=context.active_skill.tool_names)
        except ValueError as error:
            if call.name != "submit_report_assessment" or context.report_correction_count >= 1:
                raise
            context.report_correction_count += 1
            result = {
                "status": "validation_failed",
                "errors": [str(error)],
                "correction_remaining": 0,
                "instruction": "只纠正上述错误并重新调用submit_report_assessment。",
            }
    context.messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)})
    context.trace.append({"node": "code_tool", "name": call.name})
    context.pending_call = None
    context.route = "agent"
    return {"context": context}


def _require_loaded_context(context: InterviewRunContext) -> None:
    if context.confirmed_resume is None or context.job_context is None or context.interview_history is None:
        raise ValueError("委派专业子Agent前必须加载简历、岗位能力和面试历史")


async def _evaluator_subagent_node(state: InterviewGraphState) -> dict[str, InterviewRunContext]:
    context = state["context"]
    call = context.pending_call
    if call is None or call.name != DELEGATE_EVALUATOR:
        raise RuntimeError("回答分析子Agent缺少正确委派")
    _require_loaded_context(context)
    if context.phase != "turn" or not isinstance(context.request, InterviewTurnRequest):
        raise ValueError("开始面试时不能委派回答分析")
    if context.decision is not None:
        raise ValueError("本轮回答已经分析，不能重复委派")
    context.decision = await interview_specialists.evaluate_answer(context.request, context.latest_answer)
    context.messages.append({"role": "tool", "tool_call_id": call.id, "content": context.decision.model_dump_json()})
    context.trace.append({"node": "evaluator_subagent", "decision": context.decision.action})
    context.pending_call = None
    context.route = "agent"
    return {"context": context}


async def _generator_subagent_node(state: InterviewGraphState) -> dict[str, InterviewRunContext]:
    context = state["context"]
    call = context.pending_call
    if call is None or call.name != DELEGATE_GENERATOR:
        raise RuntimeError("问题生成子Agent缺少正确委派")
    _require_loaded_context(context)
    if context.question is not None:
        raise ValueError("本轮已经生成问题，不能重复委派")
    if context.phase == "turn" and context.decision is None:
        raise ValueError("必须先分析最新回答")
    if context.phase == "turn" and (context.decision.action == "follow_up" or context.completed):
        raise ValueError("当前回答决策不允许生成新的主问题")
    index = context.next_main_index
    context.question = await interview_specialists.generate_main_question(
        context.request, context.plan[index], index, context.interview_history,
    )
    context.messages.append({"role": "tool", "tool_call_id": call.id, "content": context.question.model_dump_json()})
    context.trace.append({"node": "generator_subagent", "main_question_index": index})
    context.pending_call = None
    context.route = "agent"
    return {"context": context}


def _route(state: InterviewGraphState) -> Literal["agent", "tool", "evaluator", "generator", "finish"]:
    return state["context"].route


def _compile_interview_agent_graph():
    graph = StateGraph(InterviewGraphState)
    graph.add_node("main_agent", _main_agent_node)
    graph.add_node("code_tool", _tool_node)
    graph.add_node("evaluator_subagent", _evaluator_subagent_node)
    graph.add_node("generator_subagent", _generator_subagent_node)
    graph.add_edge(START, "main_agent")
    graph.add_conditional_edges("main_agent", _route, {
        "agent": "main_agent", "tool": "code_tool", "evaluator": "evaluator_subagent",
        "generator": "generator_subagent", "finish": END,
    })
    graph.add_edge("code_tool", "main_agent")
    graph.add_edge("evaluator_subagent", "main_agent")
    graph.add_edge("generator_subagent", "main_agent")
    return graph.compile()


INTERVIEW_AGENT_GRAPH = _compile_interview_agent_graph()


async def _run_graph(context: InterviewRunContext) -> InterviewRunContext:
    context.messages = _initial_messages(context)
    with model_call_budget(MAX_TOTAL_MODEL_CALLS) as budget:
        state = await INTERVIEW_AGENT_GRAPH.ainvoke({"context": context}, config={"recursion_limit": 32})
        state["context"].model_calls = budget.used
    return state["context"]


def _turn_response(context: InterviewRunContext) -> InterviewTurnResponse:
    assert isinstance(context.request, InterviewTurnRequest)
    assert context.decision is not None
    decision = context.decision
    if decision.action == "follow_up":
        if not decision.question.strip():
            raise ValueError("追问决策缺少问题")
        current = context.request.current_question
        question = InterviewQuestion(
            id=str(uuid4()), stage=interview_specialists.STAGE_LABELS[context.plan[current.main_question_index]],
            text=decision.question.strip(), is_follow_up=True, main_question_index=current.main_question_index,
            follow_up_count=current.follow_up_count + 1, resume_evidence="",
        )
        return InterviewTurnResponse(next_question=question, completed=False, decision_reason=decision.reason, weakness=decision.weakness, total_main_questions=len(context.plan))
    return InterviewTurnResponse(
        next_question=None if context.completed else context.question,
        completed=context.completed,
        decision_reason=decision.reason,
        weakness=decision.weakness,
        total_main_questions=len(context.plan),
        report=context.report if context.completed else None,
    )


async def start_interview(request: InterviewAgentStartRequest, *, interview_id: str | None = None) -> InterviewStartResponse:
    context = await _run_graph(InterviewRunContext(phase="start", request=request, plan=interview_specialists.stage_plan(request.mode, request.focus)))
    if context.question is None:
        raise RuntimeError("Agent 完成运行但没有生成第一道问题")
    return InterviewStartResponse(interview_id=interview_id or str(uuid4()), question=context.question, total_main_questions=len(context.plan))


async def advance_interview(request: InterviewTurnRequest, *, user_id: str | None = None) -> InterviewTurnResponse:
    plan = interview_specialists.stage_plan(request.mode, request.focus)
    latest_answer = interview_specialists.validate_turn(request, plan)
    context = await _run_graph(InterviewRunContext(
        phase="turn", request=request, plan=plan, latest_answer=latest_answer, user_id=user_id,
    ))
    return _turn_response(context)
