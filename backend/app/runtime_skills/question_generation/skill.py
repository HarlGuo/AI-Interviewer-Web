from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ...agent_runtime import RuntimeSkill
from ...llm.deepseek import chat_json
from ...presentation import clean_user_facing_text
from ..resume_context import SafeResumeSection


class PreviousAnswer(BaseModel):
    question: str
    answer: str


class QuestionGenerationInput(BaseModel):
    stage: str
    stage_label: str
    main_question_number: int = Field(ge=1)
    target_role: str
    job_description: str = ""
    confirmed_resume: list[SafeResumeSection]
    previous_answers: list[PreviousAnswer] = Field(default_factory=list)
    searchable_resume_text: str = ""
    excluded_resume_evidence: list[str] = Field(default_factory=list, max_length=10)


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    resume_evidence: str = ""


class QuestionGenerationSkill(RuntimeSkill[QuestionGenerationInput, GeneratedQuestion]):
    input_model = QuestionGenerationInput
    output_model = GeneratedQuestion

    def __init__(self) -> None:
        super().__init__(Path(__file__).with_name("SKILL.md"))

    async def execute(self, request: QuestionGenerationInput) -> GeneratedQuestion:
        if request.stage == "self-introduction":
            return GeneratedQuestion(
                question=(
                    f"请结合你的真实经历，用 2—3 分钟做一段面向{request.target_role}岗位的自我介绍，"
                    "重点说明与你应聘岗位最相关的经验、个人贡献和求职动机。"
                ),
                resume_evidence="",
            )
        raw = await chat_json(
            messages=[
                {"role": "system", "content": self.descriptor.instructions + "\n输出字段：question、resume_evidence。"},
                {"role": "user", "content": "输入 JSON：\n" + json.dumps(request.model_dump(exclude={"searchable_resume_text"}), ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=600,
            purpose="question_generation",
        )
        generated = GeneratedQuestion.model_validate(raw)
        evidence = generated.resume_evidence
        if not evidence or evidence not in request.searchable_resume_text or evidence in request.excluded_resume_evidence:
            evidence = ""
        return generated.model_copy(update={
            "question": clean_user_facing_text(generated.question),
            "resume_evidence": clean_user_facing_text(evidence),
        })
