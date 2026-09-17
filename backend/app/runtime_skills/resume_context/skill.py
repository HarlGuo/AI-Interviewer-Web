from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from ...agent_runtime import RuntimeSkill
from ...ai_resume_reviewer import EMAIL_PATTERN, PHONE_PATTERN
from ...schemas import ResumeSection


class ResumeContextInput(BaseModel):
    sections: list[ResumeSection]


class SafeResumeSection(BaseModel):
    title: str
    content: str


class ResumeContextOutput(BaseModel):
    sections: list[SafeResumeSection]
    searchable_text: str


class ResumeContextSkill(RuntimeSkill[ResumeContextInput, ResumeContextOutput]):
    input_model = ResumeContextInput
    output_model = ResumeContextOutput

    def __init__(self) -> None:
        super().__init__(Path(__file__).with_name("SKILL.md"))

    async def execute(self, request: ResumeContextInput) -> ResumeContextOutput:
        safe: list[SafeResumeSection] = []
        remaining = 30_000
        for section in request.sections:
            if section.title in {"基本信息", "其他"} or remaining <= 0:
                continue
            content = PHONE_PATTERN.sub("[PHONE_REDACTED]", EMAIL_PATTERN.sub("[EMAIL_REDACTED]", section.content))
            content = content[: min(12_000, remaining)]
            if content.strip():
                safe.append(SafeResumeSection(title=section.title, content=content))
                remaining -= len(content)
        return ResumeContextOutput(
            sections=safe,
            searchable_text="\n".join(section.content for section in safe),
        )
