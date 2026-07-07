from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings


class DeepSeekClient:
    """Small OpenAI-compatible DeepSeek wrapper.

    This project deliberately keeps LLM calls optional and sparse.
    """

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

    def clean_competition_text(self, title: str, url: str, text: str) -> dict[str, Any]:
        system = """你是竞赛情报抽取器。只根据用户给出的页面文本判断，不要猜。
输出 JSON，字段包括：summary, mode, school_required, ai_policy, fee, deliverable, evidence。
mode 只能是 online/hybrid/onsite/unknown。
school_required/ai_policy/fee 不确定时填 unknown。
evidence 必须是页面原文短句数组。"""
        user = f"标题：{title}\nURL：{url}\n页面文本：\n{text[:12000]}"
        return self.chat_json(system, user)

    def make_digest_summary(self, items: list[dict[str, Any]]) -> str:
        system = """你是中文竞赛机会分析助手。基于 JSON 列表生成简短日程摘要。
要求：少废话，指出优先级、风险、建议行动。不要编造列表外信息。"""
        user = json.dumps(items, ensure_ascii=False, default=str)
        data = self.chat_json(system, user, temperature=0.2)
        return str(data.get("summary") or data.get("raw") or "")

