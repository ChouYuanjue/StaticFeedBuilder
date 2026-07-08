from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings


class DeepSeekClient:
    """Small OpenAI-compatible DeepSeek wrapper."""

    def __init__(self, settings: Settings):
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.model = settings.deepseek_model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str, temperature: float = 0.1) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{self.base_url}/v1/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}

    def extract_opportunity(self, title: str, url: str, text: str, current_date: str) -> dict[str, Any]:
        system = """You are a strict opportunity extraction gate.
Decide whether a webpage is a CURRENT, actionable, low-friction opportunity suitable for remote participation.
Use only the provided webpage text. Do not guess.

Reject navigation links, skip links, menus, category/tag pages, login/privacy/contact/sponsor pages, old archives, accepted-results pages, completed/closed/archived items, review guidelines, venue/program pages, and CFP pages whose deadlines are already past.

Accept only currently open or upcoming online/remote challenges, shared tasks, benchmarks, hackathons, CTFs, workshop challenges, competition tracks, or pages with explicit future deadlines.

Return ONLY JSON with this schema:
{
  "is_relevant": true/false,
  "status": "open" | "upcoming" | "closed" | "historical" | "info_page" | "unknown",
  "title": "clean real title; never use navigation text",
  "summary": "one short Chinese summary",
  "mode": "online" | "hybrid" | "onsite" | "unknown",
  "school_required": "yes" | "no" | "unknown",
  "affiliation_required": "yes" | "no" | "unknown",
  "ai_policy": "allowed" | "forbidden" | "unknown",
  "external_data_policy": "allowed" | "forbidden" | "unknown",
  "fee": "free" | "low" | "high" | "unknown",
  "deliverable": "prediction/code/model/report/writeup/demo/unknown",
  "registration_deadline": "YYYY-MM-DD or null",
  "submission_deadline": "YYYY-MM-DD or null",
  "start_at": "YYYY-MM-DD or null",
  "end_at": "YYYY-MM-DD or null",
  "authority_adjustment": -20,
  "info_gap_adjustment": 0,
  "risk_flags": ["short Chinese risk phrase"],
  "evidence": ["short exact evidence from the page, max 4 items"]
}

If all relevant dates are earlier than current_date, set is_relevant=false and status=closed or historical.
If the page is only an index/listing without a specific current opportunity, set is_relevant=false and status=info_page."""
        user = f"current_date: {current_date}\nCandidate title: {title}\nURL: {url}\nPage text:\n{text[:14000]}"
        return self.chat_json(system, user, temperature=0.0)

    def clean_competition_text(self, title: str, url: str, text: str) -> dict[str, Any]:
        from datetime import datetime

        return self.extract_opportunity(title, url, text, datetime.utcnow().date().isoformat())

    def make_digest_summary(self, items: list[dict[str, Any]]) -> str:
        system = """Write a concise Chinese daily summary from the given JSON items.
Mention priority, risks, and suggested next actions. Do not invent facts."""
        user = json.dumps(items, ensure_ascii=False, default=str)
        data = self.chat_json(system, user, temperature=0.2)
        return str(data.get("summary") or data.get("raw") or "")
