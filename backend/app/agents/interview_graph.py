from __future__ import annotations

from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from ..schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewStartResponse, InterviewTurnRequest, InterviewTurnResponse
from ..skills.interview import MAX_FOLLOW_UPS, STAGE_LABELS, AnswerDecision, evaluate_answer, generate_main_question, stage_plan, validate_turn


class StartState(TypedDict, total=False):
    request: InterviewAgentStartRequest
    plan: list[str]
    question: InterviewQuestion


class TurnState(TypedDict, total=False):
    request: InterviewTurnRequest
    plan: list[str]
    latest_answer: str
    decision: AnswerDecision
    response: InterviewTurnResponse


async def _prepare_start(state: StartState) -> dict:
    return {"plan": stage_plan(state["request"].mode, state["request"].focus)}


async def _generate_first_question(state: StartState) -> dict:
    return {"question": await generate_main_question(state["request"], state["plan"][0], 0, [])}


async def _validate_turn(state: TurnState) -> dict:
    plan = stage_plan(state["request"].mode, state["request"].focus)
    return {"plan": plan, "latest_answer": validate_turn(state["request"], plan)}


async def _evaluate_turn(state: TurnState) -> dict:
    return {"decision": await evaluate_answer(state["request"], state["latest_answer"])}


def _route_decision(state: TurnState) -> Literal["follow_up", "advance_main"]:
    current = state["request"].current_question
    return "follow_up" if state["decision"].action == "follow_up" and current.follow_up_count < MAX_FOLLOW_UPS else "advance_main"


async def _build_follow_up(state: TurnState) -> dict:
    request, decision = state["request"], state["decision"]
    if not decision.question.strip():
        raise ValueError("追问决策缺少问题")
    current = request.current_question
    question = InterviewQuestion(id=str(uuid4()), stage=STAGE_LABELS[state["plan"][current.main_question_index]], text=decision.question.strip(),
                                 is_follow_up=True, main_question_index=current.main_question_index, follow_up_count=current.follow_up_count + 1, resume_evidence="")
    return {"response": InterviewTurnResponse(next_question=question, completed=False, decision_reason=decision.reason, weakness=decision.weakness, total_main_questions=len(state["plan"]))}


async def _advance_main(state: TurnState) -> dict:
    request, decision, plan = state["request"], state["decision"], state["plan"]
    next_index = request.current_question.main_question_index + 1
    if next_index >= len(plan):
        return {"response": InterviewTurnResponse(next_question=None, completed=True, decision_reason=decision.reason, weakness=decision.weakness, total_main_questions=len(plan))}
    question = await generate_main_question(request, plan[next_index], next_index, request.answers)
    return {"response": InterviewTurnResponse(next_question=question, completed=False, decision_reason=decision.reason, weakness=decision.weakness, total_main_questions=len(plan))}


def _compile_start_graph():
    graph = StateGraph(StartState)
    graph.add_edge(START, "prepare")
    graph.add_node("prepare", _prepare_start)
    graph.add_node("generate_first_question", _generate_first_question)
    graph.add_edge("prepare", "generate_first_question")
    graph.add_edge("generate_first_question", END)
    return graph.compile()


def _compile_turn_graph():
    graph = StateGraph(TurnState)
    graph.add_node("validate", _validate_turn)
    graph.add_node("evaluate", _evaluate_turn)
    graph.add_node("follow_up", _build_follow_up)
    graph.add_node("advance_main", _advance_main)
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "evaluate")
    graph.add_conditional_edges("evaluate", _route_decision)
    graph.add_edge("follow_up", END)
    graph.add_edge("advance_main", END)
    return graph.compile()


START_GRAPH = _compile_start_graph()
TURN_GRAPH = _compile_turn_graph()


async def start_interview(request: InterviewAgentStartRequest, *, interview_id: str | None = None) -> InterviewStartResponse:
    state = await START_GRAPH.ainvoke({"request": request})
    return InterviewStartResponse(interview_id=interview_id or str(uuid4()), question=state["question"], total_main_questions=len(state["plan"]))


async def advance_interview(request: InterviewTurnRequest) -> InterviewTurnResponse:
    state = await TURN_GRAPH.ainvoke({"request": request})
    return state["response"]
