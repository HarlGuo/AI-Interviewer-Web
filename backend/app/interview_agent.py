"""Compatibility exports. New code should import the modular agent directly."""

from .agents.interview_graph import advance_interview, start_interview
from .agents.interviewer import interviewer_agent
from .runtime_skills.answer_evaluation import AnswerDecision


def stage_plan(mode: str, focus: str | None) -> list[str]:
    return interviewer_agent.policy.stage_plan(mode, focus)


__all__ = ["AnswerDecision", "advance_interview", "stage_plan", "start_interview"]
