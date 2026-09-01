"""Opportunity source adapters.

Each connector returns a shared record shape and never touches persistence. Network
access is public/official and intentionally isolated so source changes fail softly.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional

from config import SEARCH_QUERIES, env_bool
from scoring import infer_kind


USER_AGENT = "HelixScout/1.0 (local opportunity research tool)"


class ConnectorError(RuntimeError):
    pass


def fetch_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 20) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise ConnectorError(str(exc)) from exc


def post_json(url: str, payload: Dict[str, Any], timeout: int = 20) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise ConnectorError(str(exc)) from exc


def fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise ConnectorError(str(exc)) from exc


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


class BlueskyConnector:
    name = "bluesky"

    @property
    def configured(self) -> bool:
        return env_bool("ENABLE_BLUESKY", True)

    def scan(self) -> List[Dict[str, Any]]:
        if not self.configured:
            return []
        records: Dict[str, Dict[str, Any]] = {}
        # Bluesky search does not support X's complete boolean syntax. Send focused phrases.
        queries = [
            '"computational biology" NYC', 'metagenomics "New York"',
            '"microbial genomics" job', '"protein language model" hiring',
            '"protein structure" seminar NYC', 'bioinformatics fellowship NYC',
        ]
        api_host = "https://public.api.bsky.app"
        auth_headers: Dict[str, str] = {}
        public_failed: Optional[Exception] = None
        for query_index, query in enumerate(queries):
            params = urllib.parse.urlencode({"q": query, "limit": 40, "sort": "latest"})
            try:
                payload = fetch_json(f"{api_host}/xrpc/app.bsky.feed.searchPosts?{params}", headers=auth_headers)
            except ConnectorError as exc:
                public_failed = exc
                identifier = os.getenv("BLUESKY_IDENTIFIER", "").strip()
                app_password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
                if query_index or not identifier or not app_password:
                    raise
                session = post_json(
                    "https://bsky.social/xrpc/com.atproto.server.createSession",
                    {"identifier": identifier, "password": app_password},
                )
                token = session.get("accessJwt")
                if not token:
                    raise ConnectorError("Bluesky session did not return an access token") from public_failed
                api_host = "https://bsky.social"
                auth_headers = {"Authorization": f"Bearer {token}"}
                payload = fetch_json(f"{api_host}/xrpc/app.bsky.feed.searchPosts?{params}", headers=auth_headers)
            for post in payload.get("posts", []):
                record = post.get("record", {})
                author = post.get("author", {})
                text = clean_text(str(record.get("text", "")))
                uri = str(post.get("uri", ""))
                rkey = uri.rsplit("/", 1)[-1]
                handle = author.get("handle", "")
                url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle and rkey else "https://bsky.app"
                records[uri or url] = {
                    "source": self.name,
                    "external_id": uri or url,
                    "kind": infer_kind(text),
                    "title": summarize_title(text),
                    "organization": author.get("displayName") or handle,
                    "author": f"@{handle}" if handle else "",
                    "location": infer_location(text),
                    "posted_at": record.get("createdAt") or post.get("indexedAt") or now_iso(),
                    "url": url,
                    "description": text,
                    "raw": {"likeCount": post.get("likeCount", 0), "repostCount": post.get("repostCount", 0)},
                }
        return list(records.values())


class XConnector:
    name = "x"

    @property
    def configured(self) -> bool:
        return bool(os.getenv("X_BEARER_TOKEN"))

    def scan(self) -> List[Dict[str, Any]]:
        token = os.getenv("X_BEARER_TOKEN")
        if not token:
            return []
        records: Dict[str, Dict[str, Any]] = {}
        for query in SEARCH_QUERIES:
            # Keep a meaningful margin under the self-serve query length limit.
            x_query = f"{query} -is:retweet lang:en"[:500]
            params = urllib.parse.urlencode({
                "query": x_query,
                "max_results": 50,
                "sort_order": "recency",
                "tweet.fields": "created_at,author_id,entities,public_metrics",
                "expansions": "author_id",
                "user.fields": "name,username,location",
            })
            payload = fetch_json(
                f"https://api.x.com/2/tweets/search/recent?{params}",
                headers={"Authorization": f"Bearer {token}"},
            )
            users = {user["id"]: user for user in payload.get("includes", {}).get("users", [])}
            for post in payload.get("data", []):
                user = users.get(post.get("author_id"), {})
                text = clean_text(post.get("text", ""))
                username = user.get("username", "")
                post_id = str(post.get("id", ""))
                records[post_id] = {
                    "source": self.name,
                    "external_id": post_id,
                    "kind": infer_kind(text),
                    "title": summarize_title(text),
                    "organization": user.get("name") or username,
                    "author": f"@{username}" if username else "",
                    "location": infer_location(text) or user.get("location", ""),
                    "posted_at": post.get("created_at") or now_iso(),
                    "url": f"https://x.com/{username}/status/{post_id}" if username else f"https://x.com/i/status/{post_id}",
                    "description": text,
                    "raw": {"metrics": post.get("public_metrics", {})},
                }
        return list(records.values())


class LinkedInCardParser(HTMLParser):
    """Small, defensive parser for LinkedIn's public job-card fragments."""

    def __init__(self) -> None:
        super().__init__()
        self.cards: List[Dict[str, str]] = []
        self.card: Optional[Dict[str, str]] = None
        self.capture: Optional[str] = None
        self.root_tag: Optional[str] = None
        self.root_depth = 0

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attributes = dict(attrs)
        classes = attributes.get("class", "")
        if self.card is None and tag in {"li", "div"} and "job-search-card" in classes:
            self.card = {"external_id": attributes.get("data-entity-urn", "")}
            self.root_tag = tag
            self.root_depth = 1
        elif self.card is not None and tag == self.root_tag:
            self.root_depth += 1
        if not self.card:
            return
        if tag == "a" and "base-card__full-link" in classes:
            self.card["url"] = attributes.get("href", "").split("?", 1)[0]
        elif "base-search-card__title" in classes:
            self.capture = "title"
        elif "base-search-card__subtitle" in classes:
            self.capture = "organization"
        elif "job-search-card__location" in classes:
            self.capture = "location"
        elif tag == "time":
            self.card["posted_at"] = attributes.get("datetime", "")

    def handle_data(self, data: str) -> None:
        if self.card is not None and self.capture:
            self.card[self.capture] = (self.card.get(self.capture, "") + " " + data).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h3", "h4", "span"}:
            self.capture = None
        if self.card is not None and tag == self.root_tag:
            self.root_depth -= 1
        if self.card is not None and self.root_depth == 0:
            if self.card.get("title") and self.card.get("url"):
                self.cards.append(self.card)
            self.card = None
            self.capture = None
            self.root_tag = None


