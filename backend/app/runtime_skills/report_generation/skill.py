from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from ...agent_runtime import RuntimeSkill
from ...llm.deepseek import chat_json
from ...schemas import DimensionScore, InterviewReport, QuestionReview, ReportRequest
from ...scoring import DIMENSIONS, LEVEL_ANCHORS, finalize_dimensions, replace_delivery_dimension


class ReportGenerationInput(ReportRequest):
    pass


class ModelDimensionScore(DimensionScore):
    evidence_question_ids: list[str] = Field(default_factory=list, max_length=2)


class ModelInterviewReport(InterviewReport):
    dimensions: list[ModelDimensionScore]


def _answer_excerpt(answer: str, limit: int = 280) -> str:
    return answer.strip()[:limit]


class ReportGenerationSkill(RuntimeSkill[ReportGenerationInput, InterviewReport]):
    input_model = ReportGenerationInput
    output_model = InterviewReport

    def __init__(self) -> None:
        super().__init__(Path(__file__).with_name("SKILL.md"))

    async def execute(self, request: ReportGenerationInput) -> InterviewReport:
        system = (
            self.descriptor.instructions
            + "\n行为锚点：" + json.dumps(LEVEL_ANCHORS, ensure_ascii=False)
            + "\n维度必须且只能按此顺序出现：" + json.dumps(DIMENSIONS, ensure_ascii=False)
            + "\n输出字段：overall_score、completion、summary、evidence_notice、dimensions、question_reviews。"
            + " overall_score 固定返回 0；dimensions 中包含 name、level、score=null、basis、evidence=[]、"
              "evidence_question_ids、suggestion。"
        )
        content = await chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "请根据以下真实面试数据生成 JSON 报告：\n" + request.model_dump_json(exclude={"interview_id"})},
            ],
            temperature=0.1,
            max_tokens=5000,
            purpose="report_generation",
        )
        model_report = ModelInterviewReport.model_validate(content)
        answers_by_id = {item.question_id: item.answer for item in request.answers}
        grounded_dimensions: list[DimensionScore] = []
        for item in model_report.dimensions:
            grounded = [
                _answer_excerpt(answers_by_id[question_id])
                for question_id in dict.fromkeys(item.evidence_question_ids)
                if question_id in answers_by_id
            ]
            grounded_dimensions.append(DimensionScore(
                name=item.name,
                level=item.level,
                score=None,
                basis=item.basis,
                evidence=grounded or item.evidence,
                suggestion=item.suggestion,
            ))
        report = InterviewReport(
            overall_score=0,
            completion=model_report.completion,
            summary=model_report.summary,
            evidence_notice=model_report.evidence_notice,
            dimensions=grounded_dimensions,
            question_reviews=model_report.question_reviews,
        )
        answer_text = "\n".join(item.answer for item in request.answers)
        dimensions, overall = finalize_dimensions(replace_delivery_dimension(report.dimensions, request.answers), answer_text)
        reviews_by_question = {item.question_id: item for item in report.question_reviews}
        safe_reviews: list[QuestionReview] = []
        for answer in request.answers:
            review = reviews_by_question.get(answer.question_id)
            if review is None:
                safe_reviews.append(QuestionReview(
                    question_id=answer.question_id,
                    strengths=[],
                    issues=["证据不足，无法形成可靠的单题评价。"],
                    evidence=[],
                    suggestion="补充具体背景、个人行动、决策依据和可核对结果后再评估。",
                ))
            else:
                safe_reviews.append(review.model_copy(update={"evidence": [_answer_excerpt(answer.answer)]}))
        return report.model_copy(update={"dimensions": dimensions, "overall_score": overall, "question_reviews": safe_reviews})
