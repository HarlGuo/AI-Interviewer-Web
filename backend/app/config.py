from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    allowed_origins: tuple[str, ...] = tuple(filter(None, os.getenv("ALLOWED_ORIGINS", "http://localhost:8081").split(",")))
    auth_mode: str = os.getenv("AUTH_MODE", "development").strip().lower()
    supabase_url: str | None = os.getenv("SUPABASE_URL", "").rstrip("/") or None
    supabase_publishable_key: str | None = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip() or None
    supabase_jwt_audience: str = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")

    @property
    def supabase_auth_enabled(self) -> bool:
        return self.auth_mode == "supabase" and bool(self.supabase_url and self.supabase_publishable_key)


settings = Settings()
