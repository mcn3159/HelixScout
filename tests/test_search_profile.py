import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from config import X_SEARCH_QUERIES
from connectors import BlueskyConnector, ConnectorError, XConnector, validated_x_query
from scoring import contains_phrase, has_opportunity_evidence, infer_kind, score_opportunity


def score(text, **fields):
    return score_opportunity({"description": text, **fields}, [])


def params(mock, index=0):
    return parse_qs(urlparse(mock.call_args_list[index].args[0]).query)


class ProfileTests(unittest.TestCase):
    def test_core_specialties_beat_generic_research(self):
        paper = score("Our computational biology bioinformatics protein structure foundation models paper, NYC")[0]
        self.assertEqual(paper, 35)
        for specialty in ("antibiotic resistance", "bacterial gene function prediction", "genomic language models", "metagenomics"):
            with self.subTest(specialty=specialty):
                self.assertGreater(score(f"Hiring scientist in {specialty}, biotech, NYC")[0], paper)

    def test_aliases_count_once_and_topics_cap_at_50(self):
        for phrase, aliases in (
            ("antibiotic resistance", "antimicrobial resistance resistome bacterial AMR"),
            ("protein language model", "protein language models genomic language models DNA language model"),
            ("metagenomics", "metagenomic microbiome"),
            ("bacterial gene function", "gene function prediction bacterial genetics functional annotation"),
        ):
            self.assertEqual(score("Hiring " + phrase)[0], score("Hiring " + phrase + " " + aliases)[0])
        _, reasons, topics = score("Hiring antibiotic resistance metagenomics genomic language models bacterial genetics microbial genomics")
        self.assertEqual(sum(r["points"] for r in reasons if r["type"] == "topic"), 50)
        self.assertEqual(len(topics), 5)

    def test_ambiguous_terms_need_biological_context(self):
        self.assertEqual(score("Hiring AMR foundation model engineer")[2], [])
        self.assertIn("antibiotic resistance", score("Hiring bacterial AMR scientist")[2])
        self.assertIn("biological language models", score("Hiring foundation model scientist for protein biology")[2])

    def test_phrase_boundaries_and_kind(self):
        self.assertFalse(contains_phrase("international internship", "intern"))
        self.assertTrue(contains_phrase("an intern position", "intern"))
        self.assertTrue(contains_phrase("gene-function prediction", "gene function prediction"))
        self.assertEqual(infer_kind("Join our team at the metagenomics conference; hiring scientists"), "role")
        self.assertEqual(infer_kind("Join us to read a paper"), "role")
        self.assertEqual(infer_kind("Genomics networking meetup"), "event")
        self.assertEqual(infer_kind("Fellowship applications open"), "fellowship")

    @patch("scoring.NYC_SIGNALS", {"nyc": 22})
    def test_location_preference_and_author_location(self):
        text = "Hiring metagenomics scientist"
        baseline = score(text)[0]
        self.assertEqual(score(text, location="NYC")[0], baseline + 22)
        self.assertEqual(score(text, location="Remote")[0], baseline + 18)
        self.assertEqual(score(text + " fully remote in NYC")[0], baseline + 22)
        self.assertEqual(score(text, location="San Francisco")[0], baseline)
        self.assertEqual(score(text, source="x", location="NYC")[0], baseline)
        self.assertEqual(score(text + " NYC", source="x")[0], baseline + 22)
        for suffix in ("remote sensing", "not remote", "no remote work", "non-remote role"):
            self.assertEqual(score(text + " " + suffix)[0], baseline)
        self.assertEqual(score(text + " remote role")[0], baseline + 18)

    def test_caps_precede_preserved_penalties(self):
        for text in (
            "Hiring antibiotic resistance metagenomics scientist biotech NYC powerful ribosome",
            "Antibiotic resistance metagenomics paper NYC powerful ribosome",
        ):
            item = {"description": text}
            baseline = score_opportunity(item, [])[0]
            for phrase in ("ribosome", "powerful"):
                result, reasons, _ = score_opportunity(item, [{"phrase": phrase, "weight": 20}])
                self.assertEqual(result, baseline - 20)
                self.assertIn({"label": phrase, "points": -20, "type": "penalty"}, reasons)
            result = score_opportunity(item, [{"phrase": p, "weight": 20} for p in ("ribosome", "powerful")])[0]
            self.assertEqual(result, max(0, baseline - 40))

    @patch("scoring.FELLOWSHIP_SIGNALS", ("fellowship", "fellowships"))
    def test_research_uses_of_job_and_position_are_not_recruitment(self):
        for text in (
            "Most gut microbe enzymes have no known job. A protein language model maps the metagenomics data.",
            "Protein language model positions which covary are useful targets for protein engineering.",
            "A position paper about microbiome-based medicines.",
            "Part of my job is studying the microbiome.",
            "Substantiate your position with credible microbiome research.",
            "I am actively seeking a fully funded PhD position in antimicrobial resistance.",
        ):
            with self.subTest(text=text):
                self.assertFalse(has_opportunity_evidence(text))
                self.assertLessEqual(score(text)[0], 35)
        for text in (
            "A fully funded PhD position in metagenomics",
            "Postdoctoral Research Position in Microbiology",
            "New AI Job: foundation models in biology",
            "The position will be based in a bacterial pathogens research team",
        ):
            self.assertTrue(has_opportunity_evidence(text))
        self.assertEqual(infer_kind("Our microbiome seminar speaker is an ARC Fellow"), "event")


