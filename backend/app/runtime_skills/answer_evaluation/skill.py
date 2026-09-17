from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ...agent_runtime import RuntimeSkill
from ...llm.deepseek import chat_json
from ...schemas import InterviewQuestion, InterviewTurnAnswer
from ..resume_context import SafeResumeSection


class AnswerEvaluationInput(BaseModel):
    target_role: str
    job_description: str = ""
    confirmed_resume: list[SafeResumeSection]
    current_question: InterviewQuestion
    latest_answer: str
    previous_answers: list[InterviewTurnAnswer] = Field(default_factory=list)
    remaining_follow_ups: int = Field(ge=1, le=2)


class AnswerDecision(BaseModel):
    action: Literal["follow_up", "next_main"]
    question: str = ""
    reason: str = Field(min_length=1, max_length=500)
    weakness: str = ""


class AnswerEvaluationSkill(RuntimeSkill[AnswerEvaluationInput, AnswerDecision]):
    input_model = AnswerEvaluationInput
    output_model = AnswerDecision

    def __init__(self) -> None:
        super().__init__(Path(__file__).with_name("SKILL.md"))

    async def execute(self, request: AnswerEvaluationInput) -> AnswerDecision:
        raw = await chat_json(
            messages=[
                {"role": "system", "content": self.descriptor.instructions + "\n输出字段：action、question、reason、weakness。"},
                {"role": "user", "content": "输入 JSON：\n" + json.dumps(request.model_dump(), ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=1200,
            purpose="answer_evaluation",
        )
        return AnswerDecision.model_validate(raw)
