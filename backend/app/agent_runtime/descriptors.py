from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class SkillDescriptor(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    version: str
    description: str
    kind: Literal["llm", "deterministic", "hybrid"]
    input_schema: str
    output_schema: str
    instructions: str


class AgentDescriptor(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    version: str
    description: str
    framework: Literal["langgraph"]
    skills: list[str] = Field(min_length=1)
    configuration: dict[str, Any]
    instructions: str


def _load_markdown_descriptor(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"描述文件缺少 YAML frontmatter：{path}")
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError as error:
        raise ValueError(f"描述文件 frontmatter 未闭合：{path}") from error
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise ValueError(f"描述文件 frontmatter 必须是对象：{path}")
    instructions = body.strip()
    if not instructions:
        raise ValueError(f"描述文件缺少正文指令：{path}")
    return metadata, instructions


def load_skill_descriptor(path: Path) -> SkillDescriptor:
    metadata, instructions = _load_markdown_descriptor(path)
    return SkillDescriptor.model_validate({**metadata, "instructions": instructions})


def load_agent_descriptor(path: Path) -> AgentDescriptor:
    metadata, instructions = _load_markdown_descriptor(path)
    return AgentDescriptor.model_validate({**metadata, "instructions": instructions})
