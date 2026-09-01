"""Scan orchestration with per-source failure isolation."""

from __future__ import annotations

from typing import Any, Dict

from connectors import all_connectors
from database import Database


def run_scan(database: Database) -> Dict[str, Any]:
    scan_id = database.start_scan()
    totals: Dict[str, int] = {}
    errors = []
    for connector in all_connectors():
        if not connector.configured:
            totals[connector.name] = 0
            continue
        try:
            items = connector.scan()
            totals[connector.name] = database.upsert_opportunities(items)
        except Exception as exc:  # source failures must not hide results from other sources
            totals[connector.name] = 0
            errors.append({"source": connector.name, "message": str(exc)[:300]})
    database.finish_scan(scan_id, totals, errors)
    return {"scan_id": scan_id, "totals": totals, "errors": errors}

