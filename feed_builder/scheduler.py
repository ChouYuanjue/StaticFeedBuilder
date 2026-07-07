from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from rich.console import Console

from .cli_jobs import crawl_job, digest_job
from .config import Settings

console = Console()


def run_scheduler(settings: Settings, sources: str, prefs: str, llm_clean: bool, llm_summary: bool) -> None:
    scheduler = BlockingScheduler(timezone=settings.timezone)

    scheduler.add_job(
        crawl_job,
        "cron",
        hour=8,
        minute=10,
        args=[settings, sources, prefs, llm_clean, False],
        id="daily_crawl",
        replace_existing=True,
    )
    scheduler.add_job(
        digest_job,
        "cron",
        hour=8,
        minute=25,
        args=[settings, prefs, llm_summary, True],
        id="daily_digest_push",
        replace_existing=True,
    )

    console.print("[green]Scheduler started[/green]: crawl 08:10, digest push 08:25")
    scheduler.start()

