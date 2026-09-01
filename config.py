"""Configuration and the default computational-biology search profile."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Load a tiny .env subset without adding a dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv()


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


DATABASE_PATH = ROOT / os.getenv("DATABASE_PATH", "data/opportunities.db")
PORT = int(os.getenv("PORT", "8787"))
SCAN_INTERVAL_MINUTES = max(0, int(os.getenv("SCAN_INTERVAL_MINUTES", "0")))

TOPICS = {
    "microbial genomics": 25,
    "protein language model": 20,
    "protein language models": 20,
    "genomic language model": 20,
    "genomic language models": 20,
    "foundation model": 12,
    "foundation models": 12,
    "metagenomics": 25,
    "metagenomic": 25,
    "protein structure": 15,
    "structural biology": 12,
    "computational biology": 20,
    "gene function": 18,
    "phylogenetics": 18,
    "phylogeny": 18,
    "bioinformatics": 20,
    "AIxBio": 13,
    "AI for biology": 13,
    "AI for life sciences": 13,
    "AI x Bio": 13,
}

OPPORTUNITY_SIGNALS = {
    "scientist": 12,
    "full-time": 15,
    "full time": 15,
    "fellowship": 12,
    "fellow": 15,
    "conference": 10,
    "happy hour": 10,
    "workshop": 12,
    "seminar": 9,
    "symposium": 9,
    "workshop": 7,
    "hiring": 6,
    "job": 5,
    "position": 5,
    "internship": 15,
    "intern": 15,
    "post-doc":7,
    "postdoc":7,
    "social":6,
}

INDUSTRY_SIGNALS = {
    "biotech": 10,
    "biotechnology": 10,
    "pharmaceutical": 10,
    "pharma": 9,
    "therapeutics": 7,
    "drug discovery": 8,
}

NYC_SIGNALS = {
    "new york city": 22,
    "new york, ny": 22,
    "nyc": 22,
    "manhattan": 18,
    "brooklyn": 18,
    "queens": 18,
    "bronx": 18,
    "new york": 14,
    "san francisco": 15,
    "south san francisco": 15
}

# Suggestions are shown in the UI but are not active until the user adds them.
PENALTY_SUGGESTIONS = ["sales","director"]

SEARCH_QUERIES = [
    '"computational biology" (job OR hiring OR fellowship OR seminar OR conference) (NYC OR "New York" OR "San Francisco" OR "South San Francisco")',
    '"bioinformatics" (job OR hiring OR fellowship OR seminar OR conference) (NYC OR "New York" OR "San Francisco" OR "South San Francisco")',
    '(metagenomics OR "microbial genomics") (job OR scientist OR seminar) (NYC OR "New York" OR "San Francisco" OR "South San Francisco")',
    '("protein language model" OR "foundation model" OR "protein structure") (hiring OR fellowship OR conference) (NYC OR "New York" OR "San Francisco" OR "South San Francisco")',
]

