from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ...agent_runtime import RuntimeSkill
from ...llm.deepseek import chat_json
from ...presentation import clean_user_facing_text
from ...schemas import InterviewTurnAnswer, ProjectCoverage, ProjectTarget


class CoverageEvidence(BaseModel):
    target: ProjectTarget
    answer_id: str
    evidence_quote: str = Field(min_length=1, max_length=500)


class ResumeProjectFollowUpInput(BaseModel):
    target_role: str
    project_key: str
    project_resume_evidence: str
    latest_answer: str
    project_answers: list[InterviewTurnAnswer] = Field(min_length=1, max_length=3)
    coverage: ProjectCoverage
    follow_up_count: int = Field(ge=0, le=2)
    project_round_count: int = Field(ge=1, le=3)
    consecutive_insufficient_count: int = Field(ge=0, le=2)


class ResumeProjectFollowUpDecision(BaseModel):
    action: Literal["follow_up", "switch_project", "leave_resume_deep_dive"]
    information_quality: Literal["effective", "insufficient", "not_responsible"]
    newly_covered_targets: list[CoverageEvidence] = Field(default_factory=list, max_length=5)
    next_target: ProjectTarget | None = None
    question: str = Field(default="", max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    weakness: str = Field(default="", max_length=500)


class ResumeProjectFollowUpSkill(RuntimeSkill[ResumeProjectFollowUpInput, ResumeProjectFollowUpDecision]):
    input_model = ResumeProjectFollowUpInput
    output_model = ResumeProjectFollowUpDecision

    def __init__(self) -> None:
        super().__init__(Path(__file__).with_name("SKILL.md"))

    async def execute(self, request: ResumeProjectFollowUpInput) -> ResumeProjectFollowUpDecision:
        raw = await chat_json(
            messages=[
                {
                    "role": "system",
                    "content": self.descriptor.instructions
                    + "\n输出字段：action、information_quality、newly_covered_targets、next_target、question、reason、weakness。",
                },
                {"role": "user", "content": "输入 JSON：\n" + json.dumps(request.model_dump(), ensure_ascii=False)},
            ],
            temperature=0.1,
            max_tokens=1600,
            purpose="resume_project_followup",
        )
        decision = ResumeProjectFollowUpDecision.model_validate(raw)
        answers = {item.question_id: item.answer for item in request.project_answers}
        grounded = [
            item
            for item in decision.newly_covered_targets
            if item.answer_id in answers and item.evidence_quote in answers[item.answer_id]
        ]
        if decision.action == "follow_up" and not decision.question.strip():
            raise ValueError("项目追问决策缺少问题")
        return decision.model_copy(update={
            "newly_covered_targets": grounded,
            "question": clean_user_facing_text(decision.question) if decision.action == "follow_up" else "",
        })
