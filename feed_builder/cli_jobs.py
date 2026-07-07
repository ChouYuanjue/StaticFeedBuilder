from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import PROJECT_ROOT, Settings, ensure_runtime_dirs, load_yaml
from .crawler_runner import crawl_all
from .db import init_db, list_recommendations, upsert_competitions
from .digest import competition_to_digest_item, make_digest
from .llm import DeepSeekClient
from .notifiers import push_ntfy, push_telegram, push_webhook, write_markdown_digest

console = Console()


def crawl_job(settings: Settings, sources: str, prefs: str, llm_clean: bool, push: bool) -> int:
    ensure_runtime_dirs()
    init_db(settings)
    comps = crawl_all(settings, sources, prefs, llm_clean=llm_clean)
    n = upsert_competitions(settings, comps)
    console.print(f"[green]Saved[/green] {n} competitions")
    if push:
        digest_job(settings, prefs, llm_summary=False, push=True)
    return n


def digest_job(settings: Settings, prefs_path: str, llm_summary: bool, push: bool) -> Path:
    ensure_runtime_dirs()
    init_db(settings)
    prefs = load_yaml(prefs_path)
    pref = prefs.get("preferences", {})
    comps = list_recommendations(
        settings,
        days_ahead=int(pref.get("digest_days_ahead", 45)),
        min_score=float(pref.get("min_score_to_push", 55)),
        limit=int(pref.get("max_items_per_digest", 12)),
    )
    text = make_digest(comps)
    if llm_summary:
        llm = DeepSeekClient(settings)
        if llm.enabled and comps:
            try:
                summary = llm.make_digest_summary([competition_to_digest_item(c) for c in comps])
                if summary:
                    text = text.replace("\n\n共筛出", f"\n\n## LLM 日程摘要\n\n{summary}\n\n共筛出", 1)
            except Exception as exc:
                console.print(f"[yellow]LLM summary failed[/yellow]: {type(exc).__name__}: {exc}")
    path = write_markdown_digest(text)
    console.print(f"[green]Digest written[/green] {path.relative_to(PROJECT_ROOT)}")
    if push:
        pushed = False
        try:
            pushed = push_telegram(settings, text) or pushed
        except Exception as exc:
            console.print(f"[yellow]Telegram push failed[/yellow]: {type(exc).__name__}: {exc}")
        try:
            pushed = push_ntfy(settings, text) or pushed
        except Exception as exc:
            console.print(f"[yellow]ntfy push failed[/yellow]: {type(exc).__name__}: {exc}")
        try:
            pushed = push_webhook(settings, text, comps) or pushed
        except Exception as exc:
            console.print(f"[yellow]Webhook push failed[/yellow]: {type(exc).__name__}: {exc}")
        if not pushed:
            console.print("[yellow]No push channel configured; digest file only.[/yellow]")
    return path

