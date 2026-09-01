"""Transparent, deterministic relevance scoring."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from config import INDUSTRY_SIGNALS, NYC_SIGNALS, OPPORTUNITY_SIGNALS, TOPICS


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _matches(text: str, signals: Dict[str, int]) -> Iterable[Tuple[str, int]]:
    for phrase, points in signals.items():
        if normalize(phrase) in text:
            yield phrase, points


def infer_kind(text: str) -> str:
    value = normalize(text)
    if any(term in value for term in ("conference", "seminar", "symposium", "workshop", "register", "join us")):
        return "event"
    if any(term in value for term in ("fellowship", " fellow ", "fellow position")):
        return "fellowship"
    return "role"


def score_opportunity(opportunity: Dict[str, Any], penalties: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]], List[str]]:
    fields = [
        opportunity.get("title", ""),
        opportunity.get("description", ""),
        opportunity.get("organization", ""),
        opportunity.get("location", ""),
    ]
    text = normalize(" ".join(str(value) for value in fields if value))
    reasons: List[Dict[str, Any]] = []
    topics: List[str] = []

    # Within each category, exact synonyms should not inflate the score without bound.
    topic_hits = list(_matches(text, TOPICS))
    for phrase, points in topic_hits:
        if phrase.rstrip("s") not in [topic.rstrip("s") for topic in topics]:
            topics.append(phrase)
            reasons.append({"label": phrase, "points": points, "type": "topic"})

    for category, signals, cap in (
        ("opportunity", OPPORTUNITY_SIGNALS, 24),
        ("industry", INDUSTRY_SIGNALS, 15),
        ("location", NYC_SIGNALS, 22),
    ):
        hits = list(_matches(text, signals))
        if hits:
            best_phrase, best_points = max(hits, key=lambda item: item[1])
            total = min(cap, max(points for _, points in hits))
            reasons.append({"label": best_phrase, "points": total, "type": category})

    for penalty in penalties:
        phrase = normalize(str(penalty.get("phrase", "")))
        points = abs(int(penalty.get("weight", 0)))
        if phrase and points and phrase in text:
            reasons.append({"label": phrase, "points": -points, "type": "penalty"})

    total_score = max(0, min(100, sum(int(reason["points"]) for reason in reasons)))
    reasons.sort(key=lambda reason: abs(reason["points"]), reverse=True)
    return total_score, reasons, topics

