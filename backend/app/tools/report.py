from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..deepseek import build_interview_report, sanitize_report_text
from ..schemas import AnswerEvidence, ReportRequest
from ..scoring import DIMENSIONS
from ..skills.runtime import RUNTIME_TOOLS, RuntimeTool
from ..supabase_store import record_report
from .interview import NoArguments


class ReportDimensionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    level: int | None = Field(default=None, ge=1, le=5)
    basis: str = Field(min_length=1, max_length=2_000)
    evidence_question_ids: list[str] = Field(default_factory=list, max_length=2)
    suggestion: str = Field(min_length=1, max_length=2_000)


class ReportQuestionReviewDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    strengths: list[str] = Field(default_factory=list, max_length=5)
    issues: list[str] = Field(default_factory=list, max_length=5)
    suggestion: str = Field(min_length=1, max_length=2_000)


class SubmitReportAssessmentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=4_000)
    evidence_notice: str = Field(min_length=1, max_length=2_000)
    dimensions: list[ReportDimensionDraft] = Field(min_length=6, max_length=6)
    question_reviews: list[ReportQuestionReviewDraft]


def _get_report_request(context: object) -> ReportRequest:
    cached = getattr(context, "report_request", None)
    if cached is not None:
        return cached
    request = context.request
    if not context.completed:
        raise ValueError("只能在最后一道主问题完成后生成报告")
    report_request = ReportRequest(
        interview_id=UUID(str(request.interview_id)),
        target_role=request.target_role,
        mode=request.mode,
        completed=True,
        answers=[
            AnswerEvidence(
                question_id=item.question_id,
                question=item.question,
                answer=item.answer,
                delivery_metrics=item.delivery_metrics,
            )
            for item in request.answers
        ],
    )
    context.report_request = report_request
    return report_request


async def _load_completed_interview(context: object, arguments: BaseModel) -> dict[str, Any]:
    NoArguments.model_validate(arguments)
    request = _get_report_request(context)
    context.completed_interview_loaded = True
    return {
        "completed": True,
        "target_role": request.target_role,
        "mode": request.mode,
        "answered_count": len(request.answers),
        "answers": [
            {
                "question_id": item.question_id,
                "question": sanitize_report_text(item.question),
                "answer": sanitize_report_text(item.answer),
            }
            for item in request.answers
        ],
    }


async def _load_delivery_metrics(context: object, arguments: BaseModel) -> dict[str, Any]:
    NoArguments.model_validate(arguments)
    request = _get_report_request(context)
    context.delivery_metrics_loaded = True
    measured = [
        {
            "question_id": item.question_id,
            "duration_ms": item.delivery_metrics.duration_ms,
            "speech_rate_cpm": item.delivery_metrics.speech_rate_cpm,
            "pause_count": item.delivery_metrics.pause_count,
            "average_pause_ms": item.delivery_metrics.average_pause_ms,
            "longest_pause_ms": item.delivery_metrics.longest_pause_ms,
            "volume_variation": item.delivery_metrics.volume_variation,
        }
        for item in request.answers
        if item.delivery_metrics is not None
    ]
    return {"measured_answer_count": len(measured), "delivery_metrics": measured}


def _validate_assessment(arguments: SubmitReportAssessmentArguments, request: ReportRequest) -> None:
    names = [item.name for item in arguments.dimensions]
    if names != list(DIMENSIONS):
        raise ValueError(f"维度必须且只能按规定顺序提交：{list(DIMENSIONS)}")
    valid_ids = {item.question_id for item in request.answers}
    errors: list[str] = []
    for dimension in arguments.dimensions:
        invalid = [item for item in dimension.evidence_question_ids if item not in valid_ids]
        if invalid:
            errors.append(f"{dimension.name}包含非本场证据ID：{invalid}")
        if len(set(dimension.evidence_question_ids)) != len(dimension.evidence_question_ids):
            errors.append(f"{dimension.name}包含重复证据ID")
        if dimension.name == "流畅度" and dimension.level is not None:
            errors.append("流畅度level必须为null，由代码使用语音指标计算")
        if dimension.level is not None and not dimension.evidence_question_ids:
            errors.append(f"{dimension.name}有level但没有证据题目ID")
        if dimension.level is None and dimension.evidence_question_ids:
            errors.append(f"{dimension.name}没有level时不应提交证据题目ID")
    review_ids = [item.question_id for item in arguments.question_reviews]
    invalid_reviews = [item for item in review_ids if item not in valid_ids]
    if invalid_reviews:
        errors.append(f"单题评价包含非本场题目ID：{invalid_reviews}")
    if len(set(review_ids)) != len(review_ids):
        errors.append("单题评价包含重复题目ID")
    if errors:
        raise ValueError("；".join(errors))


async def _submit_report_assessment(context: object, arguments: BaseModel) -> dict[str, Any]:
    if not getattr(context, "completed_interview_loaded", False):
        raise ValueError("提交评价前必须先调用load_completed_interview")
    if not getattr(context, "delivery_metrics_loaded", False):
        raise ValueError("提交评价前必须先调用load_delivery_metrics")
    assessment = SubmitReportAssessmentArguments.model_validate(arguments)
    request = _get_report_request(context)
    _validate_assessment(assessment, request)
    content = {
        "overall_score": 0,
        "completion": "",
        "summary": assessment.summary,
        "evidence_notice": assessment.evidence_notice,
        "dimensions": [
            {
                **item.model_dump(),
                "score": None,
                "evidence": [],
            }
            for item in assessment.dimensions
        ],
        "question_reviews": [
            {
                **item.model_dump(),
                "evidence": [],
            }
            for item in assessment.question_reviews
        ],
    }
    context.report = build_interview_report(content, request)
    return {
        "validated": True,
        "overall_score": context.report.overall_score,
        "dimension_count": len(context.report.dimensions),
        "review_count": len(context.report.question_reviews),
        "next_required_tool": "save_interview_report",
    }


async def _save_interview_report(context: object, arguments: BaseModel) -> dict[str, Any]:
    NoArguments.model_validate(arguments)
    if getattr(context, "report", None) is None:
        raise ValueError("必须先调用submit_report_assessment并通过校验")
    user_id = getattr(context, "user_id", None)
    if not user_id:
        raise ValueError("缺少报告保存所需的用户标识")
    context.report_save_attempted = True
    context.report_persisted = await record_report(user_id, str(context.request.interview_id), context.report)
    return {"save_attempted": True, "persisted": context.report_persisted}


RUNTIME_TOOLS.register(RuntimeTool(
    name="load_completed_interview",
    description="在程序确认面试完成后，加载本场经脱敏的真实问题、回答和题目ID。",
    input_model=NoArguments,
    handler=_load_completed_interview,
))
RUNTIME_TOOLS.register(RuntimeTool(
    name="load_delivery_metrics",
    description="加载本场真实语音回答的语速、停顿和收音指标；无有效数据时返回空列表。",
    input_model=NoArguments,
    handler=_load_delivery_metrics,
))
RUNTIME_TOOLS.register(RuntimeTool(
    name="submit_report_assessment",
    description="提交Main Agent产生的六维语义评价；代码校验维度、证据ID和Schema，回填真实回答并确定性计分。",
    input_model=SubmitReportAssessmentArguments,
    handler=_submit_report_assessment,
))
RUNTIME_TOOLS.register(RuntimeTool(
    name="save_interview_report",
    description="保存已通过硬校验的最终报告；未提交或校验失败的报告不可保存。",
    input_model=NoArguments,
    handler=_save_interview_report,
))
