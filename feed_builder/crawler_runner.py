from __future__ import annotations

from datetime import datetime
from typing import Any

from dateutil import parser as dateutil_parser
from rich.console import Console

from .config import Settings, load_yaml
from .crawlers.ctftime import crawl_ctftime
from .crawlers.generic_html import crawl_generic_html
from .llm import DeepSeekClient
from .llm_cache import LLMCache
from .models import Competition
from .scoring import score_competition
from .text_rules import compact_text

console = Console()


def maybe_llm_clean(c: Competition, client: DeepSeekClient) -> Competition:
    if not client.enabled:
        return c
    # Sparse LLM rule: only clean high-authority candidates whose critical fields are unknown.
    if c.authority_score < 75:
        return c
    unknowns = [c.mode, c.school_required, c.ai_policy, c.fee].count("unknown")
    if unknowns < 3:
        return c
    text = compact_text(c.description or "", 12000)
    if len(text) < 500:
        return c
    try:
        data = client.clean_competition_text(c.title, c.url, text)
    except Exception as exc:
        c.risk_flags.append(f"LLM 清理失败：{type(exc).__name__}")
        return c

    c.description = data.get("summary") or c.description
    for field in ["mode", "school_required", "ai_policy", "fee", "deliverable"]:
        value = data.get(field)
        if value and getattr(c, field, "unknown") in [None, "unknown"]:
            setattr(c, field, value)
    ev = data.get("evidence") or []
    if isinstance(ev, list):
        c.evidence = list(dict.fromkeys(c.evidence + [str(x)[:400] for x in ev]))[:10]
    return c


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = dateutil_parser.parse(str(value), fuzzy=True)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt.replace(microsecond=0)
    except Exception:
        return None


def _expired(c: Competition, now: datetime) -> bool:
    dl = c.deadline()
    return bool(dl and dl.date() < now.date())


def _apply_llm(c: Competition, data: dict[str, Any], now: datetime) -> Competition | None:
    status = str(data.get("status") or "unknown").lower()
    if not data.get("is_relevant") or status in {"closed", "historical", "info_page"}:
        return None
    title = str(data.get("title") or "").strip()
    if len(title) >= 4 and not title.lower().startswith("skip to"):
        c.title = title[:180]
    c.description = str(data.get("summary") or c.description or "")[:14000]
    for field in ["mode", "school_required", "affiliation_required", "ai_policy", "external_data_policy", "fee", "deliverable"]:
        val = data.get(field)
        if val not in [None, "", "null"]:
            setattr(c, field, str(val))
    c.registration_deadline = _parse_date(data.get("registration_deadline")) or c.registration_deadline
    c.submission_deadline = _parse_date(data.get("submission_deadline")) or c.submission_deadline
    c.start_at = _parse_date(data.get("start_at")) or c.start_at
    c.end_at = _parse_date(data.get("end_at")) or c.end_at
    try:
        c.authority_score += float(data.get("authority_adjustment") or 0)
        c.info_gap_score += float(data.get("info_gap_adjustment") or 0)
    except Exception:
        pass
    risks = data.get("risk_flags") or []
    if isinstance(risks, list):
        c.risk_flags = list(dict.fromkeys(c.risk_flags + [str(x)[:120] for x in risks if str(x).strip()]))[:8]
    evidence = data.get("evidence") or []
    if isinstance(evidence, list):
        c.evidence = list(dict.fromkeys(c.evidence + [str(x)[:400] for x in evidence if str(x).strip()]))[:10]
    c.raw["llm_status"] = status
    c.raw["llm_relevant"] = True
    if _expired(c, now):
        return None
    return c


def llm_gate(comps: list[Competition], client: DeepSeekClient, cache: LLMCache, max_calls: int) -> list[Competition]:
    if not client.enabled:
        console.print("[yellow]LLM gate requested but API key is missing; skip generic HTML candidates to avoid noisy output.[/yellow]")
        return []
    now = datetime.utcnow()
    today = now.date().isoformat()
    kept: list[Competition] = []
    calls = hits = rejected = budget_skips = 0
    for c in comps:
        text = compact_text(str(c.raw.get("candidate_text") or c.description or ""), 14000)
        if len(text) < 120:
            rejected += 1
            continue
        data = cache.get(c.url, text)
        if data is not None:
            hits += 1
        else:
            if calls >= max_calls:
                budget_skips += 1
                continue
            try:
                data = client.extract_opportunity(c.title, c.url, text, today)
                cache.set(c.url, text, data)
                calls += 1
            except Exception as exc:
                c.risk_flags.append(f"LLM 抽取失败：{type(exc).__name__}")
                rejected += 1
                continue
        refined = _apply_llm(c, data, now)
        if refined is None:
            rejected += 1
        else:
            kept.append(refined)
    cache.save()
    console.print(f"[cyan]LLM gate[/cyan] kept={len(kept)} rejected={rejected} calls={calls} cache_hits={hits} budget_skips={budget_skips}")
    return kept


def crawl_all(settings: Settings, sources_path: str, prefs_path: str, llm_clean: bool = False) -> list[Competition]:
    sources_cfg = load_yaml(sources_path)
    prefs = load_yaml(prefs_path)
    llm_prefs = prefs.get("llm", {})
    sources = [s for s in sources_cfg.get("sources", []) if s.get("enabled", True)]
    all_comps: list[Competition] = []
    llm = DeepSeekClient(settings)
    cache = LLMCache()
    remaining_calls = int(llm_prefs.get("max_calls_per_run", 45))

    for source in sources:
        name = source.get("name", "unknown")
        strategy = source.get("strategy")
        try:
            if strategy == "ctftime_api":
                comps = crawl_ctftime(source, settings.user_agent)
            elif strategy == "generic_html":
                comps = crawl_generic_html(source, settings.user_agent)
            else:
                console.print(f"[yellow]Skip unknown strategy[/yellow] {strategy}: {name}")
                continue
        except Exception as exc:
            console.print(f"[red]Crawler failed[/red] {name}: {type(exc).__name__}: {exc}")
            continue

        if strategy == "generic_html" and (llm_clean or llm.enabled):
            before = len(comps)
            per_source_limit = int(source.get("llm_max_candidates", 8))
            budget = min(remaining_calls, per_source_limit)
            if budget <= 0:
                comps = []
                console.print(f"[yellow]LLM budget exhausted; skip[/yellow] {name}")
            else:
                comps = llm_gate(comps[:budget], llm, cache, max_calls=budget)
                remaining_calls -= budget
            console.print(f"[blue]Filtered[/blue] {before} -> {len(comps)} for {name}")
        elif llm_clean:
            comps = [maybe_llm_clean(c, llm) for c in comps]

        comps = [score_competition(c, prefs) for c in comps]
        console.print(f"[green]Fetched[/green] {len(comps):3d} from {name}")
        all_comps.extend(comps)

    # Deduplicate in memory by normalized key, keep higher score.
    best: dict[str, Competition] = {}
    for c in all_comps:
        k = c.normalized_key()
        if k not in best or c.final_score > best[k].final_score:
            best[k] = c
    return sorted(best.values(), key=lambda x: x.final_score, reverse=True)

