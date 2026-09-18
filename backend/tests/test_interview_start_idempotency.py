from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app import main
from app.auth import CurrentUser
from app.schemas import InterviewAgentStartRequest, InterviewQuestion, InterviewStartResponse, ResumeSection
from app.supabase_store import load_interview_start


USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="tester@example.com", access_token="jwt")
INTERVIEW_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def start_config() -> InterviewAgentStartRequest:
    return InterviewAgentStartRequest(
        interview_id=UUID(INTERVIEW_ID),
        target_role="产品经理",
        job_description="负责用户研究",
        mode="formal",
        resume_sections=[ResumeSection(title="项目经历", content="负责 CoachCraft 产品规划")],
        resume_review_status="ai_verified",
    )


def started_response() -> InterviewStartResponse:
    return InterviewStartResponse(
        interview_id=INTERVIEW_ID,
        question=InterviewQuestion(id="q1", stage="自我介绍", text="请做一段自我介绍。", main_question_index=0, follow_up_count=0),
        total_main_questions=4,
    )


@pytest.mark.anyio
async def test_retry_replays_existing_start_without_calling_agent(monkeypatch):
    existing = started_response()
    monkeypatch.setattr(main, "reserve_daily_interview", AsyncMock(return_value=INTERVIEW_ID))
    monkeypatch.setattr(main, "load_interview_start", AsyncMock(return_value=existing))
    commit = AsyncMock()
    monkeypatch.setattr(main, "commit_daily_interview", commit)
    agent_start = AsyncMock()
    monkeypatch.setattr(main, "interviewer_agent", SimpleNamespace(start=agent_start))
    result = await main.create_interview(start_config(), USER)
    assert result.interview_id == INTERVIEW_ID
    assert result.question.text == "请做一段自我介绍。"
    agent_start.assert_not_called()
    commit.assert_awaited_once()


@pytest.mark.anyio
async def test_load_interview_start_maps_first_question(monkeypatch):
    async def fake_select(table: str, params: dict[str, str]):
        if table == "interview_questions":
            return [{
                "id": "q1",
                "external_question_id": "q1",
                "stage": "自我介绍",
                "question_text": "请结合经历做自我介绍。",
                "is_follow_up": False,
                "main_question_index": 0,
                "follow_up_count": 0,
                "resume_evidence": "",
            }]
        return [{"id": INTERVIEW_ID, "status": "active", "total_main_questions": 4}]

    monkeypatch.setattr("app.supabase_store._select", fake_select)
    result = await load_interview_start(USER.id, INTERVIEW_ID)
    assert result is not None
    assert result.interview_id == INTERVIEW_ID
    assert result.total_main_questions == 4
    assert "自我介绍" in result.question.text
