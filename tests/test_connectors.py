import unittest

from connectors import LinkedInCardParser, infer_location, summarize_title


class ConnectorParsingTests(unittest.TestCase):
    def test_linkedin_public_card_parser(self):
        parser = LinkedInCardParser()
        parser.feed(
            """
            <ul><li class="base-card job-search-card" data-entity-urn="urn:li:jobPosting:123">
              <a class="base-card__full-link" href="https://linkedin.com/jobs/view/123?tracking=abc"></a>
              <h3 class="base-search-card__title"> Scientist, Metagenomics </h3>
              <h4 class="base-search-card__subtitle"> Genome Co </h4>
              <span class="job-search-card__location"> New York, NY </span>
              <time datetime="2026-08-31"></time>
            </li></ul>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0]["title"].strip(), "Scientist, Metagenomics")
        self.assertEqual(parser.cards[0]["url"], "https://linkedin.com/jobs/view/123")

    def test_text_helpers(self):
        self.assertEqual(infer_location("Meet us in Brooklyn for a seminar"), "Brooklyn")
        self.assertLessEqual(len(summarize_title("word " * 100)), 105)


if __name__ == "__main__":
    unittest.main()

