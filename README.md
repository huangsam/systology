# Systology

Systology is a collection of systems engineering principles, architectural designs, and hands-on explorations learned through building, maintaining, and analyzing real systems over the past decade. The goal is to make tacit knowledge explicit: what actually works in practice, where the tradeoffs bite hardest, and what patterns scale vs. what patterns fail at the limits.

## What is here

**Principles:** Foundational ideas about how systems behave: data pipeline design, networking, monitoring, algorithm performance, media analysis, ML experiment hygiene. These capture patterns that apply across many domains.

**Resources:** Curated canonical literature, architectural blueprints, and production case studies across distributed systems, stream processing, and high-concurrency architectures.

**Deep Dives:** Reflections on actual projects: [long-term maintenance](site/content/deep-dives/chowist.md) (10+ years of framework evolution), [architectural comparatives](site/content/deep-dives/data-processing-architectures.md) (same problem, different solutions), and [other focused explorations](site/content/deep-dives/) (compilers, RAG systems, git implementations).

## Getting started

To run the site locally:

```shell
# Install Hugo via https://gohugo.io/getting-started/installing/
# Then:
make serve
```

Access the site at `http://localhost:1313/systology/`.

To run validation and formatting:
```shell
make check      # Validate content
make tidy       # Format and organize
make tags       # See tag usage counts
make insights   # Get tag recommendations (LLM feedback loop)
```
