"""Compatibility entrypoint for the report API.

The report behavior belongs to the registered report_generation runtime skill.
"""

from __future__ import annotations

from .agents.interviewer import interviewer_agent
from .config import settings
from .schemas import InterviewReport, ReportRequest


class DeepSeekNotConfiguredError(RuntimeError):
    pass


async def generate_report(request: ReportRequest) -> InterviewReport:
    if not settings.deepseek_api_key:
        raise DeepSeekNotConfiguredError("DEEPSEEK_API_KEY is not configured")
    return await interviewer_agent.report(request)
