from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import auth


@pytest.mark.anyio
async def test_development_mode_uses_explicit_local_identity(monkeypatch):
    monkeypatch.setattr(auth, "settings", SimpleNamespace(auth_mode="development"))
    user = await auth.get_current_user(None)
    assert user.id == "00000000-0000-0000-0000-000000000000"


@pytest.mark.anyio
async def test_production_mode_rejects_missing_configuration(monkeypatch):
    monkeypatch.setattr(auth, "settings", SimpleNamespace(auth_mode="supabase", supabase_auth_enabled=False))
    monkeypatch.setattr(auth, "_jwks_client", None)
    with pytest.raises(HTTPException) as caught:
        await auth.get_current_user(None)
    assert caught.value.status_code == 503
