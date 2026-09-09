"""Transparent, deterministic relevance scoring."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from config import (
    BACTERIAL_CONTEXT, BIOLOGICAL_CONTEXT, BLUESKY_NO_CONTACT_PENALTY, EVENT_SIGNALS, FELLOWSHIP_SIGNALS,
    INDUSTRY_SIGNALS, NYC_SIGNALS, OPPORTUNITY_SIGNALS, RECRUITMENT_SIGNALS,
    TOPIC_CONCEPTS,
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    """Match phrases at word boundaries, including hyphenated spellings."""
    pattern = r"[\s\-–—]+".join(re.escape(part) for part in re.split(r"[\s\-–—]+", normalize(phrase)))
    return bool(re.search(r"(?<!\w)" + pattern + r"(?!\w)", normalize(text)))


def _any_match(text: str, phrases: Iterable[str]) -> bool:
    return any(contains_phrase(text, phrase) for phrase in phrases)


def _matches(text: str, signals: Dict[str, int]) -> Iterable[Tuple[str, int]]:
    for phrase, points in signals.items():
        if contains_phrase(text, phrase):
            yield phrase, points


def recruitment_hits(text: str) -> List[Tuple[str, int]]:
    # Search terms are deliberately broad; bare "job" and "position" also
    # describe enzyme functions, amino acids, opinions, and someone's current job.
    value = normalize(re.sub(r"https?://\S+|\bwww\.\S+", " ", text))
    if re.search(r"\bi(?:['’]m| am)?\b.{0,35}\b(?:seeking|looking for)\b.{0,65}\b(?:position|job|role)\b", value):
        return []
    hits = [(phrase, 20) for phrase in RECRUITMENT_SIGNALS
            if phrase not in {"job", "jobs", "position", "positions"} and contains_phrase(value, phrase)]
    title = r"(?:phd|ph\.d\.|postdoc|postdoctoral|post[ -]doc|research|scientist|researcher|engineer|faculty|assistant|associate|bioinformatician|biologist)"
    vacancy = re.search(
        rf"\b{title}(?:[\s,/–—-]+\w+){{0,3}}[\s-]+(?:position|positions|job|jobs)\b"
        r"|\b(?:job|jobs|position|positions)\s+(?:opening|openings|available|vacancy|vacancies|opportunity|opportunities|posting|postings|advert|advertisement)\b"
        r"|\b(?:open|available|funded|vacant|new)\s+(?:\w+\s+){0,2}(?:job|jobs|position|positions)\b"
        r"|\bposition\s+(?:will be|is)\s+based\b",
        value,
    )
    if vacancy:
        hits.append((vacancy.group(0), 20))
    return hits


def opportunity_hits(text: str) -> List[Tuple[str, int]]:
    hits = [(phrase, points) for phrase, points in _matches(text, OPPORTUNITY_SIGNALS) if points != 20]
    return hits + recruitment_hits(text)


def has_opportunity_evidence(text: str) -> bool:
    return bool(recruitment_hits(text)) or _any_match(text, EVENT_SIGNALS + FELLOWSHIP_SIGNALS)


def infer_kind(text: str) -> str:
    # Recruitment in a conference post is still a role; generic "join us" is
    # neither event nor recruitment evidence without a more specific phrase.
    if _any_match(text, FELLOWSHIP_SIGNALS):
        return "fellowship"
    if recruitment_hits(text):
        return "role"
    if _any_match(text, EVENT_SIGNALS):
        return "event"
    return "role"


def is_explicitly_remote(text: str) -> bool:
    value = normalize(text)
    if re.search(r"\b(?:not|no|non)[\s-]+remote\b|\bremote\s+(?:work\s+)?(?:is\s+)?(?:not|unavailable)\b", value):
        return False
    if value in {"remote", "remote only", "fully remote", "us remote", "remote, us"}:
        return True
    return bool(re.search(
        r"\b(?:fully[ -]remote|remote[ -](?:only|friendly|first|role|roles|position|positions|job|jobs|work|working|opportunity|opportunities|scientist|researcher|bioinformatician)|work\s+(?:fully\s+)?remotely|work\s+from\s+home)\b"
        r"|\b(?:location|workplace|hiring|position|role|job)\s*[:—–-]\s*remote\b"
        r"|(?:\(|#)remote\b",
        value,
    ))


def infer_location(text: str) -> str:
    for term in ("New York City", "New York, NY", "NYC", "Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island", "New York"):
        if contains_phrase(text, term):
            return term
    return "Remote" if is_explicitly_remote(text) else ""


def has_post_link_or_contact(opportunity: Dict[str, Any]) -> bool:
    """Look inside the post, never at its own permalink or author profile."""
    raw = opportunity.get("raw") or {}
    links = raw.get("post_links", []) if isinstance(raw, dict) else []
    if isinstance(links, list) and any(isinstance(link, str) and re.match(r"^(?:https?://|mailto:|at://)", link, re.I) for link in links):
        return True
    # Older/imported posts may only have text; recognize shortened display URLs,
    # bare domains, and email addresses, without mistaking @handles for links.
    text = normalize(str(opportunity.get("description") or ""))
    if re.search(r"\b(?:https?://|www\.)\S+|(?<![\w@])[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", text):
        return True
    if re.search(r"(?<![\w@.])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}(?![\w.])(?:/\S*)?", text):
        return True
    # Negated invitations should not count as a way to respond.
    text = re.sub(r"\b(?:do not|don't|don’t|cannot|can't|can’t|no)\s+(?:(?:dm|email|e-mail|message|contact)\s+(?:me|us)|dms?)\b", "", text)
    return bool(re.search(
        r"\b(?:dm|email|e-mail|message|contact)\s+(?:me|us)\b"
        r"|\b(?:send|drop)\s+(?:me|us)\s+(?:an?\s+)?(?:dm|message|email|e-mail)\b"
        r"|\b(?:my\s+)?dms?\s+(?:are\s+)?open\b"
        r"|\b(?:reach out|get in touch)\b",
        text,
    ))


def score_opportunity(opportunity: Dict[str, Any], penalties: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]], List[str]]:
    content = normalize(" ".join(str(opportunity.get(field) or "") for field in ("title", "description")))
    text = normalize(" ".join(str(opportunity.get(field) or "") for field in ("title", "description", "organization", "location")))
    reasons: List[Dict[str, Any]] = []
    topics: List[str] = []
    topic_total = 0
    for concept, (points, aliases) in TOPIC_CONCEPTS.items():
        matched = _any_match(content, aliases)
        if concept == "antibiotic resistance":
            matched |= contains_phrase(content, "AMR") and _any_match(content, BACTERIAL_CONTEXT)
        elif concept == "biological language models":
            matched |= _any_match(content, ("foundation model", "foundation models")) and _any_match(content, BIOLOGICAL_CONTEXT)
        elif concept == "gene function" and "bacterial gene function" in topics:
            matched = False  # The longer function phrase already earned points.
        if matched:
            topics.append(concept)
            awarded = min(points, 50 - topic_total)
            if awarded:
                reasons.append({"label": concept, "points": awarded, "type": "topic"})
                topic_total += awarded

    for category, signals, evidence in (
        ("opportunity", OPPORTUNITY_SIGNALS, content),
        ("industry", INDUSTRY_SIGNALS, text),
    ):
        hits = opportunity_hits(evidence) if category == "opportunity" else list(_matches(evidence, signals))
        if hits:
            phrase, points = max(hits, key=lambda hit: hit[1])
            reasons.append({"label": phrase, "points": points, "type": category})

    # Older X records used the author's location as a fallback. Only post text
    # supplies location evidence for X, including during a rescore of old rows.
    location = str(opportunity.get("location") or "") if opportunity.get("source") != "x" else ""
    location_hits = list(_matches(content + " " + normalize(location), NYC_SIGNALS))
    if location_hits:
        phrase, points = max(location_hits, key=lambda hit: hit[1])
        reasons.append({"label": phrase, "points": points, "type": "location"})
    elif is_explicitly_remote(content) or is_explicitly_remote(location):
        reasons.append({"label": "remote", "points": 18, "type": "location"})

    subtotal = sum(reason["points"] for reason in reasons)
    ceiling = 100 if opportunity.get("source") == "linkedin" or has_opportunity_evidence(content) else 35
    if subtotal > ceiling:
        label = "100-point cap" if ceiling == 100 else "No explicit opportunity evidence (35-point cap)"
        reasons.append({"label": label, "points": ceiling - subtotal, "type": "cap"})

    if opportunity.get("source") == "bluesky" and not has_post_link_or_contact(opportunity):
        reasons.append({"label": "No link or contact invitation in post", "points": -BLUESKY_NO_CONTACT_PENALTY, "type": "penalty"})

    for penalty in penalties:
        phrase = normalize(str(penalty.get("phrase", "")))
        points = abs(int(penalty.get("weight", 0)))
        if phrase and points and contains_phrase(text, phrase):
            reasons.append({"label": phrase, "points": -points, "type": "penalty"})

    total_score = max(0, min(100, sum(int(reason["points"]) for reason in reasons)))
    reasons.sort(key=lambda reason: abs(reason["points"]), reverse=True)
    return total_score, reasons, topics