class LinkedInPublicJobsConnector:
    name = "linkedin"

    @property
    def configured(self) -> bool:
        return env_bool("ENABLE_LINKEDIN_PUBLIC", True)

    def scan(self) -> List[Dict[str, Any]]:
        if not self.configured:
            return []
        keywords = [
            "computational biology", "metagenomics", "microbial genomics",
            "protein language model", "protein structure",
        ]
        records: Dict[str, Dict[str, Any]] = {}
        for index, keyword in enumerate(keywords):
            params = urllib.parse.urlencode({
                "keywords": keyword,
                "location": "New York City Metropolitan Area",
                "f_TPR": "r2592000",
                "position": 1,
                "pageNum": 0,
                "start": 0,
            })
            markup = fetch_text(f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{params}")
            parser = LinkedInCardParser()
            parser.feed(markup)
            for card in parser.cards:
                external_id = card.get("external_id") or card["url"]
                records[external_id] = {
                    "source": self.name,
                    "external_id": external_id,
                    "kind": "role",
                    "title": clean_text(card.get("title", "")),
                    "organization": clean_text(card.get("organization", "")),
                    "author": "",
                    "location": clean_text(card.get("location", "")),
                    "posted_at": card.get("posted_at") or now_iso(),
                    "url": card.get("url", ""),
                    "description": f"{card.get('title', '')} — {keyword}. Public LinkedIn job card; open the source for the full description.",
                    "raw": {},
                }
            if index < len(keywords) - 1:
                time.sleep(1.0)
        return list(records.values())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def infer_location(text: str) -> str:
    value = text.lower()
    for term in ("New York City", "New York, NY", "NYC", "Manhattan", "Brooklyn", "Queens", "Bronx"):
        if term.lower() in value:
            return term
    return ""


def summarize_title(text: str, limit: int = 105) -> str:
    value = clean_text(text)
    first = re.split(r"(?<=[.!?])\s+|\n", value, maxsplit=1)[0]
    if len(first) <= limit:
        return first or "Opportunity post"
    return first[: limit - 1].rsplit(" ", 1)[0] + "…"


def connector_status() -> List[Dict[str, Any]]:
    connectors = [XConnector(), LinkedInPublicJobsConnector(), BlueskyConnector()]
    notes = {
        "x": "Official API · token required",
        "linkedin": "Public jobs · best effort",
        "bluesky": "Public API · app-password fallback",
    }
    return [{"source": item.name, "configured": item.configured, "note": notes[item.name]} for item in connectors]


def all_connectors() -> Iterable[Any]:
    return [XConnector(), LinkedInPublicJobsConnector(), BlueskyConnector()]
