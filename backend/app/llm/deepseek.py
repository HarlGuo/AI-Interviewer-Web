from __future__ import annotations

import json
from typing import Any

import httpx

from ..config import settings


class LLMNotConfiguredError(RuntimeError):
    pass


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
        response_data = await _send(payload, read_timeout=180 if purpose == "report" else 75)
        try:
            content = response_data["choices"][0]["message"]["content"]
            parsed = json.loads(content) if content else None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            parsed = None
            last_error = "invalid or malformed JSON"
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(f"DeepSeek {purpose} failed after one retry: {last_error}")


async def _send(payload: dict[str, Any], *, read_timeout: float) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(connect=15, read=read_timeout, write=30, pool=15)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{settings.deepseek_base_url}/chat/completions", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
