from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any, Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from langgraph.graph import END, START, StateGraph

from ..llm.deepseek import chat_with_tools
from ..prompts.interview import INTERVIEW_AGENT_SYSTEM_PROMPT
from ..schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewStartResponse, InterviewTurnRequest, InterviewTurnResponse
from ..skills import interview as interview_skills
from ..skills.runtime import AgentToolCall, RUNTIME_SKILLS, RUNTIME_TOOLS, RuntimeSkill, ActivateSkillArguments, activation_tool_manifest

logger = logging.getLogger(__name__)

MAX_AGENT_TURNS = 6


class InterviewLoopState(TypedDict):
    context: InterviewRunContext


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
    decision: interview_skills.AnswerDecision | None = None
    question: InterviewQuestion | None = None
    skill_events: list[dict[str, Any]] = field(default_factory=list)
    active_skill: RuntimeSkill | None = None

    @property
    def next_main_index(self) -> int:
        if self.phase == "start":
            return 0
        assert isinstance(self.request, InterviewTurnRequest)
        return self.request.current_question.main_question_index + 1

    @property
    def completed(self) -> bool:
        return self.phase == "turn" and self.decision is not None and self.decision.action == "next_main" and self.next_main_index >= len(self.plan)


def _serialize_tool_result(result: Any) -> str:
    if isinstance(result, BaseModel):
        return result.model_dump_json()
    return json.dumps(result, ensure_ascii=False)


def _assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"role": "assistant", "content": message.get("content")}
    tool_calls = message.get("tool_calls")
    if tool_calls:
        normalized["tool_calls"] = tool_calls
    return normalized


def _parse_tool_calls(message: dict[str, Any]) -> list[AgentToolCall]:
    parsed: list[AgentToolCall] = []
    for raw in message.get("tool_calls") or []:
        function = raw.get("function") if isinstance(raw, dict) else None
        if not isinstance(function, dict):
            raise ValueError("Agent 返回了格式错误的工具调用")
        parsed.append(AgentToolCall(
            id=str(raw.get("id") or ""),
            name=str(function.get("name") or ""),
            arguments_json=str(function.get("arguments") or "{}"),
        ))
    if any(not call.id or not call.name for call in parsed):
        raise ValueError("Agent 返回了缺少标识或名称的工具调用")
    return parsed


