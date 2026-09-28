from __future__ import annotations

import json
import logging
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict
from langgraph.graph import END, START, StateGraph

from ..llm.deepseek import chat_with_tools
from ..prompts.interview import INTERVIEW_AGENT_SYSTEM_PROMPT
from ..schemas import ResumeParseResponse
from ..skills.runtime import AgentToolCall, ActivateSkillArguments, RUNTIME_SKILLS, RUNTIME_TOOLS, RuntimeSkill, activation_tool_manifest

logger = logging.getLogger(__name__)

MAX_RESUME_AGENT_TURNS = 6


class ResumeAgentState(TypedDict):
    filename: str
    data: bytes
    result: ResumeParseResponse | None


class ResumeAgentFinalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"]
    reason: str


def _parse_tool_call(message: dict[str, Any]) -> AgentToolCall | None:
    calls = message.get("tool_calls") or []
    if not calls:
        return None
    if len(calls) != 1:
        raise ValueError("简历 Agent 每一步只能调用一个工具，以便读取结果后重新规划")
    raw = calls[0]
    function = raw.get("function") if isinstance(raw, dict) else None
    if not isinstance(function, dict) or not raw.get("id") or not function.get("name"):
        raise ValueError("简历 Agent 返回了格式错误的工具调用")
    return AgentToolCall(id=str(raw["id"]), name=str(function["name"]), arguments_json=str(function.get("arguments") or "{}"))


def _assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"role": "assistant", "content": message.get("content")}
    if message.get("tool_calls"):
        normalized["tool_calls"] = message["tool_calls"]
    return normalized


async def _run_resume_agent(filename: str, data: bytes) -> ResumeParseResponse:
    context: dict[str, Any] = {"filename": filename, "data": data}
    active_skill: RuntimeSkill | None = None
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": INTERVIEW_AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": "产品运行时 Skill 目录与本轮可信状态摘要：\n" + json.dumps({
            "skills": RUNTIME_SKILLS.catalog(),
            "task": {"event": "resume_uploaded", "goal": "安全解析、结构复核用户上传的 PDF 简历，并等待用户确认"},
        }, ensure_ascii=False)},
    ]
    for turn_number in range(1, MAX_RESUME_AGENT_TURNS + 1):
        tools = [activation_tool_manifest(RUNTIME_SKILLS)] if active_skill is None else RUNTIME_TOOLS.catalog(active_skill.tool_names)
        message = await chat_with_tools(messages=list(messages), tools=tools, max_tokens=800)
        messages.append(_assistant_message(message))
        call = _parse_tool_call(message)
        logger.info("resume_agent_step", extra={"turn_number": turn_number, "tool_name": call.name if call else None})
        if call is not None:
            if active_skill is None:
                if call.name != "activate_skill":
                    raise ValueError("必须先调用 activate_skill 加载产品 Skill")
                try:
                    arguments = ActivateSkillArguments.model_validate_json(call.arguments_json or "{}")
                except ValueError as error:
                    raise ValueError("Agent 为 activate_skill 生成了无效参数") from error
                active_skill = RUNTIME_SKILLS.activate(arguments.skill_name, event="resume_uploaded")
                result: Any = active_skill.activation_result()
            else:
                if call.name == "extract_resume_pdf" and "parsed" in context:
                    raise ValueError("本轮已经完成确定性 PDF 提取，不能重复执行")
                if call.name == "verify_resume_structure" and "result" in context:
                    raise ValueError("本轮已经完成 AI 结构复核，不能重复执行")
                result = await RUNTIME_TOOLS.execute(call, context, allowed_tools=active_skill.tool_names)
            observation = result.model_dump_json() if isinstance(result, BaseModel) else json.dumps(result, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": observation})
            continue
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("简历 Agent 未返回工具调用或最终结果")
        if active_skill is None or "result" not in context:
            messages.append({"role": "user", "content": "当前 Skill 执行结果还不足以结束本轮，请继续调用所需工具。"})
            continue
        ResumeAgentFinalOutput.model_validate_json(content)
        return context["result"]
    raise RuntimeError(f"简历 Agent 超过最多 {MAX_RESUME_AGENT_TURNS} 轮仍未完成解析")


async def _run_resume_node(state: ResumeAgentState) -> dict[str, ResumeParseResponse]:
    return {"result": await _run_resume_agent(state["filename"], state["data"])}


def _compile_resume_agent_graph():
    graph = StateGraph(ResumeAgentState)
    graph.add_node("run_resume_skill_loop", _run_resume_node)
    graph.add_edge(START, "run_resume_skill_loop")
    graph.add_edge("run_resume_skill_loop", END)
    return graph.compile()


RESUME_AGENT_GRAPH = _compile_resume_agent_graph()


async def parse_resume_with_agent(filename: str, data: bytes) -> ResumeParseResponse:
    state = await RESUME_AGENT_GRAPH.ainvoke({"filename": filename, "data": data, "result": None})
    result = state["result"]
    if result is None:
        raise RuntimeError("简历 Agent 完成运行但没有返回解析结果")
    return result
