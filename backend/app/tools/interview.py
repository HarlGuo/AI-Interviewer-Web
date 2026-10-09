from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..skills.interview import STAGE_LABELS, safe_resume_sections
from ..skills.runtime import RUNTIME_TOOLS, RuntimeTool


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _load_confirmed_resume(context: object, arguments: BaseModel) -> dict[str, object]:
    NoArguments.model_validate(arguments)
    request = context.request
    context.confirmed_resume = safe_resume_sections(request.resume_sections)
    return {
        "loaded": True,
        "section_count": len(context.confirmed_resume),
        "review_status": request.resume_review_status,
    }


async def _load_job_competencies(context: object, arguments: BaseModel) -> dict[str, object]:
    NoArguments.model_validate(arguments)
    request = context.request
    context.job_context = {
        "target_role": request.target_role,
        "job_description": request.job_description,
        "stage_plan": list(context.plan),
    }
    return {
        "loaded": True,
        "target_role": request.target_role,
        "stages": [STAGE_LABELS[stage] for stage in context.plan],
        "has_job_description": bool(request.job_description.strip()),
    }


async def _get_interview_history(context: object, arguments: BaseModel) -> dict[str, object]:
    NoArguments.model_validate(arguments)
    answers = [] if context.phase == "start" else list(context.request.answers)
    context.interview_history = answers
    return {
        "loaded": True,
        "answer_count": len(answers),
        "recent_questions": [item.question[:300] for item in answers[-6:]],
        "current_main_question_index": None if context.phase == "start" else context.request.current_question.main_question_index,
    }


RUNTIME_TOOLS.register(RuntimeTool(
    name="load_confirmed_resume",
    description="把用户已确认且已脱敏的简历加载到本轮受控状态；只返回加载状态和章节数，不向外层 Agent 暴露完整正文。",
    input_model=NoArguments,
    handler=_load_confirmed_resume,
))
RUNTIME_TOOLS.register(RuntimeTool(
    name="load_job_competencies",
    description="加载目标岗位、JD和程序确定的面试阶段计划，供本轮专业节点使用。",
    input_model=NoArguments,
    handler=_load_job_competencies,
))
RUNTIME_TOOLS.register(RuntimeTool(
    name="get_interview_history",
    description="加载已确认的问题与回答历史到本轮受控状态，并返回最小化的历史元数据。",
    input_model=NoArguments,
    handler=_get_interview_history,
))
