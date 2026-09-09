# Social search validation — September 9, 2026

The implemented profile searches antibiotic resistance, bacterial gene function,
biological language models, and metagenomics, with NYC/remote ranking preferences.
Both platforms now read their queries from configuration. Scanning remains manual.

## Validation

- Full suite: 28 tests passed, including HTTP integration tests and the corrected
  BigMoveFinder branding assertion. The initial HTTP startup timeout did not recur
  on the focused or full rerun.
- After the final long-post storage-limit adjustment, all 14 search-profile tests
  passed again. `git diff --check` passed.
- Synthetic antibiotic-resistance hiring example: 44 before, 77 after.
  Metagenomics hiring example: 69 before, 77 after. Generic methods-paper example:
  89 before, 35 after. These examples have no user penalties applied.
- Stored records were rescored. Both existing penalties (`ribosome` and `powerful`,
  20 each), the minimum score of 0, and all saved/dismissed choices were verified
  unchanged. Scores and social-post kinds were updated; old X author-location
  fallbacks were cleared.

## Live scans and sample review

| Source | Returned posts | Successful search requests | Reviewed | Newest returned post (UTC) |
| --- | ---: | ---: | ---: | --- |
| X | 63 | 8 | 30 | September 9, 16:57 |
| Bluesky | 18 | 30 | 18 | September 9, 15:52 |

Counts describe posts returned/upserted, not newly discovered vacancies. Query
matches can overlap. The X searches returned matches across all four families;
the reviewed top 30 covered resistance, language models, and metagenomics. The
Bluesky review covered all four families, including a bacterial-pathogen research
position and a genomic-language-model conference announcement.

Bluesky initially returned 23 posts. Review exposed false recruitment matches for
enzyme “jobs,” protein “positions,” current-job anecdotes, and a candidate seeking
a position. Context checks and regression tests were added; the final scan returned
18 posts. X additionally retrieves long-post text so recruitment evidence beyond
the short preview can be scored, subject to the existing 10,000-character storage
limit.

The final combined scan encountered a Bluesky HTTP 504 gateway timeout. A
Bluesky-only retry completed successfully. The older August 18 freshness gap was
not reproduced with the new queries: both platforms returned September 9 posts.

## Practical limits

The sample is dominated by academic openings and scientific events; these counts
are not a verified shortlist of NYC/remote industry jobs. Keyword heuristics still
admit event recaps, broad fellowship discussions, clinical-trial recruitment, and
loosely related content. Two pages per query bound API usage but do not guarantee
complete recall, particularly for broad Bluesky terms such as AMR and microbiome.
Post freshness does not establish whether an event or vacancy is still open.

Manual scanning and existing preferences remain unchanged. LinkedIn retrieval was
not changed or run during this review; the shared scoring profile also applies to
its stored records. No database-schema or public HTTP API changes were required.

API references: [X query syntax](https://docs.x.com/x-api/posts/search/integrate/build-a-query),
[X long-post fields](https://docs.x.com/x-api/fundamentals/data-dictionary),
[Bluesky search parameters](https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/searchPosts.json).
