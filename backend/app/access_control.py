from __future__ import annotations

from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from .auth import CurrentUser
from .config import settings


def _headers(user: CurrentUser) -> dict[str, str]:
    if not user.access_token:
        return {}
    return {
        "Authorization": f"Bearer {user.access_token}",
        "apikey": settings.supabase_publishable_key or "",
        "Content-Type": "application/json",
    }


async def require_approved(user: CurrentUser) -> None:
    if settings.auth_mode == "development":
        return
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers=_headers(user),
            params={"user_id": f"eq.{user.id}", "select": "account_status"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="暂时无法验证账户审核状态")
    rows = response.json()
    account_status = rows[0].get("account_status") if rows else "pending"
    if account_status != "approved":
        labels = {"pending": "账户正在等待审核", "rejected": "账户申请未通过", "suspended": "账户已被暂停"}
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=labels.get(account_status, "账户当前不可用"))


async def reserve_daily_interview(user: CurrentUser, reservation_id: str | None = None) -> str | None:
    if settings.auth_mode == "development":
        return None
    reservation_id = reservation_id or str(uuid4())
    result = await _rpc(user, "reserve_daily_interview", {"p_reservation_id": reservation_id})
    if not result.get("allowed"):
        reason = result.get("reason")
        if reason == "daily_limit_reached":
            raise HTTPException(status_code=429, detail="今天已使用过一次完整面试，请明天再来")
        raise HTTPException(status_code=403, detail="账户尚未通过审核")
    return reservation_id


async def commit_daily_interview(user: CurrentUser, reservation_id: str | None) -> None:
    if reservation_id:
        await _rpc(user, "commit_daily_interview", {"p_reservation_id": reservation_id})


async def release_daily_interview(user: CurrentUser, reservation_id: str | None) -> None:
    if reservation_id:
        await _rpc(user, "release_daily_interview", {"p_reservation_id": reservation_id})


async def _rpc(user: CurrentUser, name: str, body: dict[str, str]):
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"{settings.supabase_url}/rest/v1/rpc/{name}", headers=_headers(user), json=body)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="账户权限服务暂时不可用")
    return response.json()
