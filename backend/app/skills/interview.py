from __future__ import annotations

import json
import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..ai_resume_reviewer import EMAIL_PATTERN, PHONE_PATTERN
from ..llm.deepseek import chat_json
from ..prompts.interview import EVALUATION_SYSTEM_PROMPT, QUESTION_SYSTEM_PROMPT
from ..presentation import clean_user_facing_text
from ..schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewTurnRequest, ResumeSection
from .runtime import RUNTIME_SKILLS, RUNTIME_TOOLS, RuntimeSkill, RuntimeTool

MAX_FOLLOW_UPS = 2
FORMAL_STAGES = ["self-introduction", "resume-deep-dive", "behavioral", "role-specific", "closing"]
STAGE_LABELS = {"self-introduction": "自我介绍", "resume-deep-dive": "简历深挖", "behavioral": "行为面试", "role-specific": "岗位专业", "closing": "结束反问"}
UNKNOWN_ANSWER = re.compile(r"^(不知道|不清楚|不会|不了解|没有(?:相关)?经历|暂时没有|想不起来)[。.!！\s]*$")


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    resume_evidence: str = ""


class AnswerDecision(BaseModel):
    action: Literal["follow_up", "next_main"]
    question: str = ""
    reason: str = Field(min_length=1, max_length=500)
    weakness: str = ""


class GenerateQuestionArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluateAnswerArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


def stage_plan(mode: str, focus: str | None) -> list[str]:
    return [focus or "self-introduction"] * 3 if mode == "focused" else FORMAL_STAGES.copy()


def validate_turn(request: InterviewTurnRequest, plan: list[str]) -> str:
    current = request.current_question
    if current.main_question_index >= len(plan) or current.stage != STAGE_LABELS[plan[current.main_question_index]]:
        raise ValueError("当前问题与面试计划不一致")
    answer = request.answers[-1].answer.strip() if request.answers else ""
    if not answer:
        raise ValueError("缺少当前问题的回答")
    return answer


def _safe_resume(sections: list[ResumeSection]) -> list[dict[str, str]]:
    safe, remaining = [], 30_000
    for section in sections:
        if section.title in {"基本信息", "其他"} or remaining <= 0:
            continue
        content = PHONE_PATTERN.sub("[PHONE_REDACTED]", EMAIL_PATTERN.sub("[EMAIL_REDACTED]", section.content))[:min(12_000, remaining)]
        safe.append({"title": section.title, "content": content})
        remaining -= len(content)
    return safe


async def generate_main_question(request: InterviewAgentStartRequest, stage: str, index: int, answers: list[object]) -> InterviewQuestion:
    data = {"stage": stage, "stage_label": STAGE_LABELS[stage], "main_question_number": index + 1, "target_role": request.target_role,
            "job_description": request.job_description, "confirmed_resume": _safe_resume(request.resume_sections),
            "previous_answers": [{"question": getattr(x, "question", "")[:1000], "answer": getattr(x, "answer", "")[:4000]} for x in answers[-6:]]}
    generated = GeneratedQuestion.model_validate(await chat_json(messages=[{"role": "system", "content": QUESTION_SYSTEM_PROMPT}, {"role": "user", "content": "输入 JSON：\n" + json.dumps(data, ensure_ascii=False)}], temperature=0.2, max_tokens=1200, purpose="question_generation"))
    resume_text = "\n".join(x.content for x in request.resume_sections if x.title not in {"基本信息", "其他"})
    evidence = generated.resume_evidence if generated.resume_evidence and generated.resume_evidence in resume_text else ""
    return InterviewQuestion(id=str(uuid4()), stage=STAGE_LABELS[stage], text=clean_user_facing_text(generated.question), is_follow_up=False, main_question_index=index, follow_up_count=0, resume_evidence=clean_user_facing_text(evidence))


