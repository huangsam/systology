---
title: "Mailprune"
description: "Email management tool for data processing."
summary: "Local-first email auditing and cleanup tool that identifies noisy senders and produces privacy-preserving recommendations."
tags: ["email","privacy","data-pipelines","networking","monitoring"]
categories: ["deep-dives"]
---

## Context — Problem — Solution

**Context:** Personal inboxes accumulate noise over time; Mailprune emerged to audit Gmail accounts locally, identify high-volume low-value senders, and recommend targeted fixes.

**Problem:** Large inboxes and API rate limits make full audits slow and fragile. Users need actionable recommendations that preserve privacy, avoid accidental mass changes, and can be reviewed before applying.

**Solution (high-level):** Keep processing local-first and privacy-preserving while improving robustness: resumable ingestion, durable processing state, cached semantic features, and staged, reversible recommendations.

## 1. The Local Implementation

- **Current Logic:** Mailprune is a Python CLI that uses the Gmail API to fetch messages and metadata, computes sender-level statistics (volume, open-rate proxies, thread activity), clusters senders by content/behavior, and produces targeted recommendations (unsubscribe, filter, mute). It runs as a local audit: `uv run mailprune audit` pulls messages, analyzes them in parallel (thread/process pool), caches intermediate results, and writes reports to disk.
- **Bottleneck:** Fetching messages at API rate limits and large inbox sizes creates IO-bound runs; memory and CPU usage spike during full-content clustering and embedding computation; OAuth token lifecycle and reauth flows complicate long-running jobs; absent persistent checkpoints, interrupted runs must restart from scratch.

## 2. Scaling Strategy

- **Vertical vs. Horizontal:**
    - Short term: vertical scaling (more CPU, faster IO) speeds up single-machine audits for tens of thousands of messages. Good for quick one-off cleans.
    - Long term: horizontal scaling is required for recurring audits across many accounts or very large mailboxes. Partition by time ranges, labels, or sender shards and run worker pools (Celery / RQ / Dask) to parallelize ingestion and analysis.

- **State Management:**
    - Move from in-memory caches to durable stores: use Redis for ephemeral caches and rate-limit state, Postgres for normalized metadata (senders, message indexes, last-checked cursors), and object storage (S3/local FS) for raw export/archives.
    - Add resumable ingestion checkpoints (per-label or per-page token) so interrupted runs resume incrementally.
    - For semantic features, maintain a local vector store (Chroma/FAISS) to avoid re-embedding repeated content; version embeddings and control retention for privacy.

- **Privacy-first considerations:**
    - Default to local-only processing (no external embedding/LLM APIs). If cloud services are optional, gate them behind explicit user consent and document data flows.
    - Encrypt at-rest artifacts (credentials, cached exports). Use short-lived OAuth tokens and secure storage for refresh tokens.

## 3. Comparison to Industry Standards

- **My Project:** Mailprune — local-first, privacy-aware audits + explainable recommendations; focuses on sender clustering and engagement heuristics.
- **Industry (e.g., SaneBox / CleanEmail / Gmail filters):** SaaS products offer managed cleanup with proprietary heuristics and cloud processing; Gmail filters operate at the server level and are immediate but require manual rule authoring.
- **Gap Analysis:**
    - Feature parity: SaaS can provide real-time, always-on filtering and cross-device integration; Mailprune is audit-first with manual or semi-automated remediation.
    - Cost: Building distributed ingestion, reliable background workers, and persistence raises engineering and infra costs compared to single-node local tooling.
    - Benefit: Mailprune's privacy-first approach and audit transparency are differentiators for privacy-conscious users.

## 4. Experiments & Metrics

- **Latency:** wall time per message (fetch + analysis) at different batch sizes and concurrency levels.
- **Throughput:** messages processed / second across worker pool sizes.
- **Recommendation quality:** precision@k measured by manual labels or small user study (do recommended unsubscribes match human decisions?).
- **False positive rate:** percentage of recommendations users revert.
- **Resource cost:** CPU / memory / storage required for N-message audits; infra cost estimate for a hosted version.

## 5. Risks & Mitigations

- **Accidental mass changes:** require `--dry-run` and explicit `--apply --confirm` flags; implement undo via saved filter definitions and a reversible action log.
- **OAuth/credentials leaks:** encrypt tokens at rest; use OS keychain when available; rotate refresh tokens and surface reauth UX.
- **Privacy violation from cloud embeddings:** default to local embeddings; if cloud is enabled, show explicit consent and purge raw message text after embedding.


