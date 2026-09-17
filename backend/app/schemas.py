from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ResumeSection(BaseModel):
    title: str
    content: str


class ResumeParseResponse(BaseModel):
    filename: str
    page_count: int
    sections: list[ResumeSection]
    warnings: list[str]
    review_status: Literal["rule_only", "ai_verified"] = "rule_only"
    review_issues: list[str] = Field(default_factory=list)


class InterviewConfig(BaseModel):
    target_role: str = Field(min_length=1, max_length=120)
    job_description: str = Field(default="", max_length=20_000)
    mode: Literal["formal", "focused"]
    focus: Literal["self-introduction", "resume-deep-dive", "behavioral", "role-specific"] | None = None


class InterviewQuestion(BaseModel):
    id: str
    stage: str
    text: str
    is_follow_up: bool = False
    main_question_index: int = Field(ge=0)
    follow_up_count: int = Field(ge=0, le=2)
    resume_evidence: str = ""


class InterviewStartResponse(BaseModel):
    interview_id: str
    question: InterviewQuestion
    total_main_questions: int
    source: Literal["resume_driven_agent"] = "resume_driven_agent"


class InterviewAgentStartRequest(InterviewConfig):
    resume_id: UUID | None = None
    resume_sections: list[ResumeSection] = Field(min_length=1, max_length=20)
    resume_review_status: Literal["ai_verified"]


class SpeechDeliveryMetrics(BaseModel):
    duration_ms: int = Field(ge=0, le=30 * 60 * 1000)
    voiced_duration_ms: int = Field(ge=0, le=30 * 60 * 1000)
    pause_count: int = Field(ge=0, le=500)
    average_pause_ms: int = Field(ge=0, le=30 * 60 * 1000)
    longest_pause_ms: int = Field(ge=0, le=30 * 60 * 1000)
    speech_rate_cpm: int = Field(ge=0, le=2000)
    average_volume: float = Field(ge=-2, le=10)
    volume_variation: float = Field(ge=0, le=12)
    sample_count: int = Field(ge=0, le=100_000)

    @model_validator(mode="after")
    def validate_internal_consistency(self) -> "SpeechDeliveryMetrics":
        if self.voiced_duration_ms > self.duration_ms:
            raise ValueError("有效发声时长不能超过回答时长")
        if self.pause_count == 0 and (self.average_pause_ms or self.longest_pause_ms):
            raise ValueError("没有停顿时，停顿时长必须为 0")
        if self.pause_count and self.average_pause_ms > self.longest_pause_ms:
            raise ValueError("平均停顿不能超过最长停顿")
        if self.average_pause_ms * self.pause_count > self.duration_ms:
            raise ValueError("停顿总时长不能超过回答时长")
        return self


class InterviewTurnAnswer(BaseModel):
    question_id: str
    question: str
    answer: str = Field(min_length=1, max_length=12_000)
    stage: str
    is_follow_up: bool
    source: Literal["text", "speech_transcript"] = "text"
    delivery_metrics: SpeechDeliveryMetrics | None = None


class InterviewTurnRequest(InterviewAgentStartRequest):
    interview_id: str
    current_question: InterviewQuestion
    answers: list[InterviewTurnAnswer] = Field(default_factory=list, max_length=30)


class InterviewTurnResponse(BaseModel):
    next_question: InterviewQuestion | None
    completed: bool
    decision_reason: str
    weakness: str = ""
    total_main_questions: int


class AnswerEvidence(BaseModel):
    question_id: str
    question: str
    answer: str = Field(min_length=1, max_length=12_000)
    delivery_metrics: SpeechDeliveryMetrics | None = None


class ReportRequest(BaseModel):
    interview_id: UUID
    target_role: str = Field(min_length=1, max_length=120)
    mode: Literal["formal", "focused"]
    completed: bool
    answers: list[AnswerEvidence] = Field(min_length=1, max_length=20)


