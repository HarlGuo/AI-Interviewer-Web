from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app import access_control
from app.auth import CurrentUser


USER = CurrentUser(id="11111111-1111-1111-1111-111111111111", email="tester@example.com", access_token="jwt")


@pytest.mark.anyio
async def test_development_mode_does_not_consume_allowance(monkeypatch):
    monkeypatch.setattr(access_control, "settings", SimpleNamespace(auth_mode="development"))
    assert await access_control.reserve_daily_interview(USER) is None


@pytest.mark.anyio
async def test_daily_limit_returns_429(monkeypatch):
    monkeypatch.setattr(access_control, "settings", SimpleNamespace(auth_mode="supabase"))
    rpc = AsyncMock(return_value={"allowed": False, "reason": "daily_limit_reached"})
    monkeypatch.setattr(access_control, "_rpc", rpc)
    with pytest.raises(HTTPException) as caught:
        await access_control.reserve_daily_interview(USER)
    assert caught.value.status_code == 429


@pytest.mark.anyio
async def test_pending_account_returns_403(monkeypatch):
    monkeypatch.setattr(access_control, "settings", SimpleNamespace(auth_mode="supabase"))
    monkeypatch.setattr(access_control, "_rpc", AsyncMock(return_value={"allowed": False, "reason": "pending"}))
    with pytest.raises(HTTPException) as caught:
        await access_control.reserve_daily_interview(USER)
    assert caught.value.status_code == 403


@pytest.mark.anyio
async def test_reserve_reuses_client_interview_id(monkeypatch):
    monkeypatch.setattr(access_control, "settings", SimpleNamespace(auth_mode="supabase"))
    rpc = AsyncMock(return_value={"allowed": True, "reason": "reserved"})
    monkeypatch.setattr(access_control, "_rpc", rpc)
    reservation_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert await access_control.reserve_daily_interview(USER, reservation_id) == reservation_id
    assert rpc.await_args.args[1] == "reserve_daily_interview"
    assert rpc.await_args.args[2] == {"p_reservation_id": reservation_id}
