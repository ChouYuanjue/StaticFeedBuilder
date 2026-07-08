from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..models import Competition
from ..text_rules import compact_text, infer_from_text

KEYWORDS = [
    "competition", "challenge", "contest", "hackathon", "shared task", "benchmark",
    "leaderboard", "call for competitions", "workshop", "ctf", "赛", "比赛", "挑战", "评测"
]
NEGATIVE = ["privacy", "terms", "login", "sign in", "contact", "sponsor", "jobs", "career"]
BAD_ANCHOR_TEXTS = {
    "skip to main content", "skip to yearly menu bar", "main content", "yearly menu bar",
    "program", "venue", "sponsors", "organizers", "committee", "reviewing guidelines",
    "reviewer guidelines", "accepted competitions", "call for workshops", "workshops",
}
BAD_TITLE_PREFIXES = ("#", "phase ", "round ", "final-evaluations", ": completed")
CURRENT_YEAR = datetime.utcnow().year


def _looks_like_candidate(text: str, href: str) -> bool:
    clean = " ".join((text or "").split()).strip()
    low_text = clean.lower()
    blob = f"{clean} {href}".lower()
    parsed = urlparse(href)

    if len(clean) < 3:
        return False
    if parsed.fragment and not parsed.path.rstrip("/").lower().endswith(("challenge", "competitions", "workshops")):
        return False
    if low_text in BAD_ANCHOR_TEXTS:
        return False
    if low_text.startswith(BAD_TITLE_PREFIXES):
        return False
    if any(n in blob for n in NEGATIVE):
        return False
    if "completed" in blob or "archived" in blob or "closed" in blob:
        return False

    # Avoid old conference/archive pages unless the source intentionally points to the current year.
    years = [int(y) for y in re.findall(r"20\d{2}", blob)]
    if years and max(years) < CURRENT_YEAR:
        return False

    return any(k in blob for k in KEYWORDS)


def _same_site_or_allowed(base: str, link: str) -> bool:
    try:
        bp = urlparse(base)
        lp = urlparse(link)
        return not lp.netloc or lp.netloc == bp.netloc
    except Exception:
        return True


def _fetch_text(client: httpx.Client, url: str) -> tuple[str, str]:
    resp = client.get(url, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "nav", "footer", "header"]):
        bad.decompose()
    title = compact_text(soup.title.get_text(" ", strip=True) if soup.title else soup.get_text(" ", strip=True), 300)
    text = compact_text(soup.get_text(" ", strip=True), 20000)
    return title, text


def crawl_generic_html(source: dict, user_agent: str, fetch_details: bool = True) -> list[Competition]:
    url = source["url"]
    headers = {"User-Agent": user_agent}
    comps: list[Competition] = []
    seen = set()

    with httpx.Client(timeout=40, headers=headers) as client:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = compact_text(soup.get_text(" ", strip=True), 16000)

        # First create a page-level candidate if the listing page itself is a challenge/call page.
        if _looks_like_candidate(soup.title.get_text(" ", strip=True) if soup.title else source["name"], url):
            inferred = infer_from_text(page_text)
            c = Competition(
                title=soup.title.get_text(" ", strip=True)[:180] if soup.title else source["name"],
                url=url,
                source=source["name"],
                tags=source.get("tags", []),
                description=page_text[:14000],
                mode=inferred["mode"],
                school_required=inferred["school_required"],
                ai_policy=inferred["ai_policy"],
                fee=inferred["fee"],
                deliverable=inferred.get("deliverable"),
                authority_score=float(source.get("authority_hint", 60)),
                info_gap_score=float(source.get("info_gap_hint", 55)),
                evidence=inferred.get("evidence", []),
                raw={"source_url": url, "kind": "page", "candidate_text": page_text[:14000]},
            )
            dates = inferred.get("dates", [])
            if dates:
                c.submission_deadline = dates[0]
            comps.append(c)
            seen.add(url)

        for a in soup.find_all("a", href=True):
            text = compact_text(a.get_text(" ", strip=True), 220)
            href = urljoin(url, a["href"])
            if href in seen:
                continue
            if not _same_site_or_allowed(url, href):
                # Cross-site workshop/challenge links can be useful, but generic crawlers should stay conservative.
                if "github.com" not in href and "codabench" not in href and "eval.ai" not in href:
                    continue
            if not _looks_like_candidate(text, href):
                continue
            seen.add(href)
            detail_text = text
            if fetch_details:
                try:
                    _, detail_text = _fetch_text(client, href)
                except Exception:
                    detail_text = text
            inferred = infer_from_text(detail_text)
            title = text or href.rstrip("/").split("/")[-1].replace("-", " ")
            c = Competition(
                title=title[:180],
                url=href,
                source=source["name"],
                tags=source.get("tags", []),
                description=detail_text[:14000],
                mode=inferred["mode"],
                school_required=inferred["school_required"],
                ai_policy=inferred["ai_policy"],
                fee=inferred["fee"],
                deliverable=inferred.get("deliverable"),
                authority_score=float(source.get("authority_hint", 60)),
                info_gap_score=float(source.get("info_gap_hint", 55)),
                evidence=inferred.get("evidence", []),
                raw={"source_url": url, "kind": "link", "anchor_text": text, "candidate_text": detail_text[:14000]},
            )
            dates = inferred.get("dates", [])
            if dates:
                c.submission_deadline = dates[0]
            comps.append(c)

    return comps[:120]

