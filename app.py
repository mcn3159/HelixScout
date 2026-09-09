#!/usr/bin/env python3
"""BigMoveFinder HTTP server. Run with: python3 app.py"""

from __future__ import annotations

import csv
import io
import json
import mimetypes
import re
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from config import PORT, ROOT, SCAN_INTERVAL_MINUTES
from connectors import connector_status
from database import Database
from importer import parse_import
from scanner import run_scan
from seed import seed_if_empty


STATIC_DIR = ROOT / "static"
database = Database()
seed_if_empty(database)
database.rescore_all()
scan_lock = threading.Lock()


def dashboard_payload() -> Dict[str, Any]:
    return {
        "opportunities": database.list_opportunities(),
        "preferences": database.get_preferences(),
        "stats": database.stats(),
        "sources": connector_status(),
        "latest_scan": database.latest_scan(),
    }


def scan_in_background() -> None:
    if not scan_lock.acquire(blocking=False):
        return
    try:
        run_scan(database)
    finally:
        scan_lock.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "HelixScout/1.0"

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message}, status)

    def read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length > 2_100_000:
            raise ValueError("Request is too large")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON") from exc

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/dashboard":
            self.send_json(dashboard_payload())
            return
        if path == "/api/export.csv":
            self.export_csv()
            return
        if path.startswith("/api/"):
            self.send_error_json("Not found", 404)
            return
        self.serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/scan":
                if scan_lock.locked():
                    self.send_json({"status": "already_running"}, HTTPStatus.CONFLICT)
                    return
                thread = threading.Thread(target=scan_in_background, name="helix-scan", daemon=True)
                thread.start()
                # Let the scan run insert its status before the first client poll.
                time.sleep(0.03)
                self.send_json({"status": "started"}, HTTPStatus.ACCEPTED)
                return
            if path == "/api/import":
                body = self.read_json()
                items = parse_import(str(body.get("content", "")), str(body.get("format", "json")))
                count = database.upsert_opportunities(items)
                self.send_json({"imported": count, "dashboard": dashboard_payload()}, HTTPStatus.CREATED)
                return
            self.send_error_json("Not found", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 422)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/preferences":
                body = self.read_json()
                preferences = database.save_preferences(body.get("penalties", []), body.get("min_score", 0))
                self.send_json({"preferences": preferences, "dashboard": dashboard_payload()})
                return
            self.send_error_json("Not found", 404)
        except (ValueError, TypeError) as exc:
            self.send_error_json(str(exc), 422)

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/opportunities/(\d+)", path)
        if not match:
            self.send_error_json("Not found", 404)
            return
        try:
            body = self.read_json()
            item = database.update_status(int(match.group(1)), str(body.get("status", "")))
            if not item:
                self.send_error_json("Opportunity not found", 404)
                return
            self.send_json({"opportunity": item, "stats": database.stats()})
        except ValueError as exc:
            self.send_error_json(str(exc), 422)

    def export_csv(self) -> None:
        output = io.StringIO()
        fields = ["title", "organization", "kind", "source", "location", "score", "status", "posted_at", "url", "description"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(database.list_opportunities())
        body = output.getvalue().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="helix-scout-opportunities.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in candidate.parents and candidate != STATIC_DIR.resolve():
            self.send_error(404)
            return
        if not candidate.is_file():
            # Client-side routes return the app shell; asset typos remain 404.
            if "." not in Path(relative).name:
                candidate = STATIC_DIR / "index.html"
            else:
                self.send_error(404)
                return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") or content_type == "application/javascript" else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; script-src 'self'; base-uri 'self'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)


def scheduler_loop() -> None:
    interval_seconds = SCAN_INTERVAL_MINUTES * 60
    while interval_seconds:
        time.sleep(interval_seconds)
        scan_in_background()


def main() -> None:
    if SCAN_INTERVAL_MINUTES:
        threading.Thread(target=scheduler_loop, name="helix-scheduler", daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"BigMoveFinder is running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping BigMoveFinder.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
