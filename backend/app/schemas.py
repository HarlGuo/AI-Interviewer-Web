from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    resume_sections: list[ResumeSection] = Field(min_length=1, max_length=20)
    resume_review_status: Literal["ai_verified"]


class InterviewTurnAnswer(BaseModel):
    question_id: str
    question: str
    answer: str = Field(min_length=1, max_length=12_000)
    stage: str
    is_follow_up: bool


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


class ReportRequest(BaseModel):
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
