"""SQLite persistence for opportunities, scans, and user preferences."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from config import DATABASE_PATH, PENALTY_SUGGESTIONS
from scoring import infer_kind, score_opportunity


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path = DATABASE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'role',
                    title TEXT NOT NULL,
                    organization TEXT NOT NULL DEFAULT '',
                    author TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    posted_at TEXT NOT NULL,
                    found_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    topics_json TEXT NOT NULL DEFAULT '[]',
                    score INTEGER NOT NULL DEFAULT 0,
                    score_reasons_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'new',
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(source, external_id)
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    penalties_json TEXT NOT NULL DEFAULT '[]',
                    min_score INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scan_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    totals_json TEXT NOT NULL DEFAULT '{}',
                    errors_json TEXT NOT NULL DEFAULT '[]'
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO preferences (id, penalties_json, min_score, updated_at) VALUES (1, '[]', 0, ?)",
                (utc_now(),),
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        for column, target in (("topics_json", "topics"), ("score_reasons_json", "score_reasons"), ("raw_json", "raw")):
            item[target] = json.loads(item.pop(column, "[]" if column != "raw_json" else "{}"))
        item["is_demo"] = bool(item["is_demo"])
        return item

    def get_preferences(self) -> Dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM preferences WHERE id = 1").fetchone()
        return {
            "penalties": json.loads(row["penalties_json"]),
            "min_score": row["min_score"],
            "suggestions": PENALTY_SUGGESTIONS,
            "updated_at": row["updated_at"],
        }

    def save_preferences(self, penalties: List[Dict[str, Any]], min_score: int = 0) -> Dict[str, Any]:
        cleaned = []
        seen = set()
        for penalty in penalties[:30]:
            phrase = " ".join(str(penalty.get("phrase", "")).strip().lower().split())[:80]
            if not phrase or phrase in seen:
                continue
            seen.add(phrase)
            cleaned.append({"phrase": phrase, "weight": max(1, min(50, abs(int(penalty.get("weight", 10)))) )})
        with self.connect() as connection:
            connection.execute(
                "UPDATE preferences SET penalties_json = ?, min_score = ?, updated_at = ? WHERE id = 1",
                (json.dumps(cleaned), max(0, min(100, int(min_score))), utc_now()),
            )
        self.rescore_all()
        return self.get_preferences()

    def upsert_opportunities(self, items: Iterable[Dict[str, Any]], is_demo: bool = False) -> int:
        penalties = self.get_preferences()["penalties"]
        count = 0
        with self.connect() as connection:
            for incoming in items:
                item = dict(incoming)
                combined = f"{item.get('title', '')} {item.get('description', '')}"
                item["kind"] = item.get("kind") or infer_kind(combined)
                score, reasons, topics = score_opportunity(item, penalties)
                external_id = str(item.get("external_id") or item.get("url") or hash(combined))
                connection.execute(
                    """
                    INSERT INTO opportunities (
                        source, external_id, kind, title, organization, author, location,
                        posted_at, found_at, url, description, topics_json, score,
                        score_reasons_json, is_demo, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, external_id) DO UPDATE SET
                        kind=excluded.kind, title=excluded.title, organization=excluded.organization,
                        author=excluded.author, location=excluded.location, posted_at=excluded.posted_at,
                        found_at=excluded.found_at, url=excluded.url, description=excluded.description,
                        topics_json=excluded.topics_json, score=excluded.score,
                        score_reasons_json=excluded.score_reasons_json, raw_json=excluded.raw_json
                    """,
                    (
                        item.get("source", "import"), external_id, item["kind"],
                        str(item.get("title") or "Untitled opportunity")[:300],
                        str(item.get("organization") or "")[:200], str(item.get("author") or "")[:200],
                        str(item.get("location") or "")[:200], item.get("posted_at") or utc_now(), utc_now(),
                        str(item.get("url") or "")[:2000], str(item.get("description") or "")[:10000],
                        json.dumps(topics), score, json.dumps(reasons), int(is_demo or item.get("is_demo", False)),
                        json.dumps(item.get("raw", {}), ensure_ascii=False)[:50000],
                    ),
                )
                count += 1
        return count

    def list_opportunities(self) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM opportunities ORDER BY score DESC, posted_at DESC, id DESC"
            ).fetchall()
        return [self._decode(row) for row in rows]

    def update_status(self, opportunity_id: int, status: str) -> Optional[Dict[str, Any]]:
        if status not in {"new", "saved", "dismissed"}:
            raise ValueError("Invalid status")
        with self.connect() as connection:
            connection.execute("UPDATE opportunities SET status = ? WHERE id = ?", (status, opportunity_id))
            row = connection.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        return self._decode(row) if row else None

    def rescore_all(self) -> None:
        penalties = self.get_preferences()["penalties"]
        items = self.list_opportunities()
        with self.connect() as connection:
            for item in items:
                score, reasons, topics = score_opportunity(item, penalties)
                connection.execute(
                    "UPDATE opportunities SET score=?, score_reasons_json=?, topics_json=? WHERE id=?",
                    (score, json.dumps(reasons), json.dumps(topics), item["id"]),
                )

    def start_scan(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO scan_runs (started_at, status) VALUES (?, 'running')", (utc_now(),)
            )
            return int(cursor.lastrowid)

    def finish_scan(self, scan_id: int, totals: Dict[str, int], errors: List[Dict[str, str]]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE scan_runs SET finished_at=?, status=?, totals_json=?, errors_json=? WHERE id=?",
                (utc_now(), "partial" if errors else "complete", json.dumps(totals), json.dumps(errors), scan_id),
            )

    def latest_scan(self) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        result = dict(row)
        result["totals"] = json.loads(result.pop("totals_json"))
        result["errors"] = json.loads(result.pop("errors_json"))
        return result

    def stats(self) -> Dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) total,
                    SUM(CASE WHEN status='saved' THEN 1 ELSE 0 END) saved,
                    SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) new_count,
                    SUM(CASE WHEN kind='event' THEN 1 ELSE 0 END) events,
                    SUM(CASE WHEN is_demo=1 THEN 1 ELSE 0 END) demos,
                    ROUND(AVG(score)) average_score
                    FROM opportunities"""
            ).fetchone()
        return {key: (value or 0) for key, value in dict(row).items()}

