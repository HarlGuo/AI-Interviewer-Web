from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import uuid4

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from ...agent_runtime import AgentDescriptor, SkillRegistry, SkillSelector, load_agent_descriptor
from ...runtime_skills.answer_evaluation import AnswerDecision, AnswerEvaluationInput
from ...runtime_skills.question_generation import GeneratedQuestion, PreviousAnswer, QuestionGenerationInput
from ...runtime_skills.report_generation import ReportGenerationInput
from ...runtime_skills.resume_context import ResumeContextInput, ResumeContextOutput
from ...runtime_skills.resume_project_followup import ResumeProjectFollowUpDecision, ResumeProjectFollowUpInput
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
from .policy import InterviewerPolicy, append_trace
from .state import ReportState, StartState, TurnState


class InterviewerAgent:
    """Modular LangGraph agent whose capabilities are resolved through a skill registry."""

    def __init__(self, registry: SkillRegistry, descriptor_path: Path | None = None) -> None:
        self.descriptor: AgentDescriptor = load_agent_descriptor(descriptor_path or Path(__file__).with_name("AGENT.md"))
        self.registry = registry
        self.policy = InterviewerPolicy(self.descriptor)
        self.selector = SkillSelector(registry, self.descriptor.skills)
        registered = {item.name for item in registry.catalog()}
        self.policy.validate_registered_skills(registered, self.descriptor.skills)
        self.start_graph = self._compile_start_graph()
        self.turn_graph = self._compile_turn_graph()
        self.report_graph = self._compile_report_graph()

    @property
    def tools(self) -> list[BaseTool]:
        """Typed LangChain tools exposed by the skills declared in AGENT.md."""
        return self.registry.tools(self.descriptor.skills)

    async def _select_skill(self, *, objective: str, context: dict) -> tuple:
        selection = await self.selector.select(objective=objective, context=context)
        return self.registry.require(selection.skill_name), selection

    async def _prepare_start(self, state: StartState) -> dict:
        request = state["request"]
        return {"plan": self.policy.stage_plan(request.mode, request.focus), "skill_trace": []}

    async def _prepare_start_resume(self, state: StartState) -> dict:
        skill, selection = await self._select_skill(
            objective="将用户已确认的简历转换为隐私安全、可用于面试的上下文",
            context={"phase": "start", "has_confirmed_resume": True},
        )
        result = await skill.invoke(ResumeContextInput(
            sections=state["request"].resume_sections,
        ))
        if not isinstance(result, ResumeContextOutput):
            raise ValueError(f"Agent 为简历上下文选择了不适用的 Skill：{skill.descriptor.name}")
        return {"resume_context": result, "skill_trace": append_trace(state.get("skill_trace"), descriptor=skill.descriptor, selection_reason=selection.reason)}

    async def _generate_start_question(self, state: StartState) -> dict:
        request, stage = state["request"], state["plan"][0]
        question, trace = await self._invoke_question_skill(
            request=request,
            stage=stage,
            index=0,
            answers=[],
            resume_context=state["resume_context"],
            trace=state.get("skill_trace"),
        )
        response = InterviewStartResponse(
            interview_id=state["interview_id"],
            question=question,
            total_main_questions=len(state["plan"]),
        )
        return {"question": question, "response": response, "skill_trace": trace}

    async def _validate_turn(self, state: TurnState) -> dict:
        request = state["request"]
        plan = self.policy.stage_plan(request.mode, request.focus)
        return {"plan": plan, "latest_answer": self.policy.validate_turn(request, plan), "skill_trace": []}

    async def _prepare_turn_resume(self, state: TurnState) -> dict:
        skill, selection = await self._select_skill(
            objective="为当前面试轮次准备隐私安全的已确认简历上下文",
            context={"phase": "turn", "has_confirmed_resume": True},
        )
        result = await skill.invoke(ResumeContextInput(
            sections=state["request"].resume_sections,
        ))
        if not isinstance(result, ResumeContextOutput):
            raise ValueError(f"Agent 为简历上下文选择了不适用的 Skill：{skill.descriptor.name}")
        return {"resume_context": result, "skill_trace": append_trace(state.get("skill_trace"), descriptor=skill.descriptor, selection_reason=selection.reason)}

    async def _evaluate_turn(self, state: TurnState) -> dict:
        request = state["request"]
        current = request.current_question
        stage = state["plan"][current.main_question_index]
        if stage == "resume-deep-dive" and current.project_context is not None:
            return await self._evaluate_resume_project(state)
        decision = self.policy.deterministic_decision(request, state["latest_answer"])
        if decision is not None:
            return {"decision": decision}
        skill, selection = await self._select_skill(
            objective="判断候选人的最新回答是否充分，并决定追问或进入下一主问题",
            context={"phase": "answer_received", "stage": stage, "has_project_context": False,
                     "follow_up_count": current.follow_up_count},
        )
        result = await skill.invoke(AnswerEvaluationInput(
            target_role=request.target_role,
            job_description=request.job_description,
            confirmed_resume=state["resume_context"].sections,
            current_question=request.current_question,
            latest_answer=state["latest_answer"],
            previous_answers=request.answers[-11:-1],
            remaining_follow_ups=self.policy.max_follow_ups - request.current_question.follow_up_count,
        ))
        if not isinstance(result, AnswerDecision):
            raise ValueError(f"Agent 为回答评估选择了不适用的 Skill：{skill.descriptor.name}")
        return {"decision": result, "skill_trace": append_trace(state.get("skill_trace"), descriptor=skill.descriptor, selection_reason=selection.reason)}

    async def _evaluate_resume_project(self, state: TurnState) -> dict:
        request = state["request"]
        current = request.current_question
        context = current.project_context
        if context is None:
            raise ValueError("简历项目追问缺少项目上下文")
        fixed = self.policy.project_stop_decision(request, state["latest_answer"])
        if fixed is not None:
            return {"decision": fixed, "project_context": context}
        question_ids = set(context.question_ids)
        project_answers = [item for item in request.answers if item.question_id in question_ids]
        skill, selection = await self._select_skill(
            objective="围绕当前已绑定的简历项目证据判断覆盖情况并决定是否继续深挖",
            context={"phase": "resume_project_followup", "stage": "resume-deep-dive",
                     "follow_up_count": current.follow_up_count, "project_round_count": context.round_count},
        )
        project_decision = await skill.invoke(ResumeProjectFollowUpInput(
            target_role=request.target_role,
            project_key=context.project_key,
            project_resume_evidence=context.project_resume_evidence,
            latest_answer=state["latest_answer"],
            project_answers=project_answers,
            coverage=context.coverage,
            follow_up_count=current.follow_up_count,
            project_round_count=context.round_count,
            consecutive_insufficient_count=context.consecutive_insufficient_count,
        ))
        if not isinstance(project_decision, ResumeProjectFollowUpDecision):
            raise ValueError(f"Agent 为项目深挖选择了不适用的 Skill：{skill.descriptor.name}")
        coverage_updates = {item.target: "covered" for item in project_decision.newly_covered_targets}
        coverage = context.coverage.model_copy(update=coverage_updates)
        insufficient_count = (
            min(2, context.consecutive_insufficient_count + 1)
            if project_decision.information_quality == "insufficient"
            else 0
        )
        updated_context = context.model_copy(update={
            "coverage": coverage,
            "consecutive_insufficient_count": insufficient_count,
        })
        all_covered = all(value == "covered" for value in coverage.model_dump().values())
        must_switch = (
            all_covered
            or insufficient_count >= 2
            or project_decision.information_quality == "not_responsible"
            or project_decision.action != "follow_up"
        )
        decision = AnswerDecision(
            action="next_main" if must_switch else "follow_up",
            question="" if must_switch else project_decision.question,
            reason=(
                "当前项目的主要考察目标已覆盖，切换主题。"
                if all_covered
                else "候选人连续两次未提供有效信息，切换主题。"
                if insufficient_count >= 2
                else project_decision.reason
            ),
            weakness=project_decision.weakness,
        )
        return {
            "decision": decision,
            "project_context": updated_context,
            "skill_trace": append_trace(state.get("skill_trace"), descriptor=skill.descriptor, selection_reason=selection.reason),
        }

    def _route_decision(self, state: TurnState) -> Literal["follow_up", "advance_main"]:
        current = state["request"].current_question
        return "follow_up" if state["decision"].action == "follow_up" and current.follow_up_count < self.policy.max_follow_ups else "advance_main"

    async def _build_follow_up(self, state: TurnState) -> dict:
        request, decision = state["request"], state["decision"]
        if not decision.question.strip():
            raise ValueError("追问决策缺少问题")
        current = request.current_question
        project_context = state.get("project_context")
        question_id = str(uuid4())
        if project_context is not None:
            project_context = project_context.model_copy(update={
                "round_count": project_context.round_count + 1,
                "question_ids": [*project_context.question_ids, question_id],
            })
        question = InterviewQuestion(
            id=question_id,
            stage=self.policy.label(state["plan"][current.main_question_index]),
            text=decision.question.strip(),
            is_follow_up=True,
            main_question_index=current.main_question_index,
            follow_up_count=current.follow_up_count + 1,
            resume_evidence="",
            project_context=project_context,
        )
        return {"response": InterviewTurnResponse(
            next_question=question,
            completed=False,
            decision_reason=decision.reason,
            weakness=decision.weakness,
            total_main_questions=len(state["plan"]),
        )}

    async def _advance_main(self, state: TurnState) -> dict:
        next_index = state["request"].current_question.main_question_index + 1
        if next_index >= len(state["plan"]):
            decision = state["decision"]
            return {"response": InterviewTurnResponse(
                next_question=None,
                completed=True,
                decision_reason=decision.reason,
                weakness=decision.weakness,
                total_main_questions=len(state["plan"]),
            )}
        return {"next_main_index": next_index}

    def _route_advance(self, state: TurnState) -> Literal["generate_next_question", "complete"]:
        return "complete" if "response" in state else "generate_next_question"

    async def _generate_next_question(self, state: TurnState) -> dict:
        request, index = state["request"], state["next_main_index"]
        current_context = request.current_question.project_context
        excluded_evidence = current_context.visited_project_evidence if current_context is not None else []
        question, trace = await self._invoke_question_skill(
            request=request,
            stage=state["plan"][index],
            index=index,
            answers=request.answers,
            resume_context=state["resume_context"],
            trace=state.get("skill_trace"),
            excluded_resume_evidence=excluded_evidence,
        )
        decision = state["decision"]
        return {
            "response": InterviewTurnResponse(
                next_question=question,
                completed=False,
                decision_reason=decision.reason,
                weakness=decision.weakness,
                total_main_questions=len(state["plan"]),
            ),
            "skill_trace": trace,
        }

    async def _invoke_question_skill(self, *, request: InterviewAgentStartRequest, stage: str, index: int,
                                     answers: list, resume_context, trace: list | None,
                                     excluded_resume_evidence: list[str] | None = None) -> tuple[InterviewQuestion, list]:
        skill, selection = await self._select_skill(
            objective="为指定面试阶段生成一道个性化主问题",
            context={"phase": "question_generation", "stage": stage, "main_question_index": index,
                     "previous_answer_count": len(answers)},
        )
        generated = await skill.invoke(QuestionGenerationInput(
            stage=stage,
            stage_label=self.policy.label(stage),
            main_question_number=index + 1,
            target_role=request.target_role,
            job_description=request.job_description,
            confirmed_resume=resume_context.sections,
            previous_answers=[PreviousAnswer(question=item.question[:1000], answer=item.answer[:4000]) for item in answers[-6:]],
            searchable_resume_text=resume_context.searchable_text,
            excluded_resume_evidence=excluded_resume_evidence or [],
        ))
        if not isinstance(generated, GeneratedQuestion):
            raise ValueError(f"Agent 为问题生成选择了不适用的 Skill：{skill.descriptor.name}")
        question_id = str(uuid4())
        visited_evidence = list(dict.fromkeys([*(excluded_resume_evidence or []), generated.resume_evidence]))
        project_context = None
        if stage == "resume-deep-dive" and generated.resume_evidence:
            project_context = ProjectInterviewContext(
                project_key=sha256(generated.resume_evidence.encode("utf-8")).hexdigest()[:16],
                project_resume_evidence=generated.resume_evidence,
                question_ids=[question_id],
                visited_project_evidence=visited_evidence,
            )
        question = InterviewQuestion(
            id=question_id,
            stage=self.policy.label(stage),
            text=generated.question,
            is_follow_up=False,
            main_question_index=index,
            follow_up_count=0,
            resume_evidence=generated.resume_evidence,
            project_context=project_context,
        )
        return question, append_trace(trace, descriptor=skill.descriptor, selection_reason=selection.reason)

    async def _generate_report(self, state: ReportState) -> dict:
        skill, selection = await self._select_skill(
            objective="根据已完成面试的真实回答生成证据型复盘报告",
            context={"phase": "report", "completed": state["request"].completed,
                     "answer_count": len(state["request"].answers)},
        )
        report = await skill.invoke(ReportGenerationInput.model_validate(state["request"].model_dump()))
        if not isinstance(report, InterviewReport):
            raise ValueError(f"Agent 为报告生成选择了不适用的 Skill：{skill.descriptor.name}")
        return {"report": report, "skill_trace": append_trace([], descriptor=skill.descriptor, selection_reason=selection.reason)}

    def _compile_start_graph(self):
        graph = StateGraph(StartState)
        graph.add_node("prepare_interview_plan", self._prepare_start)
        graph.add_node("prepare_resume_context", self._prepare_start_resume)
        graph.add_node("generate_first_question", self._generate_start_question)
        graph.add_edge(START, "prepare_interview_plan")
        graph.add_edge("prepare_interview_plan", "prepare_resume_context")
        graph.add_edge("prepare_resume_context", "generate_first_question")
        graph.add_edge("generate_first_question", END)
        return graph.compile()

    def _compile_turn_graph(self):
        graph = StateGraph(TurnState)
        graph.add_node("validate_turn", self._validate_turn)
        graph.add_node("prepare_resume_context", self._prepare_turn_resume)
        graph.add_node("evaluate_answer", self._evaluate_turn)
        graph.add_node("build_follow_up", self._build_follow_up)
        graph.add_node("advance_main_question", self._advance_main)
        graph.add_node("generate_next_question", self._generate_next_question)
        graph.add_edge(START, "validate_turn")
        graph.add_edge("validate_turn", "prepare_resume_context")
        graph.add_edge("prepare_resume_context", "evaluate_answer")
        graph.add_conditional_edges("evaluate_answer", self._route_decision, {
            "follow_up": "build_follow_up",
            "advance_main": "advance_main_question",
        })
        graph.add_edge("build_follow_up", END)
        graph.add_conditional_edges("advance_main_question", self._route_advance, {
            "generate_next_question": "generate_next_question",
            "complete": END,
        })
        graph.add_edge("generate_next_question", END)
        return graph.compile()

    def _compile_report_graph(self):
        graph = StateGraph(ReportState)
        graph.add_node("generate_evidence_report", self._generate_report)
        graph.add_edge(START, "generate_evidence_report")
        graph.add_edge("generate_evidence_report", END)
        return graph.compile()

    async def start(self, request: InterviewAgentStartRequest, *, interview_id: str | None = None) -> InterviewStartResponse:
        state = await self.start_graph.ainvoke({"request": request, "interview_id": interview_id or str(uuid4())})
        return state["response"]

    async def advance(self, request: InterviewTurnRequest) -> InterviewTurnResponse:
        state = await self.turn_graph.ainvoke({"request": request})
        return state["response"]

    async def report(self, request: ReportRequest) -> InterviewReport:
        state = await self.report_graph.ainvoke({"request": request})
        return state["report"]
