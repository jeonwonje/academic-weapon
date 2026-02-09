"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Walk up from CWD looking for a .env file."""
    cur = Path.cwd()
    for parent in [cur, *cur.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file() or ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Canvas ──────────────────────────────────────────────────────────
    canvas_api_url: str = Field(default="https://canvas.nus.edu.sg")
    canvas_api_token: str = Field(default="")

    # ── OpenAI ──────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")

    # ── Telegram ────────────────────────────────────────────────────────
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # ── Storage ─────────────────────────────────────────────────────────
    data_dir: Path = Field(default=Path("./data"))

    # ── Sync schedule (SGT = UTC+8) ─────────────────────────────────────
    sync_hour: int = Field(default=6)
    sync_minute: int = Field(default=0)

    # ── Derived helpers ─────────────────────────────────────────────────
    @property
    def canvas_base(self) -> str:
        return self.canvas_api_url.rstrip("/") + "/api/v1"

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.canvas_api_token}"}

    def course_dir(self, course_code: str) -> Path:
        """Return the data directory for a specific course."""
        d = self.data_dir / self._sanitise(course_code)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _sanitise(name: str) -> str:
        """Make a filesystem-safe directory name."""
        return "".join(c if c.isalnum() or c in ("-", "_", " ") else "_" for c in name).strip()


# Singleton – import this everywhere
settings = Settings()
