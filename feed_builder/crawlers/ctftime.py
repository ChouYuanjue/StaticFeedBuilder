from __future__ import annotations

from datetime import datetime

import httpx
from dateutil import parser as dateutil_parser

from ..models import Competition


def _parse_ts(v) -> datetime | None:
    if v is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(v))
    except Exception:
        pass
    try:
        dt = dateutil_parser.parse(str(v))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        return None


def crawl_ctftime(source: dict, user_agent: str) -> list[Competition]:
    url = source["url"]
    headers = {"User-Agent": user_agent}
    with httpx.Client(timeout=30, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    comps: list[Competition] = []
    for ev in data:
        onsite = bool(ev.get("onsite"))
        restrictions = (ev.get("restrictions") or "").lower()
        fmt = (ev.get("format") or "").lower()
        title = ev.get("title") or "Untitled CTF"
        low_title = title.lower()
        if any(word in low_title for word in ["cancelled", "canceled", "postponed", "completed"]):
            continue
        ctftime_url = ev.get("ctftime_url") or ev.get("url") or url
        tags = list(source.get("tags", []))
        if "jeopardy" in fmt:
            tags.append("jeopardy")
        c = Competition(
            title=title,
            url=ctftime_url,
            source=source["name"],
            tags=sorted(set(tags)),
            organizer=ev.get("organizers", [{}])[0].get("name") if ev.get("organizers") else None,
            description=ev.get("description") or None,
            mode="onsite" if onsite else "online",
            start_at=_parse_ts(ev.get("start")),
            end_at=_parse_ts(ev.get("finish")),
            submission_deadline=_parse_ts(ev.get("finish")),
            fee="unknown",
            school_required="unknown",
            ai_policy="unknown",
            deliverable="CTF writeup / flags",
            authority_score=float(source.get("authority_hint", 78)),
            info_gap_score=float(source.get("info_gap_hint", 65)),
            raw=ev,
        )
        if onsite:
            c.risk_flags.append("CTFtime 标记为 onsite")
        if "academic" in restrictions or "university" in restrictions:
            c.school_required = "yes"
        comps.append(c)
    return comps

