"""Clearly labeled fictional examples for the first-run dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from database import Database


def seed_if_empty(database: Database) -> None:
    if database.stats()["total"]:
        return
    now = datetime.now(timezone.utc)

    def ago(days: int) -> str:
        return (now - timedelta(days=days)).isoformat(timespec="seconds")

    demo = [
        {
            "source": "linkedin", "external_id": "demo-li-1", "kind": "role",
            "title": "Scientist, Microbial Genomics", "organization": "Example Therapeutics",
            "location": "New York, NY", "posted_at": ago(1), "url": "https://www.linkedin.com/jobs/search/",
            "description": "Demo result: full-time scientist in a NYC biotech team applying metagenomics and microbial genomics to drug discovery.",
        },
        {
            "source": "bluesky", "external_id": "demo-bs-1", "kind": "event",
            "title": "Protein language models in therapeutic discovery — seminar", "organization": "Example Genome Center",
            "author": "@example.bsky.social", "location": "Manhattan", "posted_at": ago(2), "url": "https://bsky.app",
            "description": "Demo result: Join us in Manhattan for a computational biology seminar on protein language models, foundation models, and protein structure.",
        },
        {
            "source": "x", "external_id": "demo-x-1", "kind": "fellowship",
            "title": "Applications open: Computational Biology Industry Fellowship", "organization": "Example Bio Lab",
            "author": "@examplebio", "location": "NYC", "posted_at": ago(3), "url": "https://x.com/explore",
            "description": "Demo result: New York City fellowship bridging metagenomics, foundation models, and biotech research.",
        },
        {
            "source": "linkedin", "external_id": "demo-li-2", "kind": "role",
            "title": "Senior Computational Biologist, Protein Design", "organization": "Sample Pharma",
            "location": "Brooklyn, NY", "posted_at": ago(4), "url": "https://www.linkedin.com/jobs/search/",
            "description": "Demo result: full time scientist role using protein structure prediction and protein language models in pharmaceutical discovery.",
        },
        {
            "source": "bluesky", "external_id": "demo-bs-2", "kind": "event",
            "title": "Metagenomics & the urban microbiome symposium", "organization": "Sample Science Forum",
            "author": "@sampleforum.bsky.social", "location": "New York City", "posted_at": ago(5), "url": "https://bsky.app",
            "description": "Demo result: One-day NYC conference for microbial genomics, metagenomic surveillance, and public health researchers.",
        },
        {
            "source": "x", "external_id": "demo-x-2", "kind": "role",
            "title": "Bioinformatics internship — remote only", "organization": "Example Data Co.",
            "author": "@exampledata", "location": "Remote", "posted_at": ago(1), "url": "https://x.com/explore",
            "description": "Demo result: unpaid internship in general bioinformatics and sales enablement. Remote only.",
        },
    ]
    database.upsert_opportunities(demo, is_demo=True)

