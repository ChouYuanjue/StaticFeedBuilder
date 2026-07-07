from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from .cli_jobs import crawl_job, digest_job
from .config import PROJECT_ROOT, ensure_runtime_dirs, load_settings, load_yaml
from .db import init_db, list_recommendations
from .digest import make_ics, make_items_json, make_rss, make_static_site

console = Console()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Static Feed Builder")
    p.add_argument("--sources", default="config/sources.yaml")
    p.add_argument("--prefs", default="config/preferences.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="initialize database")

    crawl = sub.add_parser("crawl", help="crawl all sources once")
    crawl.add_argument("--llm-clean", action="store_true", help="use DeepSeek only for ambiguous high-authority pages")
    crawl.add_argument("--push", action="store_true", help="push digest after crawling")

    digest = sub.add_parser("digest", help="generate digest from database")
    digest.add_argument("--days", type=int, default=None)
    digest.add_argument("--min-score", type=float, default=None)
    digest.add_argument("--limit", type=int, default=None)
    digest.add_argument("--llm-summary", action="store_true", help="use DeepSeek to create a short schedule summary")
    digest.add_argument("--push", action="store_true")

    run = sub.add_parser("run", help="run daily scheduler")
    run.add_argument("--llm-clean", action="store_true")
    run.add_argument("--llm-summary", action="store_true")

    ics = sub.add_parser("export-ics", help="export recommended deadlines as iCalendar")
    ics.add_argument("--days", type=int, default=90)
    ics.add_argument("--min-score", type=float, default=None)
    ics.add_argument("--limit", type=int, default=100)
    ics.add_argument("--output", default="out/calendar.ics")

    rss = sub.add_parser("export-rss", help="export recommended competitions as RSS feed")
    rss.add_argument("--days", type=int, default=90)
    rss.add_argument("--min-score", type=float, default=None)
    rss.add_argument("--limit", type=int, default=100)
    rss.add_argument("--output", default="out/feed.xml")
    rss.add_argument("--base-url", default="")

    site = sub.add_parser("export-site", help="export static GitHub Pages site")
    site.add_argument("--days", type=int, default=90)
    site.add_argument("--min-score", type=float, default=None)
    site.add_argument("--limit", type=int, default=100)
    site.add_argument("--output-dir", default="out")
    site.add_argument("--base-url", default="")

    return p


def main() -> None:
    args = build_parser().parse_args()
    ensure_runtime_dirs()
    settings = load_settings()

    if args.cmd == "init-db":
        init_db(settings)
        console.print("[green]Database initialized.[/green]")
        return

    if args.cmd == "crawl":
        crawl_job(settings, args.sources, args.prefs, llm_clean=args.llm_clean, push=args.push)
        return

    if args.cmd == "digest":
        if args.days is None and args.min_score is None and args.limit is None:
            digest_job(settings, args.prefs, llm_summary=args.llm_summary, push=args.push)
        else:
            prefs = load_yaml(args.prefs)
            pref = prefs.get("preferences", {})
            comps = list_recommendations(
                settings,
                days_ahead=args.days or int(pref.get("digest_days_ahead", 45)),
                min_score=args.min_score if args.min_score is not None else float(pref.get("min_score_to_push", 55)),
                limit=args.limit or int(pref.get("max_items_per_digest", 12)),
            )
            from .digest import make_digest
            from .notifiers import push_telegram, push_webhook, write_markdown_digest
            text = make_digest(comps)
            path = write_markdown_digest(text)
            console.print(text)
            console.print(f"[green]Digest written[/green] {path.relative_to(PROJECT_ROOT)}")
            if args.push:
                push_telegram(settings, text)
                push_webhook(settings, text, comps)
        return

    if args.cmd == "run":
        from .scheduler import run_scheduler

        run_scheduler(settings, args.sources, args.prefs, args.llm_clean, args.llm_summary)
        return

    if args.cmd == "export-rss":
        prefs = load_yaml(args.prefs)
        pref = prefs.get("preferences", {})
        comps = list_recommendations(
            settings,
            days_ahead=args.days,
            min_score=args.min_score if args.min_score is not None else float(pref.get("min_score_to_push", 55)),
            limit=args.limit,
        )
        out = Path(args.output)
        if not out.is_absolute():
            out = PROJECT_ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(make_rss(comps, base_url=args.base_url), encoding="utf-8")
        console.print(f"[green]RSS written[/green] {out}")
        return

    if args.cmd == "export-site":
        prefs = load_yaml(args.prefs)
        pref = prefs.get("preferences", {})
        comps = list_recommendations(
            settings,
            days_ahead=args.days,
            min_score=args.min_score if args.min_score is not None else float(pref.get("min_score_to_push", 55)),
            limit=args.limit,
        )
        out_dir = Path(args.output_dir)
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(make_static_site(comps, base_url=args.base_url), encoding="utf-8")
        (out_dir / "feed.xml").write_text(make_rss(comps, base_url=args.base_url), encoding="utf-8")
        (out_dir / "calendar.ics").write_text(make_ics(comps), encoding="utf-8")
        (out_dir / "items.json").write_text(make_items_json(comps), encoding="utf-8")
        console.print(f"[green]Site written[/green] {out_dir}")
        return

    if args.cmd == "export-ics":
        prefs = load_yaml(args.prefs)
        pref = prefs.get("preferences", {})
        comps = list_recommendations(
            settings,
            days_ahead=args.days,
            min_score=args.min_score if args.min_score is not None else float(pref.get("min_score_to_push", 55)),
            limit=args.limit,
        )
        out = Path(args.output)
        if not out.is_absolute():
            out = PROJECT_ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(make_ics(comps), encoding="utf-8")
        console.print(f"[green]ICS written[/green] {out}")
        return


if __name__ == "__main__":
    main()

