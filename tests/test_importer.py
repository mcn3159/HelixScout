import json
import unittest

from importer import parse_import


class ImporterTests(unittest.TestCase):
    def test_json_list(self):
        items = parse_import(json.dumps([{"title": "A seminar", "location": "NYC"}]), "json")
        self.assertEqual(items[0]["kind"], "event")
        self.assertEqual(items[0]["source"], "import")

    def test_csv(self):
        items = parse_import("title,organization,url\nScientist,Bio Co,https://example.com\n", "csv")
        self.assertEqual(items[0]["organization"], "Bio Co")

    def test_empty_import_rejected(self):
        with self.assertRaises(ValueError):
            parse_import("[]", "json")


if __name__ == "__main__":
    unittest.main()

