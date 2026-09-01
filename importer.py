"""Import user-controlled JSON or CSV opportunity lists."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from database import utc_now
from scoring import infer_kind


FIELDS = {"title", "organization", "author", "location", "posted_at", "url", "description", "kind", "source", "external_id"}


def parse_import(content: str, format_name: str = "json") -> List[Dict[str, Any]]:
    if len(content.encode("utf-8")) > 2_000_000:
        raise ValueError("Import is limited to 2 MB")
    if format_name.lower() == "csv":
        rows = list(csv.DictReader(io.StringIO(content)))
    else:
        payload = json.loads(content)
        rows = payload if isinstance(payload, list) else payload.get("opportunities", [])
    if not isinstance(rows, list):
        raise ValueError("Expected a list of opportunities")
    results = []
    for index, row in enumerate(rows[:1000]):
        if not isinstance(row, dict) or not str(row.get("title", "")).strip():
            continue
        item = {key: row.get(key, "") for key in FIELDS}
        item["source"] = str(item.get("source") or "import").lower()[:30]
        item["external_id"] = str(item.get("external_id") or item.get("url") or f"import-{index}-{hash(str(row))}")
        item["posted_at"] = item.get("posted_at") or utc_now()
        item["kind"] = item.get("kind") or infer_kind(f"{item.get('title')} {item.get('description')}")
        results.append(item)
    if not results:
        raise ValueError("No rows with a title were found")
    return results

