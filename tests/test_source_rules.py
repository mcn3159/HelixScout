import os
import unittest
from unittest.mock import patch

from connectors import BlueskyConnector, bluesky_post_links
from scoring import has_post_link_or_contact, score_opportunity


class SourceRuleTests(unittest.TestCase):
    def setUp(self):
        self.item = {
            'source': 'bluesky',
            'title': 'Scientist, Metagenomics',
            'description': 'Hiring a metagenomics scientist, biotech, NYC.',
            'url': 'https://bsky.app/profile/example.bsky.social/post/one',
        }

    def test_linkedin_is_exempt_from_missing_evidence_cap(self):
        item = {**self.item, 'description': 'Metagenomics and antibiotic resistance, biotech, NYC.'}
        linkedin_score, reasons, _ = score_opportunity({**item, 'source': 'linkedin'}, [])
        self.assertGreater(linkedin_score, 35)
        self.assertFalse(any('No explicit opportunity evidence' in r['label'] for r in reasons))
        for source in ('x', 'bluesky'):
            result, reasons, _ = score_opportunity({**item, 'source': source}, [])
            self.assertLessEqual(result, 35)
            self.assertTrue(any('No explicit opportunity evidence' in r['label'] for r in reasons))
        penalized = score_opportunity({**item, 'source': 'linkedin'}, [{'phrase': 'metagenomics', 'weight': 20}])[0]
        self.assertEqual(penalized, linkedin_score - 20)

    def test_only_bluesky_gets_missing_contact_penalty(self):
        base = score_opportunity({**self.item, 'source': 'x'}, [])[0]
        result, reasons, _ = score_opportunity(self.item, [])
        self.assertEqual(result, base - 20)
        self.assertIn({'label': 'No link or contact invitation in post', 'points': -20, 'type': 'penalty'}, reasons)
        self.assertEqual(score_opportunity({**self.item, 'source': 'linkedin'}, [])[0], base)
        self.assertEqual(score_opportunity(self.item, [{'phrase': 'metagenomics', 'weight': 20}])[0], base - 40)

    def test_either_link_or_contact_is_sufficient(self):
        baseline = score_opportunity({**self.item, 'source': 'x'}, [])[0]
        for suffix in (
            'Apply at https://example.com/jobs/123', 'example.org/apply',
            'forms.gle/abc...', 'Email me', 'E-mail us', 'DM me for details',
            'Send us a DM', 'Drop me a message', 'My DMs are open', 'DMs open',
            'Message us', 'Reach out for details', 'Get in touch', 'Contact me',
            'researcher@example.edu',
        ):
            with self.subTest(suffix=suffix):
                item = {**self.item, 'description': self.item['description'] + ' ' + suffix}
                self.assertTrue(has_post_link_or_contact(item))
                self.assertEqual(score_opportunity(item, [])[0], baseline)
        both = {**self.item, 'description': self.item['description'] + ' DM me https://example.org/jobs'}
        self.assertEqual(score_opportunity(both, [])[0], baseline)

    def test_permalink_mentions_and_negated_invites_do_not_count(self):
        for suffix in ('', '@example.bsky.social', 'Link in bio', 'Do not DM me', "Don't email me", 'My DMs are closed'):
            with self.subTest(suffix=suffix):
                self.assertFalse(has_post_link_or_contact({**self.item, 'description': self.item['description'] + ' ' + suffix}))

    def test_embedded_and_faceted_links_count(self):
        quote = 'at://did:plc:example/app.bsky.feed.post/one'
        for embed in (
            {'external': {'uri': 'https://example.org/apply'}},
            {'media': {'external': {'uri': 'https://example.org/apply'}}},
            {'record': {'uri': quote}},
        ):
            post = {'record': {'embed': embed}}
            links = bluesky_post_links(post)
            self.assertEqual(len(links), 1)
            self.assertTrue(has_post_link_or_contact({**self.item, 'raw': {'post_links': links}}))
        facet = {'features': [{'$type': 'app.bsky.richtext.facet#link', 'uri': 'https://example.org/apply'}]}
        post = {'record': {'facets': [facet]}, 'embed': {'external': {'uri': 'https://example.org/apply'}}}
        self.assertEqual(bluesky_post_links(post), ['https://example.org/apply'])
        self.assertEqual(bluesky_post_links({'record': {}, 'embed': {'images': [{'fullsize': 'https://example.org/photo'}]}}), [])

    @patch.dict(os.environ, {'ENABLE_BLUESKY': 'true'})
    @patch('connectors.BLUESKY_SEARCH_QUERIES', {'test': 'metagenomics'})
    @patch('connectors.fetch_json')
    def test_connector_preserves_post_links_for_scoring(self, fetch):
        fetch.return_value = {'posts': [{
            'uri': 'at://did:plc:example/app.bsky.feed.post/one',
            'record': {'text': self.item['description'], 'embed': {'external': {'uri': 'https://example.org/apply'}}},
            'author': {'handle': 'example.bsky.social'},
        }]}
        item = BlueskyConnector().scan()[0]
        self.assertEqual(item['raw']['post_links'], ['https://example.org/apply'])
        self.assertFalse(any(r['label'] == 'No link or contact invitation in post' for r in score_opportunity(item, [])[1]))


if __name__ == '__main__':
    unittest.main()
