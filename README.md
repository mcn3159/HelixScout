# HelixScout

HelixScout is a local-first opportunity radar for computational biology. It scans X, Bluesky, and LinkedIn public job cards, scores results against a focused interest profile, and puts them in a dashboard where negative preferences can be tuned without editing code.

The default profile prioritizes antibiotic resistance, bacterial gene-function prediction, protein/genomic/DNA language models, and metagenomics. It searches broadly for industry roles and scientific networking, then boosts NYC and explicitly remote opportunities.

## Run it

No package installation is required; the app uses Python's standard library.

```bash
cp .env.example .env
# Add X_BEARER_TOKEN to .env if you have one.
python3 app.py
```

Open [http://localhost:8787](http://localhost:8787). The first launch contains labeled demo cards so the interface is not empty. Click **Run scan** to replace that context with live results. Demo records can be hidden with the dashboard filter.

To run the tests:

```bash
python3 -m unittest discover -s tests -v
```

## Connectors

- **Bluesky** first uses the public `app.bsky.feed.searchPosts` endpoint. Some networks or regions may receive a CDN denial; in that case set `BLUESKY_IDENTIFIER` and a dedicated `BLUESKY_APP_PASSWORD` for the authenticated app-service fallback. Do not put your normal account password in `.env`.
- **X / Twitter** uses the official recent-search endpoint. Create a developer project and set `X_BEARER_TOKEN` in `.env`. The API returns posts from the recent window allowed by the account's access level.
- **LinkedIn** has no general-purpose public search/read API for this use case. The included adapter reads LinkedIn's public jobs cards slowly, without login or session cookies, and is deliberately isolated because the markup may change. Set `ENABLE_LINKEDIN_PUBLIC=false` to disable it. LinkedIn social posts are not scraped behind login.
- **Import fallback** accepts JSON or CSV from the dashboard. This is useful for saved LinkedIn results, newsletters, and event lists.

Only public data is collected. The app uses an X bearer token and, when configured, a Bluesky app password from your local environment. It does not bypass access controls.

### Search configuration

Both social platforms read their queries from `config.py`: `X_SEARCH_QUERIES` contains separate role/event queries for each research family; `BLUESKY_SEARCH_QUERIES` contains focused phrases, with opportunity and biological-context matching applied locally. AMR requires bacterial/microbial context, and generic foundation models require biological context in scoring.

X validates complete queries against a 512-character limit, adds English/non-retweet filters, and searches its recent seven-day window. Bluesky requests English posts sorted by latest, with a 30-day `since` window (the service filters by its search timestamp, which can differ from post creation time). Each query retrieves at most two pages: 50 posts/page on X and 40 on Bluesky. Cursors do not guarantee exhaustive coverage. Query identifiers are retained in each result's `raw.matched_queries` metadata; duplicate results merge those identifiers within a scan.

X also requests long-post text through `note_tweet`, up to the existing 10,000-character description storage limit. Recruitment matching checks context around ambiguous words such as `job` and `position`, so enzyme functions, amino-acid positions, and position papers do not automatically receive hiring points. These remain keyword heuristics: event recaps and general fellowship discussions can still appear.

Scanning remains manual by default (`SCAN_INTERVAL_MINUTES=0`). Broad specialist retrieval does not require NYC or remote wording, so posts without locations remain discoverable. Author profile locations are not treated as job locations.

## Ranking and feedback

Scoring lives in `scoring.py`. Synonyms count once per concept; the four core specialties earn 25 points each, related microbial genomics earns 20, and general methods earn 8, with a 50-point topic cap. Explicit recruitment earns 20, events 12, fellowships 8, and role titles alone 5; only the strongest opportunity signal counts. Industry scoring is retained. NYC earns 22 or explicit remote work 18, without stacking. Posts lacking explicit opportunity evidence are capped at 35 before penalties, except LinkedIn results, which are treated as opportunities based on their source. Plain research posts are filtered from new Bluesky results.

Bluesky posts receive an additional 20-point penalty if they have neither a link nor a contact invitation (for example, “DM me,” “email us,” or “get in touch”). Either is sufficient. Visible URLs, email addresses, rich-text links, and embedded link/quote cards count; the post's own permalink, author mentions, and image attachments alone do not. The weight is `BLUESKY_NO_CONTACT_PENALTY` in `config.py`. This rule applies after score caps and combines with your saved phrase penalties.

In the Preferences panel, add phrases such as `postdoc`, `unpaid`, or `principal`, assign each a penalty, and save. Every result is rescored immediately. **Not for me** can dismiss an individual result or turn a selected phrase into a reusable penalty. App startup also rescores stored records against the current profile, preserving saved/dismissed status and preferences. Existing social-post kinds and old X author-location fallbacks are corrected during rescoring.

Scores are evidence-based heuristics, not model output: expanding a score shows exactly which phrases added or subtracted points.

## API

- `GET /api/dashboard` — opportunities, preferences, stats, source status
- `POST /api/scan` — run all configured connectors
- `PUT /api/preferences` — save weights and rescore all records
- `PATCH /api/opportunities/:id` — set `saved`, `dismissed`, or `new`
- `POST /api/import` — import JSON or CSV text
- `GET /api/export.csv` — export visible stored opportunities

Environment variables are loaded from `.env` at startup. Set `SCAN_INTERVAL_MINUTES` to a positive integer for automatic scans; `0` keeps scanning manual.

## Notes on source access

X documents recent Post search at `GET /2/tweets/search/recent` and requires bearer authentication: <https://docs.x.com/x-api/posts/search-recent-posts>. Bluesky documents public AppView GET requests at <https://bsky.network/docs/category/http-reference/>. LinkedIn's documented Job Posting APIs are for approved partners publishing jobs, not general job discovery: <https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview>.
