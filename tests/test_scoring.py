import unittest

from scoring import infer_kind, score_opportunity


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.opportunity = {
            "title": "Scientist, Microbial Genomics",
            "description": "Full-time biotech role in metagenomics and drug discovery.",
            "organization": "Test Therapeutics",
            "location": "New York, NY",
        }

    def test_preferred_role_scores_strongly(self):
        score, reasons, topics = score_opportunity(self.opportunity, [])
        self.assertGreaterEqual(score, 60)
        self.assertIn("microbial genomics", topics)
        self.assertTrue(any(reason["type"] == "location" for reason in reasons))

    def test_penalties_are_applied_and_explained(self):
        opportunity = {**self.opportunity, "description": self.opportunity["description"] + " Unpaid internship."}
        baseline, _, _ = score_opportunity(opportunity, [])
        penalized, reasons, _ = score_opportunity(opportunity, [{"phrase": "unpaid", "weight": 30}])
        self.assertEqual(penalized, max(0, baseline - 30))
        self.assertIn({"label": "unpaid", "points": -30, "type": "penalty"}, reasons)

    def test_kind_inference(self):
        self.assertEqual(infer_kind("Join our protein structure seminar"), "event")
        self.assertEqual(infer_kind("Applications for a fellowship are open"), "fellowship")
        self.assertEqual(infer_kind("We are hiring a scientist"), "role")


if __name__ == "__main__":
    unittest.main()

