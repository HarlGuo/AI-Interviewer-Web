from __future__ import annotations

import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any

import httpx

from ..config import settings
from ..supabase_store import record_ai_usage
from ..telemetry_context import get_telemetry_context


class LLMNotConfiguredError(RuntimeError):
    pass


@dataclass
class ModelCallBudget:
    limit: int
    used: int = 0

    def consume(self) -> None:
        if self.used >= self.limit:
            raise RuntimeError(f"本轮模型 HTTP 调用超过最多 {self.limit} 次")
        self.used += 1


_MODEL_CALL_BUDGET: ContextVar[ModelCallBudget | None] = ContextVar("model_call_budget", default=None)


@contextmanager
def model_call_budget(limit: int) -> Iterator[ModelCallBudget]:
    """Count every real model HTTP attempt, including specialist retries."""
    budget = ModelCallBudget(limit=limit)
    token = _MODEL_CALL_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _MODEL_CALL_BUDGET.reset(token)


PURPOSE_OPERATIONS = {
    "resume review": "resume_review",
    "resume_review": "resume_review",
    "question_generation": "question_generation",
    "answer_evaluation": "answer_analysis",
    "answer_analysis": "answer_analysis",
    "skill_selection": "skill_selection",
    # The deployed analytics schema already groups planner calls under skill_selection.
    "agent_loop": "skill_selection",
    "report": "report_generation",
    "report_generation": "report_generation",
}


async def chat_with_tools(
    *, messages: list[dict[str, Any]], tools: list[dict[str, Any]], max_tokens: int = 1200,
) -> dict[str, Any]:
    """Run one non-thinking model step and return its assistant message, including tool calls."""
    if not settings.deepseek_api_key:
        raise LLMNotConfiguredError("DEEPSEEK_API_KEY is not configured")
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "thinking": {"type": "disabled"},
        "stream": False,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    response_data = await _send(payload, read_timeout=75, purpose="agent_loop", attempt_no=1)
    try:
        message = response_data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("DeepSeek agent loop returned a malformed message") from error
    if not isinstance(message, dict):
        raise RuntimeError("DeepSeek agent loop returned a malformed message")
    return message


async def chat_json(*, messages: list[dict[str, str]], temperature: float, max_tokens: int, purpose: str) -> dict[str, Any]:
    """DeepSeek JSON adapter. No agent or business decisions belong in this layer."""
    if not settings.deepseek_api_key:
        raise LLMNotConfiguredError("DEEPSEEK_API_KEY is not configured")
    last_error = "empty content"
    for attempt in range(2):
        payload = {
            "model": settings.deepseek_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens * (attempt + 1),
        }
        response_data = await _send(
            payload,
            read_timeout=180 if purpose == "report" else 75,
            purpose=purpose,
            attempt_no=attempt + 1,
        )
        try:
            content = response_data["choices"][0]["message"]["content"]
            parsed = json.loads(content) if content else None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            parsed = None
            last_error = "invalid or malformed JSON"
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(f"DeepSeek {purpose} failed after one retry: {last_error}")


async def _send(
    payload: dict[str, Any], *, read_timeout: float,
    purpose: str = "question_generation", attempt_no: int = 1,
) -> dict[str, Any]:
    budget = _MODEL_CALL_BUDGET.get()
    if budget is not None:
        budget.consume()
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
