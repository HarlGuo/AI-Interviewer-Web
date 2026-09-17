"""Compatibility entrypoints; implementation lives in the modular interviewer package."""

from __future__ import annotations

from ..schemas import InterviewAgentStartRequest, InterviewStartResponse, InterviewTurnRequest, InterviewTurnResponse
from .interviewer import interviewer_agent

START_GRAPH = interviewer_agent.start_graph
TURN_GRAPH = interviewer_agent.turn_graph


async def start_interview(request: InterviewAgentStartRequest, *, interview_id: str | None = None) -> InterviewStartResponse:
    return await interviewer_agent.start(request, interview_id=interview_id)


async def advance_interview(request: InterviewTurnRequest) -> InterviewTurnResponse:
    return await interviewer_agent.advance(request)
