from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT


class LLMCache:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else PROJECT_ROOT / "data" / "llm_cache.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    @staticmethod
    def text_hash(text: str) -> str:
        normalized = " ".join((text or "").split())[:16000]
        return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def key(url: str, text: str, schema_version: str = "v2") -> str:
        canonical_url = url.split("#")[0].split("?")[0].rstrip("/")
        return f"{schema_version}:{canonical_url}:{LLMCache.text_hash(text)}"

    def get(self, url: str, text: str) -> dict[str, Any] | None:
        value = self.data.get(self.key(url, text))
        return value if isinstance(value, dict) else None

    def set(self, url: str, text: str, value: dict[str, Any]) -> None:
        self.data[self.key(url, text)] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
