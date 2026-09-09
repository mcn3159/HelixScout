import tempfile
import unittest
from pathlib import Path

from database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.tempdir.name) / "test.db")
        self.item = {
            "source": "test",
            "external_id": "one",
            "title": "Computational Biology Scientist",
            "organization": "Bio Co",
            "location": "NYC",
            "description": "Full-time biotech metagenomics role",
            "posted_at": "2026-01-01T00:00:00+00:00",
            "url": "https://example.com/one",
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def test_upsert_is_deduplicated(self):
        self.database.upsert_opportunities([self.item])
        self.database.upsert_opportunities([{**self.item, "title": "Updated scientist title"}])
        items = self.database.list_opportunities()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Updated scientist title")

    def test_status_and_preferences_persist(self):
        self.database.upsert_opportunities([self.item])
        item = self.database.list_opportunities()[0]
        updated = self.database.update_status(item["id"], "saved")
        self.assertEqual(updated["status"], "saved")
        before = updated["score"]
        preferences = self.database.save_preferences([{"phrase": "metagenomics", "weight": 25}], 20)
        after = self.database.list_opportunities()[0]["score"]
        self.assertEqual(preferences["min_score"], 20)
        self.assertEqual(after, max(0, before - 25))

    def test_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            self.database.update_status(1, "deleted")

    def test_rescore_preserves_preferences_and_status_and_repairs_social_metadata(self):
        self.database.upsert_opportunities([
            {**self.item, "source": "x", "kind": "event", "description": "Join our team hiring in metagenomics", "location": "NYC"},
            {**self.item, "external_id": "two"},
        ])
        rows = self.database.list_opportunities()
        for item, status in zip(rows, ("saved", "dismissed")):
            self.database.update_status(item["id"], status)
        preferences = self.database.save_preferences([
            {"phrase": "ribosome", "weight": 20}, {"phrase": "powerful", "weight": 20},
        ], 15)
        before = {item["id"]: item["status"] for item in self.database.list_opportunities()}
        self.database.rescore_all()
        after = self.database.list_opportunities()
        self.assertEqual(before, {item["id"]: item["status"] for item in after})
        self.assertEqual(preferences, self.database.get_preferences())
        social = next(item for item in after if item["source"] == "x")
        self.assertEqual(social["kind"], "role")
        self.assertEqual(social["location"], "")


if __name__ == "__main__":
    unittest.main()
