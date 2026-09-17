from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from .descriptors import SkillDescriptor, load_skill_descriptor

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class RuntimeSkill(ABC, Generic[InputT, OutputT]):
    """Executable, typed product skill backed by a human-readable SKILL.md."""

    input_model: type[InputT]
    output_model: type[OutputT]

    def __init__(self, descriptor_path: Path) -> None:
        self.descriptor = load_skill_descriptor(descriptor_path)
        if self.descriptor.input_schema != self.input_model.__name__:
            raise ValueError(f"Skill {self.descriptor.name} 输入契约与实现不一致")
        if self.descriptor.output_schema != self.output_model.__name__:
            raise ValueError(f"Skill {self.descriptor.name} 输出契约与实现不一致")

    async def invoke(self, payload: BaseModel | dict[str, Any]) -> OutputT:
        data = payload.model_dump() if isinstance(payload, BaseModel) else payload
        validated = self.input_model.model_validate(data)
        result = await self.execute(validated)
        return self.output_model.model_validate(result)

    def as_tool(self) -> BaseTool:
        async def run(**kwargs: Any) -> dict[str, Any]:
            return (await self.invoke(kwargs)).model_dump()

        return StructuredTool.from_function(
            coroutine=run,
            name=self.descriptor.name,
            description=self.descriptor.description,
            args_schema=self.input_model,
        )

    @abstractmethod
    async def execute(self, request: InputT) -> OutputT | dict[str, Any]:
        raise NotImplementedError


class SkillRegistry:
    """Single discovery and invocation boundary for all runtime skills."""

    def __init__(self) -> None:
        self._skills: dict[str, RuntimeSkill[Any, Any]] = {}

    def register(self, skill: RuntimeSkill[Any, Any]) -> None:
        name = skill.descriptor.name
        if name in self._skills:
            raise ValueError(f"Skill 已重复注册：{name}")
        self._skills[name] = skill

    def require(self, name: str) -> RuntimeSkill[Any, Any]:
        try:
            return self._skills[name]
        except KeyError as error:
            raise ValueError(f"Agent 请求了未注册的 Skill：{name}") from error

    async def invoke(self, name: str, payload: BaseModel | dict[str, Any]) -> BaseModel:
        return await self.require(name).invoke(payload)

    def tools(self, names: list[str] | None = None) -> list[BaseTool]:
        selected = names or list(self._skills)
        return [self.require(name).as_tool() for name in selected]

    def catalog(self) -> list[SkillDescriptor]:
        return [skill.descriptor for skill in self._skills.values()]
