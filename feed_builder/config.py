from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    database_url: str
    timezone: str
    user_agent: str
    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    webhook_url: str | None
    ntfy_topic: str | None
    ntfy_server: str


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/feed_builder.sqlite3"),
        timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
        user_agent=os.getenv("USER_AGENT", "CompetitionRadarAgent/0.1"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        webhook_url=os.getenv("WEBHOOK_URL") or None,
        ntfy_topic=os.getenv("NTFY_TOPIC") or None,
        ntfy_server=(os.getenv("NTFY_SERVER") or "https://ntfy.sh").rstrip("/"),
    )


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def ensure_runtime_dirs() -> None:
    for name in ["data", "out", "logs"]:
        (PROJECT_ROOT / name).mkdir(parents=True, exist_ok=True)

