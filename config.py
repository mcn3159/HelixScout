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

# A concept contributes once, regardless of how many aliases a post contains.
TOPIC_CONCEPTS = {
    "antibiotic resistance": (25, ("antibiotic resistance", "antimicrobial resistance", "resistome", "resistomes")),
    "bacterial gene function": (25, ("bacterial gene function", "bacterial genetics", "gene function prediction", "functional annotation")),
    "biological language models": (25, ("protein language model", "protein language models", "genomic language model", "genomic language models", "DNA language model", "DNA language models", "protein function prediction")),
    "metagenomics": (25, ("metagenomics", "metagenomic", "microbiome", "microbiomes")),
    "microbial genomics": (20, ("microbial genomics", "bacterial genomics", "bacterial pathogen", "bacterial pathogens", "pathogen", "pathogens")),
    "computational biology": (8, ("computational biology",)),
    "bioinformatics": (8, ("bioinformatics",)),
    "protein structure": (8, ("protein structure", "structural biology")),
    "gene function": (8, ("gene function",)),
    "phylogenetics": (8, ("phylogenetics", "phylogeny")),
    "AI for biology": (8, ("AIxBio", "AI for biology", "AI for life sciences", "AI x Bio")),
}
BACTERIAL_CONTEXT = ("bacterial", "bacteria", "microbial", "pathogen", "pathogens")
BIOLOGICAL_CONTEXT = BACTERIAL_CONTEXT + ("biology", "biological", "protein", "proteins", "genomic", "genomics", "genome", "DNA")
RECRUITMENT_SIGNALS = ("hiring", "recruiting", "job", "jobs", "position", "positions", "join our team", "applications open", "applications are open", "full-time", "full time", "internship", "internships")
EVENT_SIGNALS = ("conference", "conferences", "seminar", "seminars", "workshop", "workshops", "symposium", "symposia", "meetup", "meetups", "networking", "happy hour")
FELLOWSHIP_SIGNALS = ("fellowship", "fellowships", "fellow", "fellows")
ROLE_SIGNALS = ("scientist", "scientists", "researcher", "researchers", "computational biologist", "bioinformatician", "intern", "postdoc", "post-doc")
OPPORTUNITY_SIGNALS = {
    **dict.fromkeys(ROLE_SIGNALS, 5),
    **dict.fromkeys(FELLOWSHIP_SIGNALS, 8),
    **dict.fromkeys(EVENT_SIGNALS, 12),
    **dict.fromkeys(RECRUITMENT_SIGNALS, 20),
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
    "manhattan": 22,
    "brooklyn": 22,
    "queens": 22,
    "bronx": 22,
    "staten island": 22,
    "new york": 22,
    "new jersey": 18,
    "san francisco": 15,
    "south san francisco": 15

}

# Suggestions are shown in the UI but are not active until the user adds them.
PENALTY_SUGGESTIONS = ["sales","director"]

SEARCH_FAMILIES = {
    "resistance": ("antibiotic resistance", "antimicrobial resistance", "resistome", "AMR"),
    "gene_function": ("bacterial genetics", "bacterial pathogens", "bacterial gene function", "gene function prediction", "functional annotation"),
    "language_models": ("protein language model", "protein language models", "genomic language model", "genomic language models", "DNA language model", "DNA language models", "protein function prediction", "foundation model", "foundation models"),
    "metagenomics": ("metagenomics", "metagenomic", "microbial genomics", "microbiome"),
}
X_TOPIC_QUERIES = {
    "resistance": '("antibiotic resistance" OR "antimicrobial resistance" OR resistome OR (AMR (bacterial OR microbial)))',
    "gene_function": '("bacterial genetics" OR "bacterial pathogens" OR "bacterial gene function" OR "gene function prediction" OR "functional annotation")',
    "language_models": '("protein language model" OR "protein language models" OR "genomic language model" OR "genomic language models" OR "DNA language model" OR "DNA language models" OR "protein function prediction" OR (("foundation model" OR "foundation models") (biology OR protein OR genomic OR bacterial OR DNA)))',
    "metagenomics": '(metagenomics OR metagenomic OR "microbial genomics" OR microbiome)',
}
X_OPPORTUNITY_QUERIES = {
    "roles": '(hiring OR recruiting OR job OR position OR "join our team" OR "applications open" OR fellowship)',
    "events": '(conference OR seminar OR workshop OR symposium OR symposia OR meetup OR networking OR "happy hour")',
}
X_SEARCH_QUERIES = {
    f"{family}:{kind}": f"{topic} {opportunity}"
    for family, topic in X_TOPIC_QUERIES.items()
    for kind, opportunity in X_OPPORTUNITY_QUERIES.items()
}
BLUESKY_SEARCH_QUERIES = {
    f"{family}:{phrase}": f'"{phrase}"'
    for family, phrases in SEARCH_FAMILIES.items()
    for phrase in phrases
}
# Retained for local code that previously imported this X-only list.
SEARCH_QUERIES = list(X_SEARCH_QUERIES.values())
SEARCH_MAX_PAGES = 2
BLUESKY_LOOKBACK_DAYS = 30
BLUESKY_NO_CONTACT_PENALTY = 20
