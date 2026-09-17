"""Deprecated compatibility helpers for callers outside the agent package.

New product behavior must be implemented as a runtime skill under
``app/runtime_skills`` and registered in ``agents/interviewer/runtime.py``.
"""

from __future__ import annotations

from uuid import uuid4

from ..agents.interviewer import interviewer_agent
from ..runtime_skills.answer_evaluation import AnswerDecision, AnswerEvaluationInput
from ..runtime_skills.question_generation import PreviousAnswer, QuestionGenerationInput
from ..runtime_skills.resume_context import ResumeContextInput
from ..schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewTurnRequest

MAX_FOLLOW_UPS = interviewer_agent.policy.max_follow_ups
FORMAL_STAGES = [stage.key for stage in interviewer_agent.policy.configuration.formal_stages]
STAGE_LABELS = {stage.key: stage.label for stage in interviewer_agent.policy.configuration.formal_stages}


def stage_plan(mode: str, focus: str | None) -> list[str]:
    return interviewer_agent.policy.stage_plan(mode, focus)


def validate_turn(request: InterviewTurnRequest, plan: list[str]) -> str:
    return interviewer_agent.policy.validate_turn(request, plan)


async def generate_main_question(
    request: InterviewAgentStartRequest,
    stage: str,
    index: int,
    answers: list,
) -> InterviewQuestion:
    resume_skill = interviewer_agent.registry.require(interviewer_agent.policy.skill("resume_context"))
    context = await resume_skill.invoke(ResumeContextInput(
        sections=request.resume_sections,
    ))
    question_skill = interviewer_agent.registry.require(interviewer_agent.policy.skill("question_generation"))
    generated = await question_skill.invoke(QuestionGenerationInput(
        stage=stage,
        stage_label=interviewer_agent.policy.label(stage),
        main_question_number=index + 1,
        target_role=request.target_role,
        job_description=request.job_description,
        confirmed_resume=context.sections,
        previous_answers=[PreviousAnswer(question=item.question[:1000], answer=item.answer[:4000]) for item in answers[-6:]],
        searchable_resume_text=context.searchable_text,
    ))
    return InterviewQuestion(
        id=str(uuid4()),
        stage=interviewer_agent.policy.label(stage),
        text=generated.question,
        is_follow_up=False,
        main_question_index=index,
        follow_up_count=0,
        resume_evidence=generated.resume_evidence,
    )


async def evaluate_answer(request: InterviewTurnRequest, latest_answer: str) -> AnswerDecision:
    fixed = interviewer_agent.policy.deterministic_decision(request, latest_answer)
    if fixed is not None:
        return fixed
    resume_skill = interviewer_agent.registry.require(interviewer_agent.policy.skill("resume_context"))
    context = await resume_skill.invoke(ResumeContextInput(
        sections=request.resume_sections,
    ))
    evaluation_skill = interviewer_agent.registry.require(interviewer_agent.policy.skill("answer_evaluation"))
    return await evaluation_skill.invoke(AnswerEvaluationInput(
        target_role=request.target_role,
        job_description=request.job_description,
        confirmed_resume=context.sections,
        current_question=request.current_question,
        latest_answer=latest_answer,
        previous_answers=request.answers[-11:-1],
        remaining_follow_ups=MAX_FOLLOW_UPS - request.current_question.follow_up_count,
    ))


__all__ = [
    "AnswerDecision",
    "FORMAL_STAGES",
    "MAX_FOLLOW_UPS",
    "STAGE_LABELS",
    "evaluate_answer",
    "generate_main_question",
    "stage_plan",
    "validate_turn",
]