class SocialSearchTests(unittest.TestCase):
    def test_configured_x_queries_are_valid(self):
        self.assertEqual(len(X_SEARCH_QUERIES), 8)
        for query in X_SEARCH_QUERIES.values():
            self.assertLessEqual(len(validated_x_query(query)), 512)
        for query in ("x" * 500, '("metagenomics"', '"metagenomics', ')metagenomics('):
            with self.assertRaises(ConnectorError):
                validated_x_query(query)

    @patch.dict(os.environ, {"X_BEARER_TOKEN": "test"})
    @patch("connectors.X_SEARCH_QUERIES", {"a:roles": "metagenomics hiring", "b:roles": "resistome hiring"})
    @patch("connectors.fetch_json")
    def test_x_pagination_dedup_attribution_and_location(self, fetch):
        post = {"id": "1", "text": "Hiring metagenomics scientist", "author_id": "a"}
        payload = {"data": [post], "includes": {"users": [{"id": "a", "username": "test", "location": "NYC"}]}, "meta": {"next_token": "more"}}
        fetch.return_value = payload
        items = XConnector().scan()
        self.assertEqual(fetch.call_count, 4)  # Two pages per query, even with more available.
        self.assertNotIn("next_token", params(fetch, 0))
        self.assertEqual(params(fetch, 1)["next_token"], ["more"])
        self.assertNotIn("next_token", params(fetch, 2))
        self.assertEqual(params(fetch)["max_results"], ["50"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["location"], "")
        self.assertEqual(items[0]["raw"]["matched_queries"], ["a:roles", "b:roles"])

    @patch.dict(os.environ, {"X_BEARER_TOKEN": "test"})
    @patch("connectors.X_SEARCH_QUERIES", {"bad": "x" * 500})
    @patch("connectors.fetch_json")
    def test_invalid_x_query_fails_before_request(self, fetch):
        with self.assertRaises(ConnectorError):
            XConnector().scan()
        fetch.assert_not_called()

    @patch.dict(os.environ, {"X_BEARER_TOKEN": "test"})
    @patch("connectors.X_SEARCH_QUERIES", {"test": "metagenomics hiring"})
    @patch("connectors.fetch_json")
    def test_x_uses_full_long_post_text(self, fetch):
        full = "Hiring a scientist in metagenomics, fully remote"
        fetch.return_value = {"data": [{"id": "1", "text": "Hiring a scientist…", "note_tweet": {"text": full}}]}
        item = XConnector().scan()[0]
        self.assertEqual(item["description"], full)
        self.assertEqual(item["location"], "Remote")
        fetch.return_value["data"][0]["note_tweet"]["text"] = "word " * 2500
        self.assertEqual(len(XConnector().scan()[0]["description"]), 10000)

    @staticmethod
    def bsky_post(key, text):
        return {"uri": f"at://did:plc:test/app.bsky.feed.post/{key}", "record": {"text": text, "createdAt": datetime.now(timezone.utc).isoformat()}, "author": {"handle": "test.bsky.social"}}

    @patch.dict(os.environ, {"ENABLE_BLUESKY": "true"})
    @patch("connectors.BLUESKY_SEARCH_QUERIES", {"metagenomics:one": '"metagenomics"', "metagenomics:two": '"microbiome"'})
    @patch("connectors.fetch_json")
    def test_bluesky_freshness_pagination_and_local_filter(self, fetch):
        role = self.bsky_post("1", "Hiring metagenomics scientist, fully remote")
        paper = self.bsky_post("2", "New metagenomics paper published today")
        event = self.bsky_post("3", "Metagenomics workshop in NYC")
        noise = self.bsky_post("4", "Hiring foundation model engineer for finance")
        fetch.return_value = {"posts": [role, paper, event, noise], "cursor": "more"}
        items = BlueskyConnector().scan()
        self.assertEqual(fetch.call_count, 4)
        request = params(fetch)
        self.assertEqual(request["q"], ['"metagenomics"'])
        self.assertEqual(request["limit"], ["40"])
        self.assertEqual(request["lang"], ["en"])
        self.assertEqual(request["sort"], ["latest"])
        since = datetime.fromisoformat(request["since"][0])
        self.assertLess(abs((datetime.now(timezone.utc) - timedelta(days=30) - since).total_seconds()), 5)
        self.assertEqual(params(fetch, 1)["cursor"], ["more"])
        self.assertNotIn("cursor", params(fetch, 2))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["location"], "Remote")
        self.assertEqual(items[0]["raw"]["matched_queries"], ["metagenomics:one:roles", "metagenomics:two:roles"])
        self.assertEqual(items[1]["kind"], "event")

    @patch.dict(os.environ, {"ENABLE_BLUESKY": "true", "BLUESKY_IDENTIFIER": "test", "BLUESKY_APP_PASSWORD": "test"})
    @patch("connectors.BLUESKY_SEARCH_QUERIES", {"test": '"metagenomics"'})
    @patch("connectors.post_json", return_value={"accessJwt": "test-token"})
    @patch("connectors.fetch_json")
    def test_bluesky_authenticated_fallback_keeps_filters(self, fetch, login):
        fetch.side_effect = [ConnectorError("denied"), {"posts": []}]
        self.assertEqual(BlueskyConnector().scan(), [])
        login.assert_called_once()
        self.assertEqual(params(fetch, 0), params(fetch, 1))
        self.assertEqual(urlparse(fetch.call_args_list[1].args[0]).netloc, "bsky.social")
        self.assertEqual(fetch.call_args_list[1].kwargs["headers"], {"Authorization": "Bearer test-token"})

    @patch.dict(os.environ, {"X_BEARER_TOKEN": "test", "ENABLE_BLUESKY": "true"})
    @patch("connectors.X_SEARCH_QUERIES", {"test": "metagenomics hiring"})
    @patch("connectors.BLUESKY_SEARCH_QUERIES", {"test": '"metagenomics"'})
    @patch("connectors.fetch_json", return_value={})
    def test_empty_results_stop_without_extra_pages(self, fetch):
        self.assertEqual(XConnector().scan(), [])
        self.assertEqual(BlueskyConnector().scan(), [])
        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
