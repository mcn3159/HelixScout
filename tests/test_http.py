import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        environment = os.environ.copy()
        environment.update({
            "PORT": str(cls.port),
            "DATABASE_PATH": str(Path(cls.tempdir.name) / "http.db"),
            "ENABLE_BLUESKY": "false",
            "ENABLE_LINKEDIN_PUBLIC": "false",
            "X_BEARER_TOKEN": "",
        })
        cls.process = subprocess.Popen(
            ["python3", "app.py"], cwd=ROOT, env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/api/dashboard", timeout=.3)
                break
            except Exception:
                time.sleep(.05)
        else:
            raise RuntimeError("Test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=3)
        cls.tempdir.cleanup()

    def request_json(self, path, method="GET", payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_dashboard_and_preferences_flow(self):
        status, dashboard = self.request_json("/api/dashboard")
        self.assertEqual(status, 200)
        self.assertGreater(len(dashboard["opportunities"]), 0)
        status, updated = self.request_json(
            "/api/preferences", "PUT",
            {"penalties": [{"phrase": "unpaid", "weight": 30}], "min_score": 15},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["preferences"]["min_score"], 15)

    def test_static_app_is_served_with_csp(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=2) as response:
            body = response.read().decode()
            self.assertIn("Helix Scout", body)
            self.assertIn("Content-Security-Policy", response.headers)


if __name__ == "__main__":
    unittest.main()

