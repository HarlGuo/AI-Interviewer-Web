from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentToolCall:
    id: str
    name: str
    arguments_json: str


ToolHandler = Callable[[Any, BaseModel], Awaitable[Any]]


@dataclass(frozen=True)
class RuntimeTool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler

    def manifest(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RuntimeTool] = {}

    def register(self, tool: RuntimeTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool 已注册：{tool.name}")
        self._tools[tool.name] = tool

    def catalog(self, names: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        selected = self._tools.values() if names is None else (self.get(name) for name in names)
        return [tool.manifest() for tool in selected]

    def get(self, name: str) -> RuntimeTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Agent 选择了未注册的 Tool：{name}")
        return tool

    async def execute(self, call: AgentToolCall, context: Any, *, allowed_tools: tuple[str, ...]) -> Any:
        if call.name not in allowed_tools:
            raise ValueError(f"当前 Skill 不允许调用 Tool：{call.name}")
        tool = self.get(call.name)
        try:
            raw_arguments = json.loads(call.arguments_json or "{}")
        except json.JSONDecodeError as error:
            raise ValueError(f"Agent 为 Tool {call.name} 生成了无效 JSON 参数") from error
        arguments = tool.input_model.model_validate(raw_arguments)
        result = await tool.handler(context, arguments)
        logger.info(
            "runtime_tool_executed",
            extra={"tool_name": call.name, "tool_arguments": raw_arguments, "result_type": type(result).__name__},
        )
        return result


@dataclass(frozen=True)
class RuntimeSkill:
    name: str
    description: str
    instructions: str
    tool_names: tuple[str, ...]
    supported_events: tuple[str, ...]
    input_contract: tuple[str, ...]
    output_contract: tuple[str, ...]
    fact_constraints: tuple[str, ...]
    failure_policy: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]

    def manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "supported_events": list(self.supported_events),
        }

    def activation_result(self) -> dict[str, Any]:
        return {
            "skill_name": self.name,
            "instructions": self.instructions,
            "available_tools": list(self.tool_names),
            "input_contract": list(self.input_contract),
            "output_contract": list(self.output_contract),
            "fact_constraints": list(self.fact_constraints),
            "failure_policy": list(self.failure_policy),
            "acceptance_criteria": list(self.acceptance_criteria),
        }


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, RuntimeSkill] = {}

    def register(self, skill: RuntimeSkill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill 已注册：{skill.name}")
        self._skills[skill.name] = skill

    def catalog(self) -> list[dict[str, Any]]:
        return [skill.manifest() for skill in self._skills.values()]

    def activate(self, name: str, *, event: str) -> RuntimeSkill:
        skill = self._skills.get(name)
        if skill is None:
            raise ValueError(f"Agent 选择了未注册的 Skill：{name}")
        if event not in skill.supported_events:
            raise ValueError(f"Skill {name} 不支持事件：{event}")
        logger.info("runtime_skill_activated", extra={"skill_name": name, "event": event})
        return skill


class ActivateSkillArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str


def activation_tool_manifest(skills: SkillRegistry) -> dict[str, Any]:
    names = [item["name"] for item in skills.catalog()]
    return {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": "根据当前用户事件，从产品运行时 Skill 目录中选择并加载一个最适合的 Skill。必须先激活 Skill，才能使用其 Tools。",
            "parameters": {
                "type": "object",
                "properties": {"skill_name": {"type": "string", "enum": names}},
                "required": ["skill_name"],
                "additionalProperties": False,
            },
        },
    }


RUNTIME_TOOLS = ToolRegistry()
RUNTIME_SKILLS = SkillRegistry()
