from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    access_token: str | None = None


_bearer = HTTPBearer(auto_error=False)
_jwks_client = jwt.PyJWKClient(
    f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
    cache_keys=True,
) if settings.supabase_url else None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Validate Supabase access tokens; use an explicit local identity only in development mode."""
    if settings.auth_mode == "development":
        return CurrentUser(id="00000000-0000-0000-0000-000000000000", email=None, access_token=None)

    if not settings.supabase_auth_enabled or _jwks_client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="账号服务尚未配置")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    try:
        signing_key = await run_in_threadpool(_jwks_client.get_signing_key_from_jwt, credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            audience=settings.supabase_jwt_audience,
            issuer=f"{settings.supabase_url}/auth/v1",
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录") from error

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证无效")
    email = payload.get("email")
    return CurrentUser(id=user_id, email=email if isinstance(email, str) else None, access_token=credentials.credentials)
