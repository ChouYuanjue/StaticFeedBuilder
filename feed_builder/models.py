from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Competition:
    title: str
    url: str
    source: str
    tags: list[str] = field(default_factory=list)
    organizer: str | None = None
    venue: str | None = None
    description: str | None = None
    mode: str = "unknown"  # online / hybrid / onsite / unknown
    registration_deadline: datetime | None = None
    submission_deadline: datetime | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    fee: str = "unknown"  # free / low / high / unknown
    team_size: str | None = None
    school_required: str = "unknown"  # yes / no / unknown
    affiliation_required: str = "unknown"
    ai_policy: str = "unknown"  # allowed / forbidden / unknown
    external_data_policy: str = "unknown"
    deliverable: str | None = None
    authority_score: float = 50
    feasibility_score: float = 50
    low_cost_score: float = 50
    ai_friendliness_score: float = 50
    info_gap_score: float = 50
    time_window_score: float = 50
    portfolio_value_score: float = 50
    final_score: float = 0
    risk_flags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def deadline(self) -> datetime | None:
        return self.submission_deadline or self.registration_deadline or self.end_at or self.start_at

    def normalized_key(self) -> str:
        safe_title = " ".join(self.title.lower().strip().split())
        return f"{safe_title}|{self.url.lower().split('?')[0].rstrip('/')}"

