"""
Shared constants for Systology management scripts.
"""

# Maximum length for description
MAX_DESC_LEN = 160

# Hugo Directory Paths
SITE_DIR = "site"
CONTENT_DIR = "content"
STATIC_DIR = "static"
ASSETS_DIR = "assets"
ARCHETYPES_DIR = "archetypes"

# File Extensions
MD_EXT = ".md"
FM_DELIM = "---"

# Frontmatter Keys
FM_TITLE = "title"
FM_DATE = "date"
FM_LASTMOD = "lastmod"
FM_TAGS = "tags"
FM_SUMMARY = "summary"
FM_DESC = "description"

# Formatting Exclusions
IGNORE_FORMAT = [
    "syntax.css",
    "mermaid.min.js",
]

# Tag Management
TAG_ALIASES = {
    "goog-cloud-storage": "gcs",
    "google-cloud-storage": "gcs",
    "amazon-s3": "s3",
    "aws-s3": "s3",
    "feature-extraction": "ml",
    "rust": "systems-programming",
    "vcs": "systems-programming",
    # Resilience
    "circuit-breaker": "resilience",
    "retries": "resilience",
    # Monitoring & Observability
    "telemetry": "monitoring",
    "metrics": "monitoring",
    "observability": "monitoring",
    # Concurrency & Synchronization
    "atomic": "concurrency",
    "locking": "concurrency",
    "synchronization": "concurrency",
    "conflict-resolution": "concurrency",
    # Networking & Messaging
    "websocket": "networking",
    "delivery": "networking",
    "fan-out": "networking",
    "channel": "networking",
    "redirect": "networking",
    "resolution": "networking",
    # Algorithms
    "hashing": "algorithms",
    "traversal": "algorithms",
    # Orchestration
    "autonomous": "orchestration",
    "coordinator": "orchestration",
    # Privacy & Decentralization
    "secure-aggregation": "privacy",
    "decentralized": "privacy",
    # Media
    "chunking": "media",
    # Databases
    "consistency-models": "consistency",
    "relational": "database",
    "non-relational": "database",
}

TAG_REMOVALS = [
    "spark-trial",
    "onboarding",
]
