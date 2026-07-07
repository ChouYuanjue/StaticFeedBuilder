from __future__ import annotations

from datetime import datetime

from .models import Competition


def clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def score_competition(c: Competition, prefs: dict) -> Competition:
    weights = prefs.get("weights", {})
    preferred_tags = set(prefs.get("preferences", {}).get("preferred_tags", []))
    disliked_tags = set(prefs.get("preferences", {}).get("disliked_tags", []))
    tags = set(c.tags)

    risks = []

    # Feasibility
    feasibility = 55
    if c.mode == "online":
        feasibility += 25
    elif c.mode == "hybrid":
        feasibility += 10
    elif c.mode == "onsite":
        feasibility -= 40
        risks.append("可能需要线下/现场")

    if c.school_required == "yes":
        feasibility -= 30
        risks.append("可能需要学校/机构名义")
    if c.affiliation_required == "yes":
        feasibility -= 15
        risks.append("可能需要机构身份")

    # Cost
    low_cost = 55
    if c.fee == "free":
        low_cost += 30
    elif c.fee == "low":
        low_cost += 10
    elif c.fee == "high":
        low_cost -= 45
        risks.append("成本可能较高")

    # AI friendliness
    ai = 55
    if c.ai_policy == "allowed":
        ai += 30
    elif c.ai_policy == "forbidden":
        ai -= 55
        risks.append("规则可能禁止 AI/外部工具")
    elif any(t in tags for t in ["llm", "agents", "ai", "data_science", "cv", "nlp"]):
        ai += 8

    # Time window
    tw = 55
    deadline = c.deadline()
    if deadline:
        days = (deadline - datetime.utcnow()).days
        if days < 0:
            tw -= 35
            risks.append("可能已过截止日期")
        elif days <= 3:
            tw -= 10
        elif 4 <= days <= 45:
            tw += 30
        elif 46 <= days <= 120:
            tw += 18
        else:
            tw += 5

    # Portfolio value
    portfolio = 50
    if any(t in tags for t in ["conference", "workshop", "shared_task", "benchmark"]):
        portfolio += 30
    if any(t in tags for t in ["ctf", "hackathon"]):
        portfolio += 12
    if c.deliverable and any(x in c.deliverable.lower() for x in ["report", "writeup", "code", "model"]):
        portfolio += 10

    # Authority and info gap already seeded by source hints.
    authority = c.authority_score
    info_gap = c.info_gap_score

    # Tag tuning
    if preferred_tags & tags:
        info_gap += 6
        portfolio += 4
    if disliked_tags & tags:
        feasibility -= 15
        risks.append("命中不偏好的标签")

    c.feasibility_score = clamp(feasibility)
    c.low_cost_score = clamp(low_cost)
    c.ai_friendliness_score = clamp(ai)
    c.time_window_score = clamp(tw)
    c.portfolio_value_score = clamp(portfolio)
    c.authority_score = clamp(authority)
    c.info_gap_score = clamp(info_gap)

    c.final_score = round(
        weights.get("authority", 0.20) * c.authority_score
        + weights.get("feasibility", 0.18) * c.feasibility_score
        + weights.get("low_cost", 0.15) * c.low_cost_score
        + weights.get("ai_friendliness", 0.15) * c.ai_friendliness_score
        + weights.get("info_gap", 0.12) * c.info_gap_score
        + weights.get("time_window", 0.10) * c.time_window_score
        + weights.get("portfolio_value", 0.10) * c.portfolio_value_score,
        1,
    )

    # Hard filter as score penalty rather than deletion; the digest layer can skip if needed.
    hard = prefs.get("hard_filters", {})
    if hard.get("reject_onsite_only") and c.mode == "onsite":
        c.final_score = min(c.final_score, 35)
    if hard.get("reject_school_required") and c.school_required == "yes":
        c.final_score = min(c.final_score, 40)
    if hard.get("reject_high_fee") and c.fee == "high":
        c.final_score = min(c.final_score, 38)
    if hard.get("reject_ai_forbidden") and c.ai_policy == "forbidden":
        c.final_score = min(c.final_score, 30)

    c.risk_flags = sorted(set(c.risk_flags + risks))
    return c

