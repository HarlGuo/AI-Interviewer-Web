from __future__ import annotations

from typing import Any, TypedDict

from ...runtime_skills.answer_evaluation import AnswerDecision
from ...runtime_skills.resume_context import ResumeContextOutput
from ...schemas import (
    InterviewAgentStartRequest,
    InterviewQuestion,
    InterviewReport,
    InterviewStartResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
    ProjectInterviewContext,
    ReportRequest,
)


class SkillTrace(TypedDict):
    skill: str
    version: str
    input_contract: str
    output_contract: str
    selection_reason: str


class StartState(TypedDict, total=False):
    request: InterviewAgentStartRequest
    interview_id: str
    plan: list[str]
    resume_context: ResumeContextOutput
    question: InterviewQuestion
    response: InterviewStartResponse
    skill_trace: list[SkillTrace]


class TurnState(TypedDict, total=False):
    request: InterviewTurnRequest
    plan: list[str]
    latest_answer: str
    resume_context: ResumeContextOutput
    decision: AnswerDecision
    project_context: ProjectInterviewContext
    next_main_index: int
    response: InterviewTurnResponse
    skill_trace: list[SkillTrace]


class ReportState(TypedDict, total=False):
    request: ReportRequest
    report: InterviewReport
    skill_trace: list[SkillTrace]


AgentGraphState = StartState | TurnState | ReportState
StateUpdate = dict[str, Any]