async def evaluate_answer(request: InterviewTurnRequest, latest_answer: str) -> AnswerDecision:
    current = request.current_question
    if current.follow_up_count >= MAX_FOLLOW_UPS:
        return AnswerDecision(action="next_main", reason=f"已达到单道主问题最多 {MAX_FOLLOW_UPS} 次追问限制，进入下一阶段。", weakness="当前主问题已完成规定的追问次数")
    if UNKNOWN_ANSWER.fullmatch(latest_answer):
        return AnswerDecision(action="next_main", reason="用户明确表示不知道或没有相关经历", weakness="当前问题缺少可用回答证据")
    data = {"target_role": request.target_role, "job_description": request.job_description, "confirmed_resume": _safe_resume(request.resume_sections),
            "current_question": current.model_dump(), "latest_answer": latest_answer,
            "previous_answers": [{**x.model_dump(), "answer": x.answer[:4000]} for x in request.answers[-11:-1]],
            "remaining_follow_ups": MAX_FOLLOW_UPS - current.follow_up_count}
    return AnswerDecision.model_validate(await chat_json(messages=[{"role": "system", "content": EVALUATION_SYSTEM_PROMPT}, {"role": "user", "content": "输入 JSON：\n" + json.dumps(data, ensure_ascii=False)}], temperature=0.2, max_tokens=1200, purpose="answer_evaluation"))


async def _run_generate_question(context: dict, arguments: BaseModel) -> InterviewQuestion:
    GenerateQuestionArguments.model_validate(arguments)
    return await generate_main_question(context["request"], context["stage"], context["main_question_index"], context["answers"])


async def _run_evaluate_answer(context: dict, arguments: BaseModel) -> AnswerDecision:
    EvaluateAnswerArguments.model_validate(arguments)
    return await evaluate_answer(context["request"], context["latest_answer"])


RUNTIME_TOOLS.register(RuntimeTool(
    name="generate_interview_question",
    description="当面试需要开始或进入下一主阶段时，依据已确认简历、目标岗位、JD 与既往回答生成一道个性化主问题。不能用于分析当前回答。",
    input_model=GenerateQuestionArguments,
    handler=_run_generate_question,
))
RUNTIME_TOOLS.register(RuntimeTool(
    name="evaluate_interview_answer",
    description="当候选人已经回答当前问题且尚未触发确定性跳过规则时，判断回答是否充分，并返回追问或进入下一主问题的建议。不能用于生成新的主问题。",
    input_model=EvaluateAnswerArguments,
    handler=_run_evaluate_answer,
))

RUNTIME_SKILLS.register(RuntimeSkill(
    name="conduct_resume_interviews",
    description="依据用户已确认的简历、目标岗位、JD 与真实回答开展个性化模拟面试，判断回答充分性，进行有限追问并推进面试阶段。",
    instructions="""你正在执行“简历驱动动态面试”Skill。
- 开始面试时调用 generate_interview_question 生成第一道主问题。
- 收到回答时先调用 evaluate_interview_answer。
- 若结果为 follow_up，本轮信息已足够；若为 next_main 且仍有下一阶段，继续调用 generate_interview_question；若已完成全部阶段，本轮信息已足够。
- 每轮只返回一道问题。只能依据已确认简历、JD 和用户真实回答，不得编造事实。
- 阶段索引、追问次数和完成条件由程序控制，不得自行修改。""",
    tool_names=("generate_interview_question", "evaluate_interview_answer"),
    supported_events=("interview_started", "answer_submitted"),
    input_contract=(
        "resume_review_status 必须为 ai_verified，且包含用户已确认的简历章节",
        "目标岗位非空；面试轮次还必须包含当前问题和最新真实回答",
    ),
    output_contract=(
        "每轮只返回一道 InterviewQuestion，或在全部主阶段完成后返回 completed",
        "回答分析只产生 follow_up 或 next_main 决策、理由和可选薄弱项",
    ),
    fact_constraints=(
        "问题与判断只能依据已确认简历、JD 和用户提交的回答",
        "用户回答可补充简历未展开细节，但不得冒充简历原文",
        "不得编造经历、公司、项目、职责、数字、技能或证据",
    ),
    failure_policy=(
        "未确认简历、空回答、错误 JSON、非法 Tool 或状态冲突时安全失败",
        "用户明确不知道时记录证据不足并推进；达到两次追问上限时强制推进",
    ),
    acceptance_criteria=(
        "首题与已确认简历和目标岗位相关",
        "追问紧扣最新回答且单道主问题最多两次",
        "充分回答推进、未知回答不反复施压、最终结果可恢复且可追溯",
    ),
))
