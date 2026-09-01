# BigMoveFinder

BigMoveFinder is a local-first opportunity radar for computational biology. It scans X, Bluesky, and LinkedIn public job cards, scores results against a focused interest profile, and puts them in a dashboard where negative preferences can be tuned without editing code.

The default profile prioritizes New York City opportunities involving microbial genomics, protein language models, foundation models, metagenomics, protein structure, and computational biology. It recognizes full-time industry roles, scientist positions, fellowships, conferences, and seminars.

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

Only public data is collected. The app does not automate login, bypass access controls, or store social-network credentials other than an X API bearer token in your local environment.

## Ranking and feedback

Scoring lives in `scoring.py`. Positive evidence is grouped into topics, opportunity types, industry, and NYC proximity. In the Preferences panel, add phrases such as `postdoc`, `unpaid`, `principal`, or `remote only`, assign each a penalty, and save. Every result is rescored immediately. **Not for me** can dismiss an individual result or turn a selected phrase into a reusable penalty.

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
