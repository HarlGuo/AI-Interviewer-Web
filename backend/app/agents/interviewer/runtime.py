from __future__ import annotations

from ...agent_runtime import SkillRegistry
from ...runtime_skills.answer_evaluation import AnswerEvaluationSkill
from ...runtime_skills.question_generation import QuestionGenerationSkill
from ...runtime_skills.report_generation import ReportGenerationSkill
from ...runtime_skills.resume_context import ResumeContextSkill
from .agent import InterviewerAgent


def build_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(ResumeContextSkill())
    registry.register(QuestionGenerationSkill())
    registry.register(AnswerEvaluationSkill())
    registry.register(ReportGenerationSkill())
    return registry


interviewer_agent = InterviewerAgent(build_skill_registry())
