from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryContext:
    user_id: str | None = None
    interview_id: str | None = None


_current_context: ContextVar[TelemetryContext] = ContextVar(
    "ai_interviewer_telemetry_context",
    default=TelemetryContext(),
)


def get_telemetry_context() -> TelemetryContext:
    return _current_context.get()


def set_telemetry_context(*, user_id: str | None, interview_id: str | None = None) -> Token[TelemetryContext]:
    return _current_context.set(TelemetryContext(user_id=user_id, interview_id=interview_id))


def reset_telemetry_context(token: Token[TelemetryContext]) -> None:
    _current_context.reset(token)
