from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ...agent_runtime import AgentDescriptor
from ...runtime_skills.answer_evaluation import AnswerDecision
from ...schemas import InterviewTurnRequest


UNKNOWN_ANSWER = re.compile(r"^(不知道|不清楚|不会|不了解|没有(?:相关)?经历|暂时没有|想不起来)[。.!！\s]*$")


class StageDefinition(BaseModel):
    key: str
    label: str


class InterviewerConfiguration(BaseModel):
    max_follow_ups: int = Field(ge=0, le=2)
    focused_main_questions: int = Field(ge=1, le=10)
    formal_stages: list[StageDefinition] = Field(min_length=1)
    skill_bindings: dict[str, str]

    @model_validator(mode="after")
    def validate_configuration(self) -> "InterviewerConfiguration":
        keys = [stage.key for stage in self.formal_stages]
        if len(keys) != len(set(keys)):
            raise ValueError("Agent 阶段 key 不能重复")
        required = {"resume_context", "question_generation", "answer_evaluation", "report_generation"}
        if set(self.skill_bindings) != required:
            raise ValueError("Agent skill_bindings 不完整")
        return self


class InterviewerPolicy:
    """Deterministic safety and progression rules owned by the agent."""

    def __init__(self, descriptor: AgentDescriptor) -> None:
        self.configuration = InterviewerConfiguration.model_validate(descriptor.configuration)
        self._labels = {stage.key: stage.label for stage in self.configuration.formal_stages}

    @property
    def max_follow_ups(self) -> int:
        return self.configuration.max_follow_ups

    def skill(self, capability: str) -> str:
        return self.configuration.skill_bindings[capability]

    def stage_plan(self, mode: str, focus: str | None) -> list[str]:
        if mode == "focused":
            stage = focus or self.configuration.formal_stages[0].key
            if stage not in self._labels:
                raise ValueError(f"Agent 不支持该专项阶段：{stage}")
            return [stage] * self.configuration.focused_main_questions
        return [stage.key for stage in self.configuration.formal_stages]

    def label(self, stage: str) -> str:
        try:
            return self._labels[stage]
        except KeyError as error:
            raise ValueError(f"Agent 计划包含未定义阶段：{stage}") from error

    def validate_turn(self, request: InterviewTurnRequest, plan: list[str]) -> str:
        current = request.current_question
        if current.main_question_index >= len(plan) or current.stage != self.label(plan[current.main_question_index]):
            raise ValueError("当前问题与 Agent 面试计划不一致")
        answer = request.answers[-1].answer.strip() if request.answers else ""
        if not answer:
            raise ValueError("缺少当前问题的回答")
        return answer

    def deterministic_decision(self, request: InterviewTurnRequest, latest_answer: str) -> AnswerDecision | None:
        current = request.current_question
        if current.follow_up_count >= self.max_follow_ups:
            return AnswerDecision(
                action="next_main",
                reason=f"已达到单道主问题最多 {self.max_follow_ups} 次追问限制，进入下一阶段。",
                weakness="当前主问题已完成规定的追问次数",
            )
        if UNKNOWN_ANSWER.fullmatch(latest_answer):
            return AnswerDecision(
                action="next_main",
                reason="用户明确表示不知道或没有相关经历",
                weakness="当前问题缺少可用回答证据",
            )
        return None

    def validate_registered_skills(self, registered_names: set[str], descriptor_skills: list[str]) -> None:
        declared = set(descriptor_skills)
        bound = set(self.configuration.skill_bindings.values())
        if bound - declared:
            raise ValueError(f"Agent 绑定了未声明的 Skill：{sorted(bound - declared)}")
        if declared - registered_names:
            raise ValueError(f"Agent 声明的 Skill 未注册：{sorted(declared - registered_names)}")


def append_trace(current: list[dict[str, Any]] | None, *, descriptor: Any) -> list[dict[str, Any]]:
    return [
        *(current or []),
        {
            "skill": descriptor.name,
            "version": descriptor.version,
            "input_contract": descriptor.input_schema,
            "output_contract": descriptor.output_schema,
        },
    ]
