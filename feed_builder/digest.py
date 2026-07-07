from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from .models import Competition


def fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "未知"


def risk_line(c: Competition) -> str:
    if not c.risk_flags:
        return "暂无明显硬风险"
    return "；".join(c.risk_flags[:3])


def make_card(c: Competition, index: int | None = None) -> str:
    prefix = f"{index}. " if index is not None else ""
    tags = ", ".join(c.tags[:6]) if c.tags else "未分类"
    evidence = ""
    if c.evidence:
        evidence = "\n证据：" + " / ".join(e[:120] for e in c.evidence[:2])
    return (
        f"{prefix}【{c.final_score:.1f}/100】{c.title}\n"
        f"领域：{tags}\n"
        f"来源：{c.source}\n"
        f"模式：{c.mode}｜学校/机构：{c.school_required}｜AI政策：{c.ai_policy}｜费用：{c.fee}\n"
        f"截止：{fmt_date(c.deadline())}\n"
        f"风险：{risk_line(c)}\n"
        f"建议：先看 rules/baseline，确认是否远程、是否需要学校名义、是否允许外部工具。\n"
        f"链接：{c.url}"
        f"{evidence}"
    )


def make_digest(comps: list[Competition], title: str = "Static Feed Builder Daily Digest") -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    if not comps:
        return f"# {title} - {today}\n\n今日没有达到阈值的推荐。"
    parts = [f"# {title} - {today}", ""]
    parts.append(f"共筛出 {len(comps)} 个候选，按推荐分排序。")
    parts.append("")
    for i, c in enumerate(comps, 1):
        parts.append(make_card(c, i))
        parts.append("\n---\n")
    return "\n".join(parts).strip() + "\n"


def competition_to_digest_item(c: Competition) -> dict:
    return {
        "title": c.title,
        "url": c.url,
        "source": c.source,
        "tags": c.tags,
        "score": c.final_score,
        "mode": c.mode,
        "deadline": fmt_date(c.deadline()),
        "ai_policy": c.ai_policy,
        "school_required": c.school_required,
        "risk_flags": c.risk_flags,
    }


def make_ics(comps: list[Competition]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Static Feed Builder//CN",
        "CALSCALE:GREGORIAN",
    ]
    for c in comps:
        dl = c.deadline()
        if not dl:
            continue
        day = dl.strftime("%Y%m%d")
        uid = f"{abs(hash(c.normalized_key()))}@static-feed-builder"
        summary = _ics_escape(f"DDL: {c.title[:80]}")
        desc = _ics_escape(f"Score: {c.final_score}\nSource: {c.source}\nURL: {c.url}\nRisk: {risk_line(c)}")
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;VALUE=DATE:{day}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_rss(comps: list[Competition], base_url: str = "", title: str = "Static Feed Builder") -> str:
    now = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    channel_link = base_url.rstrip("/") + "/" if base_url else ""
    items: list[str] = []
    for c in comps:
        pub = (c.updated_at or c.discovered_at or datetime.utcnow()).strftime("%a, %d %b %Y %H:%M:%S +0000")
        desc = html.escape(
            f"领域：{', '.join(c.tags[:6]) if c.tags else '未分类'}\n"
            f"来源：{c.source}\n"
            f"分数：{c.final_score}\n"
            f"截止：{fmt_date(c.deadline())}\n"
            f"模式：{c.mode}\n"
            f"学校/机构：{c.school_required}\n"
            f"AI政策：{c.ai_policy}\n"
            f"风险：{risk_line(c)}\n"
            f"链接：{c.url}"
        )
        guid = html.escape(c.normalized_key())
        items.append(
            "  <item>\n"
            f"    <title>{html.escape(f'[{c.final_score:.1f}] {c.title}')}</title>\n"
            f"    <link>{html.escape(c.url)}</link>\n"
            f"    <guid isPermaLink=\"false\">{guid}</guid>\n"
            f"    <pubDate>{pub}</pubDate>\n"
            f"    <description>{desc}</description>\n"
            "  </item>"
        )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<rss version=\"2.0\">\n"
        "<channel>\n"
        f"  <title>{html.escape(title)}</title>\n"
        f"  <link>{html.escape(channel_link)}</link>\n"
        "  <description>AI/CS/modeling/CTF low-cost competition opportunities</description>\n"
        f"  <lastBuildDate>{now}</lastBuildDate>\n"
        + "\n".join(items)
        + "\n</channel>\n</rss>\n"
    )


def make_static_site(comps: list[Competition], base_url: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards = []
    for c in comps:
        tag_html = "".join(f"<span>{html.escape(t)}</span>" for t in c.tags[:8])
        evidence = ""
        if c.evidence:
            evidence = f"<p class='evidence'>证据：{html.escape(' / '.join(c.evidence[:2])[:260])}</p>"
        cards.append(f"""
        <article class="card">
          <h2><a href="{html.escape(c.url)}" target="_blank" rel="noreferrer">{html.escape(c.title)}</a></h2>
          <div class="score">{c.final_score:.1f}/100</div>
          <p class="meta">来源：{html.escape(c.source)}｜截止：{fmt_date(c.deadline())}｜模式：{html.escape(c.mode)}｜AI：{html.escape(c.ai_policy)}</p>
          <p class="risk">风险：{html.escape(risk_line(c))}</p>
          <div class="tags">{tag_html}</div>
          {evidence}
        </article>
        """)
    rss = f"<a href='{base_url.rstrip('/')}/feed.xml'>RSS</a>" if base_url else "<a href='feed.xml'>RSS</a>"
    ics = f"<a href='{base_url.rstrip('/')}/calendar.ics'>Calendar</a>" if base_url else "<a href='calendar.ics'>Calendar</a>"
    json_link = f"<a href='{base_url.rstrip('/')}/items.json'>JSON</a>" if base_url else "<a href='items.json'>JSON</a>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Static Feed Builder</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f6f7f9; color: #161616; }}
    header {{ padding: 32px 18px; background: #111827; color: white; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 20px; }}
    a {{ color: #2563eb; text-decoration: none; }}
    .links a {{ color: white; margin-right: 14px; text-decoration: underline; }}
    .card {{ position: relative; background: white; border-radius: 16px; padding: 18px; margin: 16px 0; box-shadow: 0 4px 18px rgba(0,0,0,.06); }}
    .card h2 {{ margin: 0 80px 8px 0; font-size: 20px; }}
    .score {{ position: absolute; right: 18px; top: 18px; font-weight: 700; color: #0f766e; }}
    .meta, .risk, .evidence {{ color: #4b5563; line-height: 1.55; }}
    .tags span {{ display: inline-block; background: #e5e7eb; padding: 4px 8px; border-radius: 999px; margin: 3px; font-size: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>Static Feed Builder</h1>
    <p>自动收集 AI / CS / 建模 / CTF / Workshop Challenge 的低成本机会。</p>
    <p>更新时间：{html.escape(now)}｜共 {len(comps)} 条</p>
    <p class="links">{rss} {ics} {json_link}</p>
  </header>
  <main>
    {''.join(cards) if cards else '<p>暂无达到阈值的推荐。</p>'}
  </main>
</body>
</html>
"""


def make_items_json(comps: list[Competition]) -> str:
    return json.dumps([competition_to_digest_item(c) | {"url": c.url, "source": c.source} for c in comps], ensure_ascii=False, indent=2, default=str)