def _initial_messages(context: InterviewRunContext) -> list[dict[str, Any]]:
    request = context.request
    if context.phase == "start":
        task = {
            "event": "interview_started",
            "goal": "生成第一道主问题，然后结束本轮",
            "stage": context.plan[0],
            "main_question_index": 0,
            "has_confirmed_resume": request.resume_review_status == "ai_verified",
        }
    else:
        assert isinstance(request, InterviewTurnRequest)
        task = {
            "event": "answer_submitted",
            "goal": "分析最新回答；自主决定追问、生成下一道主问题或完成面试",
            "current_stage": request.current_question.stage,
            "main_question_index": request.current_question.main_question_index,
            "follow_up_count": request.current_question.follow_up_count,
            "remaining_main_questions": len(context.plan) - request.current_question.main_question_index - 1,
            "has_latest_answer": True,
        }
    return [
        {"role": "system", "content": INTERVIEW_AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": "产品运行时 Skill 目录与本轮可信状态摘要：\n" + json.dumps({"skills": RUNTIME_SKILLS.catalog(), "task": task}, ensure_ascii=False)},
    ]


def _validate_tool_sequence(context: InterviewRunContext, call: AgentToolCall) -> None:
    if call.name == "evaluate_interview_answer":
        if context.phase != "turn":
            raise ValueError("开始面试时不能分析回答")
        if context.decision is not None:
            raise ValueError("本轮回答已经分析，不能重复分析")
        return
    if call.name == "generate_interview_question":
        if context.question is not None:
            raise ValueError("本轮已经生成问题，不能重复生成")
        if context.phase == "turn" and context.decision is None:
            raise ValueError("必须先分析最新回答，再决定是否生成下一道主问题")
        if context.phase == "turn" and (context.decision.action == "follow_up" or context.completed):
            raise ValueError("当前回答决策不允许生成新的主问题")
        return
    raise ValueError(f"动态面试 Skill 不允许调用 Tool：{call.name}")


async def _execute_tool(context: InterviewRunContext, call: AgentToolCall) -> Any:
    _validate_tool_sequence(context, call)
    if call.name == "evaluate_interview_answer":
        result = await RUNTIME_TOOLS.execute(call, {"request": context.request, "latest_answer": context.latest_answer}, allowed_tools=context.active_skill.tool_names)
        if not isinstance(result, interview_skills.AnswerDecision):
            raise ValueError("回答分析 Skill 返回了错误类型")
        context.decision = result
    else:
        index = context.next_main_index
        result = await RUNTIME_TOOLS.execute(call, {
            "request": context.request,
            "stage": context.plan[index],
            "main_question_index": index,
            "answers": [] if context.phase == "start" else context.request.answers,
        }, allowed_tools=context.active_skill.tool_names)
        if not isinstance(result, InterviewQuestion):
            raise ValueError("问题生成 Skill 返回了错误类型")
        context.question = result
    context.skill_events.append({"skill_name": call.name, "arguments": json.loads(call.arguments_json or "{}")})
    return result


def _ready_to_finish(context: InterviewRunContext) -> bool:
    if context.active_skill is None:
        return False
    if context.phase == "start":
        return context.question is not None
    if context.decision is None:
        return False
    if context.decision.action == "follow_up" or context.completed:
        return True
    return context.question is not None


async def _run_agent_loop(context: InterviewRunContext) -> None:
    messages = _initial_messages(context)
    final_output_corrections = 0
    for turn_number in range(1, MAX_AGENT_TURNS + 1):
        tools = [activation_tool_manifest(RUNTIME_SKILLS)] if context.active_skill is None else RUNTIME_TOOLS.catalog(context.active_skill.tool_names)
        message = await chat_with_tools(messages=list(messages), tools=tools)
        messages.append(_assistant_message(message))
        calls = _parse_tool_calls(message)
        logger.info("interview_agent_step", extra={"turn_number": turn_number, "tool_names": [call.name for call in calls], "phase": context.phase})
        if calls:
            if len(calls) != 1:
                raise ValueError("面试 Agent 每一步只能调用一个工具，以便读取结果后重新规划")
            for call in calls:
                if context.active_skill is None:
                    if call.name != "activate_skill":
                        raise ValueError("必须先调用 activate_skill 加载产品 Skill")
                    try:
                        arguments = ActivateSkillArguments.model_validate_json(call.arguments_json or "{}")
                    except ValueError as error:
                        raise ValueError("Agent 为 activate_skill 生成了无效参数") from error
                    event = "interview_started" if context.phase == "start" else "answer_submitted"
                    context.active_skill = RUNTIME_SKILLS.activate(arguments.skill_name, event=event)
                    result = context.active_skill.activation_result()
                    context.skill_events.append({"skill_name": context.active_skill.name, "event": event})
                else:
                    result = await _execute_tool(context, call)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": _serialize_tool_result(result)})
            continue
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Agent 未返回工具调用或最终结果")
        if not _ready_to_finish(context):
            messages.append({"role": "user", "content": "当前工具结果还不足以结束本轮。请继续调用完成目标所需的工具。"})
            continue
        try:
            AgentFinalOutput.model_validate_json(content)
        except ValueError as error:
            if final_output_corrections >= 1:
                raise ValueError("Agent 最终输出在一次纠正后仍不是符合协议的纯 JSON") from error
            final_output_corrections += 1
            messages.append({
                "role": "user",
                "content": '最终输出格式错误。不要再调用工具，不要输出解释、Markdown 或代码块；只返回纯 JSON：{"status":"ready","reason":"为何可以结束本轮"}。',
            })
            continue
        return
    raise RuntimeError(f"Agent 超过最多 {MAX_AGENT_TURNS} 轮仍未完成本轮任务")


async def _run_loop_node(state: InterviewLoopState) -> dict[str, InterviewRunContext]:
    await _run_agent_loop(state["context"])
    return {"context": state["context"]}


def _compile_interview_loop_graph():
    graph = StateGraph(InterviewLoopState)
    graph.add_node("run_agent_skill_loop", _run_loop_node)
    graph.add_edge(START, "run_agent_skill_loop")
    graph.add_edge("run_agent_skill_loop", END)
    return graph.compile()


INTERVIEW_LOOP_GRAPH = _compile_interview_loop_graph()


def _turn_response(context: InterviewRunContext) -> InterviewTurnResponse:
    assert isinstance(context.request, InterviewTurnRequest)
    assert context.decision is not None
    decision = context.decision
    if decision.action == "follow_up":
        if not decision.question.strip():
            raise ValueError("追问决策缺少问题")
        current = context.request.current_question
        question = InterviewQuestion(
            id=str(uuid4()), stage=interview_skills.STAGE_LABELS[context.plan[current.main_question_index]],
            text=decision.question.strip(), is_follow_up=True, main_question_index=current.main_question_index,
            follow_up_count=current.follow_up_count + 1, resume_evidence="",
        )
        return InterviewTurnResponse(next_question=question, completed=False, decision_reason=decision.reason,
                                     weakness=decision.weakness, total_main_questions=len(context.plan))
    return InterviewTurnResponse(next_question=None if context.completed else context.question, completed=context.completed,
                                 decision_reason=decision.reason, weakness=decision.weakness,
                                 total_main_questions=len(context.plan))


async def start_interview(request: InterviewAgentStartRequest, *, interview_id: str | None = None) -> InterviewStartResponse:
    plan = interview_skills.stage_plan(request.mode, request.focus)
    context = InterviewRunContext(phase="start", request=request, plan=plan)
    state = await INTERVIEW_LOOP_GRAPH.ainvoke({"context": context})
    context = state["context"]
    if context.question is None:
        raise RuntimeError("Agent 完成运行但没有生成第一道问题")
    return InterviewStartResponse(interview_id=interview_id or str(uuid4()), question=context.question, total_main_questions=len(plan))


async def advance_interview(request: InterviewTurnRequest) -> InterviewTurnResponse:
    plan = interview_skills.stage_plan(request.mode, request.focus)
    latest_answer = interview_skills.validate_turn(request, plan)
    context = InterviewRunContext(phase="turn", request=request, plan=plan, latest_answer=latest_answer)
    state = await INTERVIEW_LOOP_GRAPH.ainvoke({"context": context})
    context = state["context"]
    return _turn_response(context)
