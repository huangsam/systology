---
title: "Mailprune"
description: "Privacy-first Gmail auditing tool for sender clustering and inbox cleanup."
summary: "A highly effective, local-first email auditing and automated cleanup tool designed to definitively identify noisy senders and deliver actionable, strictly privacy-preserving recommendations."
tags: [monitoring, privacy, protocols]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/mailprune"
draft: false
date: "2026-02-16T10:22:20-08:00"
---

## Context & Motivation

**Context:** Personal inboxes accumulate noise over time; Mailprune emerged to audit Gmail accounts locally, identify high-volume low-value senders, and recommend targeted fixes.

**Motivation:** Large inboxes and API rate limits make full audits slow and fragile. Users need actionable recommendations that preserve privacy, avoid accidental mass changes, and can be reviewed before applying.

## The Local Implementation

- **Execution Modes:** Mailprune can run either as a local Python CLI (`uv run mailprune`) or as a Model Context Protocol (MCP) server (`uv run mailprune-mcp`), built using `FastMCP` to let AI assistants audit and clean inboxes directly.
- **MCP Server Capabilities:**
  - **Resources:** Exposes `mailprune://guidance/cleanup-strategy` (interpret sender clusters) and `mailprune://guidance/noise-metrics` (explaining the "Ignorance Score").
  - **Tools:** Exposes `audit` (fetch and cache Gmail message metadata), `report` (generate cleanup summaries), `patterns` (NLP-driven sender intent and entity extraction from snippets), `engagement` (analyze sender open rates by tiers), and `cluster` (K-Means behavioral clustering).
- **Current Logic:** Mailprune uses the Gmail API to fetch messages and metadata, computes sender-level statistics (volume, open-rate proxies, thread activity), clusters senders by content/behavior, and produces targeted recommendations (unsubscribe, filter, mute). It runs as a local audit, chunking API requests into sequential batches to respect rate limits, caching intermediate results, and writing reports to disk.
- **Bottleneck:** Fetching messages at API rate limits and large inbox sizes creates IO-bound runs; memory and CPU usage spike during full-content clustering and embedding computation; OAuth token lifecycle and reauth flows complicate long-running jobs; absent persistent checkpoints, interrupted runs must restart from scratch.

## Comparison to Industry Standards

- **My Project:** Mailprune — local-first, privacy-aware audits + explainable recommendations; focuses on sender clustering and engagement heuristics.
- **Industry (e.g., SaneBox / CleanEmail / Gmail filters):** SaaS products offer managed cleanup with proprietary heuristics and cloud processing; Gmail filters operate at the server level and are immediate but require manual rule authoring.
- **Gap Analysis:**
    - Feature parity: SaaS can provide real-time, always-on filtering and cross-device integration; Mailprune is audit-first with manual or semi-automated remediation.
    - Cost: Building distributed ingestion, reliable background workers, and persistence raises engineering and infra costs compared to single-node local tooling.
    - Benefit: Mailprune's privacy-first approach and audit transparency are differentiators for privacy-conscious users.

## Risks & Mitigations

- **OAuth/credentials leaks:** encrypt tokens at rest; use OS keychain when available; rotate refresh tokens and surface reauth UX.
- **Privacy violation from cloud embeddings:** default to local embeddings; if cloud is enabled, show explicit consent and purge raw message text after embedding.
