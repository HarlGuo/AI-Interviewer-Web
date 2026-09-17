from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from .config import settings
from .schemas import (
    AnalyticsEventRequest,
    FeedbackRequest,
    InterviewAgentStartRequest,
    InterviewReport,
    InterviewStartResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers(*, prefer: str = "return=minimal") -> dict[str, str]:
    key = settings.supabase_secret_key or ""
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


async def _request(
    method: str,
    table: str,
    *,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    params: dict[str, str] | None = None,
    prefer: str = "return=minimal",
    timeout_seconds: float = 12,
) -> bool:
    if not settings.analytics_enabled:
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.request(
                method,
                f"{settings.supabase_url}/rest/v1/{table}",
                headers=_headers(prefer=prefer),
                params=params,
                json=payload,
            )
        if response.status_code >= 400:
            logger.warning("Supabase write failed table=%s status=%s", table, response.status_code)
            return False
        return True
    except httpx.HTTPError as error:
        logger.warning("Supabase write unavailable table=%s error=%s", table, type(error).__name__)
        return False


async def record_product_event(user_id: str, event: AnalyticsEventRequest) -> bool:
    row = {
        "event_id": str(event.event_id),
        "event_name": event.event_name,
        "user_id": user_id,
        "session_id": str(event.session_id),
        "interview_id": str(event.interview_id) if event.interview_id else None,
        "occurred_at": event.occurred_at.isoformat(),
        "page": event.page,
        "app_version": settings.app_version,
        "source": "client",
        "properties": event.properties,
    }
    return await _request("POST", "analytics_events", payload=row, prefer="resolution=ignore-duplicates,return=minimal")


async def record_server_event(
    *, user_id: str, session_id: str, event_name: str, interview_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> bool:
    return await _request("POST", "analytics_events", payload={
        "event_id": str(uuid4()),
        "event_name": event_name,
        "user_id": user_id,
        "session_id": session_id,
        "interview_id": interview_id,
        "occurred_at": _now(),
        "page": "backend",
        "app_version": settings.app_version,
        "source": "server",
        "properties": properties or {},
    })


async def upsert_attribution(user_id: str, event: AnalyticsEventRequest) -> bool:
    source = str(event.properties.get("utm_source") or "direct")[:80]
    medium = str(event.properties.get("utm_medium") or "none")[:80]
    campaign = str(event.properties.get("utm_campaign") or "none")[:120]
    content = str(event.properties.get("utm_content") or "none")[:120]
    return await _request(
        "POST",
        "acquisition_attributions",
        params={"on_conflict": "user_id"},
        prefer="resolution=ignore-duplicates,return=minimal",
        payload={
            "user_id": user_id,
            "landing_session_id": str(event.session_id),
            "utm_source": source,
            "utm_medium": medium,
            "utm_campaign": campaign,
            "utm_content": content,
            "first_landed_at": event.occurred_at.isoformat(),
        },
    )


async def record_interview_start(
    user_id: str,
    request: InterviewAgentStartRequest,
    result: InterviewStartResponse,
) -> bool:
    interview_id = result.interview_id
    interview_saved = await _request("POST", "interviews", params={"on_conflict": "id"}, prefer="resolution=merge-duplicates,return=minimal", payload={
        "id": interview_id,
        "user_id": user_id,
        "resume_id": str(request.resume_id) if request.resume_id else None,
        "mode": request.mode,
        "focus": request.focus,
        "status": "active",
        "target_title_snapshot": request.target_role,
        "job_description_snapshot": request.job_description,
        "total_main_questions": result.total_main_questions,
        "started_at": _now(),
        "app_version": settings.app_version,
        "agent_version": settings.agent_version,
        "prompt_version": settings.prompt_version,
        "skill_version": settings.skill_version,
    })
    question_saved = await _request("POST", "interview_questions", payload=_question_row(
        user_id=user_id,
        interview_id=interview_id,
        question=result.question.model_dump(),
        sequence_no=1,
    ))
    return interview_saved and question_saved


async def record_interview_draft(user_id: str, interview_id: str, request: InterviewAgentStartRequest) -> bool:
    """Create the parent row before the first LLM call so usage can reference it."""
    return await _request("POST", "interviews", payload={
        "id": interview_id,
        "user_id": user_id,
        "resume_id": str(request.resume_id) if request.resume_id else None,
        "mode": request.mode,
        "focus": request.focus,
        "status": "draft",
        "target_title_snapshot": request.target_role,
        "job_description_snapshot": request.job_description,
        "total_main_questions": 0,
        "app_version": settings.app_version,
        "agent_version": settings.agent_version,
        "prompt_version": settings.prompt_version,
        "skill_version": settings.skill_version,
    })


def _question_row(*, user_id: str, interview_id: str, question: dict[str, Any], sequence_no: int) -> dict[str, Any]:
    return {
        "id": question["id"],
        "user_id": user_id,
        "interview_id": interview_id,
        "external_question_id": question["id"],
        "sequence_no": sequence_no,
        "stage": question["stage"],
        "question_text": question["text"],
        "is_follow_up": question.get("is_follow_up", False),
        "main_question_index": question.get("main_question_index", 0),
        "follow_up_count": question.get("follow_up_count", 0),
        "resume_evidence": question.get("resume_evidence", ""),
    }


async def record_interview_turn(
    user_id: str,
    request: InterviewTurnRequest,
    result: InterviewTurnResponse,
) -> None:
    latest = request.answers[-1]
    answer_row = {
        "id": str(uuid4()),
        "user_id": user_id,
        "interview_id": request.interview_id,
        "question_id": latest.question_id,
        "answer_text": latest.answer,
        "source": latest.source,
        "delivery_metrics": latest.delivery_metrics.model_dump() if latest.delivery_metrics else {},
        "confirmed_by_user": True,
        "submitted_at": _now(),
    }
    answer_saved = await _request(
        "POST", "interview_answers",
        params={"on_conflict": "question_id"},
        prefer="resolution=merge-duplicates,return=minimal",
        payload=answer_row,
    )
    if not answer_saved and latest.delivery_metrics:
        # Keep answer persistence compatible while a deployment and its database migration roll out.
        answer_row.pop("delivery_metrics", None)
        await _request(
            "POST", "interview_answers",
            params={"on_conflict": "question_id"},
            prefer="resolution=merge-duplicates,return=minimal",
            payload=answer_row,
        )
    if result.next_question:
        await _request("POST", "interview_questions", payload=_question_row(
            user_id=user_id,
            interview_id=request.interview_id,
            question=result.next_question.model_dump(),
            sequence_no=len(request.answers) + 1,
        ))
    await update_interview_status(
        user_id,
        request.interview_id,
        "completed" if result.completed else "active",
    )


async def update_interview_status(user_id: str, interview_id: str, status: str) -> bool:
    payload: dict[str, Any] = {"status": status}
    if status in {"completed", "ended-early"}:
        payload["completed_at"] = _now()
    return await _request(
        "PATCH", "interviews", payload=payload,
        params={"id": f"eq.{interview_id}", "user_id": f"eq.{user_id}"},
    )


async def record_report(user_id: str, interview_id: str, report: InterviewReport) -> bool:
    return await _request(
        "POST", "interview_reports",
        params={"on_conflict": "interview_id"},
        prefer="resolution=merge-duplicates,return=minimal",
        payload={
            "user_id": user_id,
            "interview_id": interview_id,
            "status": "completed",
            "report_data": report.model_dump(),
            "model_name": settings.deepseek_model,
            "rubric_version": settings.rubric_version,
            "generated_at": _now(),
        },
    )


async def record_feedback(user_id: str, interview_id: str, feedback: FeedbackRequest) -> bool:
    return await _request(
        "POST", "feedback_responses",
        params={"on_conflict": "interview_id"},
        prefer="resolution=merge-duplicates,return=minimal",
        payload={
            "interview_id": interview_id,
            "user_id": user_id,
            "satisfaction_score": feedback.satisfaction_score,
            "payment_willingness": feedback.payment_willingness,
            "tags": feedback.tags,
            "comment": feedback.comment,
            "completion_type": feedback.completion_type,
            "app_version": settings.app_version,
            "agent_version": settings.agent_version,
            "submitted_at": _now(),
        },
    )


async def record_ai_usage(
    *, user_id: str | None, interview_id: str | None, operation: str, attempt_no: int,
    request_id: str | None, prompt_tokens: int | None, completion_tokens: int | None,
    total_tokens: int | None, prompt_cache_hit_tokens: int | None,
    prompt_cache_miss_tokens: int | None, latency_ms: int, outcome: str,
    http_status: int | None = None, finish_reason: str | None = None,
    error_code: str | None = None,
) -> bool:
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return False
    return await _request("POST", "ai_usage_events", timeout_seconds=3, payload={
        "event_id": str(uuid4()),
        "user_id": user_id,
        "interview_id": interview_id,
        "operation": operation,
        "provider": "deepseek",
        "model_name": settings.deepseek_model,
        "request_id": request_id,
        "attempt_no": attempt_no,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_cache_hit_tokens": prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": prompt_cache_miss_tokens,
        "latency_ms": latency_ms,
        "outcome": outcome,
        "error_code": error_code,
        "http_status": http_status,
        "finish_reason": finish_reason,
        "app_version": settings.app_version,
        "agent_version": settings.agent_version,
        "prompt_version": settings.prompt_version,
        "skill_version": settings.skill_version,
        "rubric_version": settings.rubric_version,
    })