class DimensionScore(BaseModel):
    name: str
    level: int | None = Field(default=None, ge=1, le=5)
    score: int | None = Field(default=None, ge=0, le=100)
    basis: str
    evidence: list[str]
    suggestion: str


class QuestionReview(BaseModel):
    question_id: str
    strengths: list[str]
    issues: list[str]
    evidence: list[str]
    suggestion: str


class InterviewReport(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    completion: str
    summary: str
    evidence_notice: str
    dimensions: list[DimensionScore]
    question_reviews: list[QuestionReview]


AnalyticsEventName = Literal[
    "landing_viewed", "registration_submitted", "registration_created", "registration_failed",
    "account_approved", "authenticated_session_started", "sign_in_succeeded", "sign_in_failed",
    "resume_upload_started", "resume_upload_succeeded", "resume_upload_failed",
    "resume_parse_started", "resume_parse_succeeded", "resume_parse_failed", "resume_confirmed",
    "interview_entry_viewed", "interview_mode_selected", "interview_config_completed",
    "interview_start_requested", "interview_started", "interview_start_failed",
    "question_presented", "answer_submit_requested", "answer_accepted", "answer_failed",
    "followup_triggered", "interview_paused", "interview_resumed", "interview_ended_early",
    "interview_completed", "interview_abandoned", "recording_started", "recording_stopped",
    "transcription_succeeded", "transcription_failed", "report_generation_started",
    "report_generation_succeeded", "report_generation_failed", "report_viewed",
    "report_advice_viewed", "feedback_prompt_viewed", "feedback_skipped", "feedback_submitted",
]

ANALYTICS_PROPERTY_KEYS = {
    "mode", "focus", "resume_ready", "replace_existing", "size_bucket", "duration_ms",
    "warning_count", "error_code", "stage", "has_jd", "question_source", "latency_ms",
    "question_index", "is_follow_up", "follow_up", "follow_up_count", "reason_code",
    "input_mode", "recording_duration_bucket", "main_question_index", "answered_count",
    "last_stage", "duration_bucket", "paused", "pause_duration_bucket", "stop_reason",
    "character_bucket", "completed", "rubric_version", "completion_type", "app_surface",
    "schema_version", "utm_source", "utm_medium", "utm_campaign", "utm_content",
    "satisfaction_score", "payment_willingness", "tags", "answers", "ended_early",
}


class AnalyticsEventRequest(BaseModel):
    event_id: UUID
    event_name: AnalyticsEventName
    session_id: UUID
    interview_id: UUID | None = None
    occurred_at: datetime
    page: str = Field(default="", max_length=120)
    properties: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        unknown = set(self.properties) - ANALYTICS_PROPERTY_KEYS
        if unknown:
            raise ValueError(f"不允许的埋点属性：{', '.join(sorted(unknown))}")
        if len(self.properties) > 24:
            raise ValueError("埋点属性数量超过限制")
        for key, value in self.properties.items():
            if isinstance(value, str) and len(value) > 160:
                raise ValueError(f"埋点属性 {key} 过长")
            if isinstance(value, list) and (len(value) > 8 or any(not isinstance(item, str) or len(item) > 40 for item in value)):
                raise ValueError(f"埋点属性 {key} 格式错误")
            if not isinstance(value, (str, int, float, bool, list, type(None))):
                raise ValueError(f"埋点属性 {key} 类型错误")


class InterviewStatusRequest(BaseModel):
    status: Literal["active", "paused", "ended-early"]


class FeedbackRequest(BaseModel):
    satisfaction_score: int = Field(ge=1, le=5)
    payment_willingness: Literal["willing", "depends_on_price", "unwilling", "prefer_not_to_say"]
    tags: list[Literal["问题贴合简历", "追问有深度", "等待太久", "语音体验不顺", "问题重复"]] = Field(default_factory=list, max_length=5)
    comment: str = Field(default="", max_length=500)
    completion_type: Literal["completed", "ended_early"]
