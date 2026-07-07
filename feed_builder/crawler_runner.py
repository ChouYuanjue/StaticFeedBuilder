from __future__ import annotations

from rich.console import Console

from .config import Settings, load_yaml
from .crawlers.ctftime import crawl_ctftime
from .crawlers.generic_html import crawl_generic_html
from .llm import DeepSeekClient
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


def crawl_all(settings: Settings, sources_path: str, prefs_path: str, llm_clean: bool = False) -> list[Competition]:
    sources_cfg = load_yaml(sources_path)
    prefs = load_yaml(prefs_path)
    sources = [s for s in sources_cfg.get("sources", []) if s.get("enabled", True)]
    all_comps: list[Competition] = []
    llm = DeepSeekClient(settings)

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

        if llm_clean:
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

