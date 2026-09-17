from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from ...agent_runtime import AgentDescriptor, SkillRegistry, load_agent_descriptor
from ...runtime_skills.answer_evaluation import AnswerDecision, AnswerEvaluationInput
from ...runtime_skills.question_generation import PreviousAnswer, QuestionGenerationInput
from ...runtime_skills.report_generation import ReportGenerationInput
from ...runtime_skills.resume_context import ResumeContextInput
from ...schemas import (
    InterviewAgentStartRequest,
    InterviewQuestion,
    InterviewReport,
    InterviewStartResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
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
        registered = {item.name for item in registry.catalog()}
        self.policy.validate_registered_skills(registered, self.descriptor.skills)
        self.start_graph = self._compile_start_graph()
        self.turn_graph = self._compile_turn_graph()
        self.report_graph = self._compile_report_graph()

    @property
    def tools(self) -> list[BaseTool]:
        """Typed LangChain tools exposed by the skills declared in AGENT.md."""
        return self.registry.tools(self.descriptor.skills)

    async def _prepare_start(self, state: StartState) -> dict:
        request = state["request"]
        return {"plan": self.policy.stage_plan(request.mode, request.focus), "skill_trace": []}

    async def _prepare_start_resume(self, state: StartState) -> dict:
        name = self.policy.skill("resume_context")
        skill = self.registry.require(name)
        result = await skill.invoke(ResumeContextInput(
            sections=state["request"].resume_sections,
        ))
        return {"resume_context": result, "skill_trace": append_trace(state.get("skill_trace"), descriptor=skill.descriptor)}

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
        name = self.policy.skill("resume_context")
        skill = self.registry.require(name)
        result = await skill.invoke(ResumeContextInput(
            sections=state["request"].resume_sections,
        ))
        return {"resume_context": result, "skill_trace": append_trace(state.get("skill_trace"), descriptor=skill.descriptor)}

    async def _evaluate_turn(self, state: TurnState) -> dict:
        request = state["request"]
        decision = self.policy.deterministic_decision(request, state["latest_answer"])
        if decision is not None:
            return {"decision": decision}
        name = self.policy.skill("answer_evaluation")
        skill = self.registry.require(name)
        result = await skill.invoke(AnswerEvaluationInput(
            target_role=request.target_role,
            job_description=request.job_description,
            confirmed_resume=state["resume_context"].sections,
            current_question=request.current_question,
            latest_answer=state["latest_answer"],
            previous_answers=request.answers[-11:-1],
            remaining_follow_ups=self.policy.max_follow_ups - request.current_question.follow_up_count,
        ))
        return {"decision": result, "skill_trace": append_trace(state.get("skill_trace"), descriptor=skill.descriptor)}

    def _route_decision(self, state: TurnState) -> Literal["follow_up", "advance_main"]:
        current = state["request"].current_question
        return "follow_up" if state["decision"].action == "follow_up" and current.follow_up_count < self.policy.max_follow_ups else "advance_main"

    async def _build_follow_up(self, state: TurnState) -> dict:
        request, decision = state["request"], state["decision"]
        if not decision.question.strip():
            raise ValueError("追问决策缺少问题")
        current = request.current_question
        question = InterviewQuestion(
            id=str(uuid4()),
            stage=self.policy.label(state["plan"][current.main_question_index]),
            text=decision.question.strip(),
            is_follow_up=True,
            main_question_index=current.main_question_index,
            follow_up_count=current.follow_up_count + 1,
            resume_evidence="",
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
        question, trace = await self._invoke_question_skill(
            request=request,
            stage=state["plan"][index],
            index=index,
            answers=request.answers,
            resume_context=state["resume_context"],
            trace=state.get("skill_trace"),
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
                                     answers: list, resume_context, trace: list | None) -> tuple[InterviewQuestion, list]:
        name = self.policy.skill("question_generation")
        skill = self.registry.require(name)
        generated = await skill.invoke(QuestionGenerationInput(
            stage=stage,
            stage_label=self.policy.label(stage),
            main_question_number=index + 1,
            target_role=request.target_role,
            job_description=request.job_description,
            confirmed_resume=resume_context.sections,
            previous_answers=[PreviousAnswer(question=item.question[:1000], answer=item.answer[:4000]) for item in answers[-6:]],
            searchable_resume_text=resume_context.searchable_text,
        ))
        question = InterviewQuestion(
            id=str(uuid4()),
            stage=self.policy.label(stage),
            text=generated.question,
            is_follow_up=False,
            main_question_index=index,
            follow_up_count=0,
            resume_evidence=generated.resume_evidence,
        )
        return question, append_trace(trace, descriptor=skill.descriptor)

    async def _generate_report(self, state: ReportState) -> dict:
        name = self.policy.skill("report_generation")
        skill = self.registry.require(name)
        report = await skill.invoke(ReportGenerationInput.model_validate(state["request"].model_dump()))
        return {"report": report, "skill_trace": append_trace([], descriptor=skill.descriptor)}

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
