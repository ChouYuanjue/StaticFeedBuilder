from __future__ import annotations

import re
from datetime import datetime

try:
    import dateparser  # type: ignore
except Exception:  # pragma: no cover - optional fallback
    dateparser = None

from dateutil import parser as dateutil_parser

ONLINE_WORDS = ["online", "virtual", "remote", "submission", "leaderboard", "internet", "线上", "在线", "远程"]
ONSITE_WORDS = ["onsite only", "in-person only", "现场", "线下", "proctored", "closed-book", "live coding"]
SCHOOL_WORDS = ["university only", "student only", "school nomination", "institutional", "以学校", "学校推荐", "院校"]
AI_ALLOWED_WORDS = [
    "pre-trained", "pretrained", "external data", "open source", "any method", "llm", "large language model",
    "foundation model", "generative ai", "agents", "允许使用", "外部数据", "预训练", "开源"
]
AI_FORBIDDEN_WORDS = ["no ai", "ai tools are prohibited", "forbidden to use", "禁止使用ai", "禁止外部", "不得使用"]
FREE_WORDS = ["free", "no fee", "免费", "no registration fee"]
HIGH_FEE_WORDS = ["registration fee", "fee:", "报名费", "$", "usd", "eur"]
DELIVERABLE_WORDS = ["prediction", "code", "model", "report", "writeup", "technical report", "demo", "submission"]

DATE_PATTERNS = [
    r"(?:deadline|due|submission deadline|registration deadline|ends?|closes?)[:：]?\s*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
    r"(?:deadline|due|submission deadline|registration deadline|ends?|closes?)[:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
    r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
    r"([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
]


def compact_text(text: str, max_len: int = 4000) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_len]


def contains_any(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def evidence_for(text: str, words: list[str], window: int = 130) -> list[str]:
    low = text.lower()
    out = []
    for w in words:
        i = low.find(w.lower())
        if i >= 0:
            start = max(0, i - window)
            end = min(len(text), i + len(w) + window)
            out.append(compact_text(text[start:end], 300))
    return out[:4]


def guess_mode(text: str) -> tuple[str, list[str]]:
    if contains_any(text, ONSITE_WORDS):
        return "onsite", evidence_for(text, ONSITE_WORDS)
    if contains_any(text, ONLINE_WORDS):
        return "online", evidence_for(text, ONLINE_WORDS)
    return "unknown", []


def guess_school_required(text: str) -> tuple[str, list[str]]:
    if contains_any(text, SCHOOL_WORDS):
        return "yes", evidence_for(text, SCHOOL_WORDS)
    return "unknown", []


def guess_ai_policy(text: str) -> tuple[str, list[str]]:
    if contains_any(text, AI_FORBIDDEN_WORDS):
        return "forbidden", evidence_for(text, AI_FORBIDDEN_WORDS)
    if contains_any(text, AI_ALLOWED_WORDS):
        return "allowed", evidence_for(text, AI_ALLOWED_WORDS)
    return "unknown", []


def guess_fee(text: str) -> tuple[str, list[str]]:
    if contains_any(text, FREE_WORDS):
        return "free", evidence_for(text, FREE_WORDS)
    if contains_any(text, HIGH_FEE_WORDS):
        # Mentioning fee is not always high. Mark unknown with risk evidence instead of high.
        return "unknown", evidence_for(text, HIGH_FEE_WORDS)
    return "unknown", []


def guess_deliverable(text: str) -> tuple[str | None, list[str]]:
    hits = [w for w in DELIVERABLE_WORDS if w.lower() in text.lower()]
    if hits:
        return ", ".join(hits[:4]), evidence_for(text, hits[:4])
    return None, []


def find_dates(text: str) -> list[datetime]:
    dates: list[datetime] = []
    for pat in DATE_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            raw = m.group(1) if m.groups() else m.group(0)
            if dateparser is not None:
                dt = dateparser.parse(raw, settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False})
            else:
                try:
                    dt = dateutil_parser.parse(raw, fuzzy=True)
                except Exception:
                    dt = None
            if dt and dt.year >= datetime.utcnow().year - 1:
                dates.append(dt.replace(microsecond=0))
    # unique while preserving order
    seen = set()
    uniq = []
    for d in dates:
        k = d.date().isoformat()
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    return uniq[:5]


def infer_from_text(text: str) -> dict:
    text = compact_text(text, 12000)
    mode, mode_ev = guess_mode(text)
    school, school_ev = guess_school_required(text)
    ai, ai_ev = guess_ai_policy(text)
    fee, fee_ev = guess_fee(text)
    deliverable, deliv_ev = guess_deliverable(text)
    dates = find_dates(text)
    evidence = mode_ev + school_ev + ai_ev + fee_ev + deliv_ev
    return {
        "mode": mode,
        "school_required": school,
        "ai_policy": ai,
        "fee": fee,
        "deliverable": deliverable,
        "dates": dates,
        "evidence": evidence[:8],
    }

