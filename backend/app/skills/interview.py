from __future__ import annotations

import json
import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from ..ai_resume_reviewer import EMAIL_PATTERN, PHONE_PATTERN
from ..llm.deepseek import chat_json
from ..prompts.interview import EVALUATION_SYSTEM_PROMPT, QUESTION_SYSTEM_PROMPT
from ..presentation import clean_user_facing_text
from ..schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewTurnRequest, ResumeSection

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
