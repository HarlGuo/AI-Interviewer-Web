from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ..config import settings
from ..supabase_store import record_ai_usage
from ..telemetry_context import get_telemetry_context


class LLMNotConfiguredError(RuntimeError):
    pass


PURPOSE_OPERATIONS = {
    "resume review": "resume_review",
    "resume_review": "resume_review",
    "question_generation": "question_generation",
    "answer_evaluation": "answer_analysis",
    "answer_analysis": "answer_analysis",
    "resume_project_followup": "answer_analysis",
    "report": "report_generation",
    "report_generation": "report_generation",
}

# CloudBase Run has a hard 60-second request limit. A turn can invoke answer
# analysis and question generation sequentially, so each interactive model call
# must leave enough time for the second skill and for the API to return a
# structured error instead of an opaque gateway 503.
PURPOSE_READ_TIMEOUTS = {
    "question_generation": 22,
    "answer_evaluation": 22,
    "answer_analysis": 22,
    "resume_project_followup": 22,
    "resume review": 45,
    "resume_review": 45,
    "report": 50,
    "report_generation": 50,
}


async def chat_json(*, messages: list[dict[str, str]], temperature: float, max_tokens: int, purpose: str) -> dict[str, Any]:
    """DeepSeek JSON adapter. No agent or business decisions belong in this layer."""
    if not settings.deepseek_api_key:
        raise LLMNotConfiguredError("DEEPSEEK_API_KEY is not configured")
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response_data = await _send(
        payload,
        read_timeout=PURPOSE_READ_TIMEOUTS.get(purpose, 22),
        purpose=purpose,
        attempt_no=1,
    )
    try:
        content = response_data["choices"][0]["message"]["content"]
        parsed = json.loads(content) if content else None
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    raise RuntimeError(f"DeepSeek {purpose} returned invalid or malformed JSON")


async def _send(
    payload: dict[str, Any], *, read_timeout: float,
    purpose: str = "question_generation", attempt_no: int = 1,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(connect=15, read=read_timeout, write=30, pool=15)
    started = time.monotonic()
    context = get_telemetry_context()
    operation = PURPOSE_OPERATIONS.get(purpose, "question_generation")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{settings.deepseek_base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        usage = response_data.get("usage") if isinstance(response_data, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        choices = response_data.get("choices") if isinstance(response_data, dict) else None
        first_choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        response_id = response_data.get("id") if isinstance(response_data, dict) else None
        await record_ai_usage(
            user_id=context.user_id,
            interview_id=context.interview_id,
            operation=operation,
            attempt_no=attempt_no,
            request_id=response_id if isinstance(response_id, str) else None,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            prompt_cache_hit_tokens=usage.get("prompt_cache_hit_tokens"),
            prompt_cache_miss_tokens=usage.get("prompt_cache_miss_tokens"),
            latency_ms=round((time.monotonic() - started) * 1000),
            outcome="succeeded",
            http_status=response.status_code,
            finish_reason=first_choice.get("finish_reason") if isinstance(first_choice.get("finish_reason"), str) else None,
        )
        return response_data
    except Exception as error:
        status_code = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
        outcome = "timed_out" if isinstance(error, httpx.TimeoutException) else "failed"
        await record_ai_usage(
            user_id=context.user_id,
            interview_id=context.interview_id,
            operation=operation,
            attempt_no=attempt_no,
            request_id=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            prompt_cache_hit_tokens=None,
            prompt_cache_miss_tokens=None,
            latency_ms=round((time.monotonic() - started) * 1000),
            outcome=outcome,
            http_status=status_code,
            error_code=type(error).__name__,
        )
        raise
