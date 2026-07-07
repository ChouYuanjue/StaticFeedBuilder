from __future__ import annotations

from pathlib import Path

import httpx

from .config import PROJECT_ROOT, Settings
from .models import Competition


def write_markdown_digest(text: str, filename: str | None = None) -> Path:
    out = PROJECT_ROOT / "out"
    out.mkdir(parents=True, exist_ok=True)
    path = out / (filename or "latest_digest.md")
    path.write_text(text, encoding="utf-8")
    return path


def push_telegram(settings: Settings, text: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    # Telegram single message limit is around 4096 chars; keep first chunk.
    payload = {"chat_id": settings.telegram_chat_id, "text": text[:3900], "disable_web_page_preview": True}
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
    return True


def push_webhook(settings: Settings, text: str, items: list[Competition]) -> bool:
    if not settings.webhook_url:
        return False
    payload = {
        "text": text,
        "items": [
            {
                "title": c.title,
                "url": c.url,
                "source": c.source,
                "score": c.final_score,
                "tags": c.tags,
                "deadline": c.deadline().isoformat() if c.deadline() else None,
                "risk_flags": c.risk_flags,
            }
            for c in items
        ],
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(settings.webhook_url, json=payload)
        resp.raise_for_status()
    return True


def push_ntfy(settings: Settings, text: str) -> bool:
    if not getattr(settings, "ntfy_topic", None):
        return False
    url = f"{settings.ntfy_server}/{settings.ntfy_topic}"
    headers = {
        "Title": "Static Feed Builder",
        "Tags": "trophy,robot",
        "Priority": "default",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, content=text[:3900].encode("utf-8"), headers=headers)
        resp.raise_for_status()
    return True

