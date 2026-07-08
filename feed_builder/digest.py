from __future__ import annotations

import html
import json
from datetime import datetime

from .models import Competition


def fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "未知"


def risk_line(c: Competition) -> str:
    if not c.risk_flags:
        return "暂无明显硬风险"
    return "；".join(c.risk_flags[:3])


def tags_text(c: Competition, max_items: int = 6) -> str:
    return "，".join(c.tags[:max_items]) if c.tags else "未分类"


def zh_summary(c: Competition) -> str:
    """Return a mobile-friendly Chinese summary without extra LLM calls."""
    desc = (c.description or "").strip()
    if desc:
        return desc[:260]

    tag_blob = tags_text(c, 4)
    source = c.source or "公开来源"
    mode = c.mode or "unknown"
    lower_blob = f"{source} {tag_blob}".lower()
    if "ctf" in lower_blob:
        return f"这是来自 {source} 的线上安全/CTF 赛事线索，适合希望远程刷题、练习安全题型的小队或个人；请进入链接确认赛制、时区、报名方式和题目范围。"
    if any(t in lower_blob for t in ["nlp", "shared", "qa", "ir", "retrieval"]):
        return f"这是来自 {source} 的 NLP/检索/问答类 shared task 或 benchmark 线索，适合用现成模型、LLM 或检索增强方法做远程提交；请查看规则确认数据、提交格式和截止时间。"
    if any(t in lower_blob for t in ["cv", "multimodal", "medical", "vision"]):
        return f"这是来自 {source} 的视觉/多模态/医学 AI 相关挑战线索，可能关联 workshop、benchmark 或线上评测；请查看链接确认是否仍开放报名和提交。"
    return f"这是来自 {source} 的 {tag_blob} 相关线上机会，当前模式标记为 {mode}；建议打开比赛链接核对报名/提交截止、团队限制、费用和外部工具政策。"


def make_card(c: Competition, index: int | None = None) -> str:
    prefix = f"{index}. " if index is not None else ""
    evidence = ""
    if c.evidence:
        evidence = "\n证据：" + " / ".join(e[:120] for e in c.evidence[:2])
    return (
        f"{prefix}【{c.final_score:.1f}/100】{c.title}\n"
        f"中文简介：{zh_summary(c)}\n"
        f"领域：{tags_text(c)}\n"
        f"来源：{c.source}\n"
        f"截止：{fmt_date(c.deadline())}\n"
        f"模式：{c.mode}｜学校/机构：{c.school_required}｜AI政策：{c.ai_policy}｜费用：{c.fee}\n"
        f"风险：{risk_line(c)}\n"
        f"比赛链接：{c.url}"
        f"{evidence}"
    )


def make_digest(comps: list[Competition], title: str = "Static Feed Builder Daily Digest") -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    if not comps:
        return f"# {title} - {today}\n\n今日没有达到阈值的推荐。\n"
    parts = [f"# {title} - {today}", ""]
    parts.append(f"共筛出 {len(comps)} 个候选；已做来源多样化，避免单一平台刷屏。")
    parts.append("")
    for i, c in enumerate(comps, 1):
        parts.append(make_card(c, i))
        parts.append("\n---\n")
    return "\n".join(parts).strip() + "\n"


def competition_to_digest_item(c: Competition) -> dict:
    return {
        "title": c.title,
        "summary_zh": zh_summary(c),
        "url": c.url,
        "competition_link": c.url,
        "source": c.source,
        "tags": c.tags,
        "score": c.final_score,
        "mode": c.mode,
        "deadline": fmt_date(c.deadline()),
        "ai_policy": c.ai_policy,
        "school_required": c.school_required,
        "fee": c.fee,
        "risk_flags": c.risk_flags,
    }


def make_ics(comps: list[Competition]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Static Feed Builder//CN", "CALSCALE:GREGORIAN"]
    for c in comps:
        dl = c.deadline()
        if not dl:
            continue
        day = dl.strftime("%Y%m%d")
        uid = f"{abs(hash(c.normalized_key()))}@static-feed-builder"
        summary = _ics_escape(f"DDL: {c.title[:80]}")
        desc = _ics_escape(
            f"中文简介: {zh_summary(c)}\n"
            f"Score: {c.final_score}\n"
            f"Source: {c.source}\n"
            f"Link: {c.url}\n"
            f"Risk: {risk_line(c)}"
        )
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
            f"中文简介：{zh_summary(c)}\n"
            f"领域：{tags_text(c)}\n"
            f"来源：{c.source}\n"
            f"分数：{c.final_score:.1f}\n"
            f"截止：{fmt_date(c.deadline())}\n"
            f"模式：{c.mode}\n"
            f"学校/机构：{c.school_required}\n"
            f"AI政策：{c.ai_policy}\n"
            f"风险：{risk_line(c)}\n"
            f"比赛链接：{c.url}"
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
        "  <description>Public source digest with RSS, calendar and mobile-friendly summaries</description>\n"
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
          <p class="summary"><strong>中文简介：</strong>{html.escape(zh_summary(c))}</p>
          <p class="meta">来源：{html.escape(c.source)}｜截止：{fmt_date(c.deadline())}｜模式：{html.escape(c.mode)}｜AI：{html.escape(c.ai_policy)}｜费用：{html.escape(c.fee)}</p>
          <p class="risk">风险：{html.escape(risk_line(c))}</p>
          <p class="link"><a href="{html.escape(c.url)}" target="_blank" rel="noreferrer">打开比赛链接</a></p>
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
    .summary {{ line-height: 1.65; }}
    .meta, .risk, .evidence {{ color: #4b5563; line-height: 1.55; }}
    .link {{ margin: 10px 0; font-weight: 600; }}
    .tags span {{ display: inline-block; background: #e5e7eb; padding: 4px 8px; border-radius: 999px; margin: 3px; font-size: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>Static Feed Builder</h1>
    <p>自动生成公开机会订阅源、日历和移动端摘要。</p>
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
    return json.dumps([competition_to_digest_item(c) for c in comps], ensure_ascii=False, indent=2, default=str)
