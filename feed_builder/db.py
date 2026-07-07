from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import PROJECT_ROOT, Settings
from .models import Competition


def _db_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// DATABASE_URL is supported in this MVP")
    raw = database_url.replace("sqlite:///", "", 1)
    p = Path(raw)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def connect(settings: Settings) -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(settings.database_url))
    con.row_factory = sqlite3.Row
    return con


def init_db(settings: Settings) -> None:
    with connect(settings) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS competitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                normalized_key TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                tags TEXT NOT NULL,
                organizer TEXT,
                venue TEXT,
                description TEXT,
                mode TEXT,
                registration_deadline TEXT,
                submission_deadline TEXT,
                start_at TEXT,
                end_at TEXT,
                fee TEXT,
                team_size TEXT,
                school_required TEXT,
                affiliation_required TEXT,
                ai_policy TEXT,
                external_data_policy TEXT,
                deliverable TEXT,
                authority_score REAL,
                feasibility_score REAL,
                low_cost_score REAL,
                ai_friendliness_score REAL,
                info_gap_score REAL,
                time_window_score REAL,
                portfolio_value_score REAL,
                final_score REAL,
                risk_flags TEXT NOT NULL,
                evidence TEXT NOT NULL,
                raw TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_competitions_score ON competitions(final_score DESC);
            CREATE INDEX IF NOT EXISTS idx_competitions_deadline ON competitions(submission_deadline, registration_deadline, end_at);
            CREATE INDEX IF NOT EXISTS idx_competitions_source ON competitions(source);
            """
        )


def _dt(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def upsert_competitions(settings: Settings, comps: Iterable[Competition]) -> int:
    rows = 0
    with connect(settings) as con:
        for c in comps:
            rows += 1
            con.execute(
                """
                INSERT INTO competitions (
                    normalized_key, title, url, source, tags, organizer, venue, description, mode,
                    registration_deadline, submission_deadline, start_at, end_at, fee, team_size,
                    school_required, affiliation_required, ai_policy, external_data_policy, deliverable,
                    authority_score, feasibility_score, low_cost_score, ai_friendliness_score,
                    info_gap_score, time_window_score, portfolio_value_score, final_score,
                    risk_flags, evidence, raw, discovered_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_key) DO UPDATE SET
                    title=excluded.title,
                    url=excluded.url,
                    source=excluded.source,
                    tags=excluded.tags,
                    organizer=excluded.organizer,
                    venue=excluded.venue,
                    description=excluded.description,
                    mode=excluded.mode,
                    registration_deadline=excluded.registration_deadline,
                    submission_deadline=excluded.submission_deadline,
                    start_at=excluded.start_at,
                    end_at=excluded.end_at,
                    fee=excluded.fee,
                    team_size=excluded.team_size,
                    school_required=excluded.school_required,
                    affiliation_required=excluded.affiliation_required,
                    ai_policy=excluded.ai_policy,
                    external_data_policy=excluded.external_data_policy,
                    deliverable=excluded.deliverable,
                    authority_score=excluded.authority_score,
                    feasibility_score=excluded.feasibility_score,
                    low_cost_score=excluded.low_cost_score,
                    ai_friendliness_score=excluded.ai_friendliness_score,
                    info_gap_score=excluded.info_gap_score,
                    time_window_score=excluded.time_window_score,
                    portfolio_value_score=excluded.portfolio_value_score,
                    final_score=excluded.final_score,
                    risk_flags=excluded.risk_flags,
                    evidence=excluded.evidence,
                    raw=excluded.raw,
                    updated_at=excluded.updated_at
                """,
                (
                    c.normalized_key(),
                    c.title,
                    c.url,
                    c.source,
                    json.dumps(c.tags, ensure_ascii=False),
                    c.organizer,
                    c.venue,
                    c.description,
                    c.mode,
                    _dt(c.registration_deadline),
                    _dt(c.submission_deadline),
                    _dt(c.start_at),
                    _dt(c.end_at),
                    c.fee,
                    c.team_size,
                    c.school_required,
                    c.affiliation_required,
                    c.ai_policy,
                    c.external_data_policy,
                    c.deliverable,
                    c.authority_score,
                    c.feasibility_score,
                    c.low_cost_score,
                    c.ai_friendliness_score,
                    c.info_gap_score,
                    c.time_window_score,
                    c.portfolio_value_score,
                    c.final_score,
                    json.dumps(c.risk_flags, ensure_ascii=False),
                    json.dumps(c.evidence, ensure_ascii=False),
                    json.dumps(c.raw, ensure_ascii=False, default=str),
                    _dt(c.discovered_at) or datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
    return rows


def row_to_competition(row: sqlite3.Row) -> Competition:
    return Competition(
        title=row["title"],
        url=row["url"],
        source=row["source"],
        tags=json.loads(row["tags"] or "[]"),
        organizer=row["organizer"],
        venue=row["venue"],
        description=row["description"],
        mode=row["mode"] or "unknown",
        registration_deadline=_parse_dt(row["registration_deadline"]),
        submission_deadline=_parse_dt(row["submission_deadline"]),
        start_at=_parse_dt(row["start_at"]),
        end_at=_parse_dt(row["end_at"]),
        fee=row["fee"] or "unknown",
        team_size=row["team_size"],
        school_required=row["school_required"] or "unknown",
        affiliation_required=row["affiliation_required"] or "unknown",
        ai_policy=row["ai_policy"] or "unknown",
        external_data_policy=row["external_data_policy"] or "unknown",
        deliverable=row["deliverable"],
        authority_score=row["authority_score"] or 0,
        feasibility_score=row["feasibility_score"] or 0,
        low_cost_score=row["low_cost_score"] or 0,
        ai_friendliness_score=row["ai_friendliness_score"] or 0,
        info_gap_score=row["info_gap_score"] or 0,
        time_window_score=row["time_window_score"] or 0,
        portfolio_value_score=row["portfolio_value_score"] or 0,
        final_score=row["final_score"] or 0,
        risk_flags=json.loads(row["risk_flags"] or "[]"),
        evidence=json.loads(row["evidence"] or "[]"),
        raw=json.loads(row["raw"] or "{}"),
        discovered_at=_parse_dt(row["discovered_at"]) or datetime.utcnow(),
        updated_at=_parse_dt(row["updated_at"]) or datetime.utcnow(),
    )


def list_recommendations(settings: Settings, days_ahead: int, min_score: float, limit: int) -> list[Competition]:
    now = datetime.utcnow()
    max_dt = now.timestamp() + days_ahead * 24 * 3600
    with connect(settings) as con:
        rows = con.execute(
            """
            SELECT * FROM competitions
            WHERE final_score >= ?
            ORDER BY final_score DESC, updated_at DESC
            LIMIT ?
            """,
            (min_score, max(limit * 4, limit)),
        ).fetchall()
    comps = []
    for row in rows:
        c = row_to_competition(row)
        dl = c.deadline()
        if dl is None or dl.timestamp() <= max_dt:
            comps.append(c)
        if len(comps) >= limit:
            break
    return comps

