---
title: "Photohaul"
description: "Photo system with media analysis and storage."
summary: "Java tool for organizing and migrating large photo collections with deduplication, metadata preservation, and resumable jobs."
tags: ["deduplication", "extensibility", "media", "migration", "networking"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/photohaul"
draft: false
---

## Context — Problem — Solution

**Context:** `Photohaul` is a Java/Gradle tool for organizing and migrating large photo collections to local or cloud targets with configurable folder rules and deduplication.

**Problem:** Processing tens of thousands of files reliably and quickly while preserving metadata, avoiding duplicates, and supporting multiple migration backends (S3, Dropbox, Google Drive, SFTP) requires careful IO, hashing, and failure-recovery design.

**Solution (high-level):** Use streaming traversal with skip-on-change semantics, robust content hashing for deduplication, pluggable migrators with idempotent operations, and a small job-state store for resumability.

## 1. The Local Implementation

- **Current Logic:** Photohaul traverses file paths using configured `PathRuleSet`, computes photo hashes for deduplication, and migrates files via `PathMigrator` implementations (local path, S3, Dropbox, Google Drive, SFTP). It supports skipping unchanged files and has configuration-driven folder rules.
- **Bottleneck:** IO-bound traversal and remote API latencies for cloud backends; deduplication hashing cost for large binary sets; ensuring metadata (EXIF) preservation across backends.

## 2. Scaling Strategy

- **Vertical vs. Horizontal:** Increase local IO concurrency and parallelize hashing; for very large archives, partition traversal into shards (by time range or file tree) and run workers in parallel. For cloud migrations, use concurrent uploads with retry/backoff.
- **State Management:** Introduce resumable job checkpoints (per-shard), a local SQLite/Postgres job-state table, and object manifest files for each migration run to enable idempotence and safe retries.

## 3. Comparison to Industry Standards

- **My Project:** Focus on customizable folder rules, local-first processing, and multiple backend migrators.
- **Industry:** Managed migration tools (rclone, cloud migration services) scale well and provide broad backend coverage; Photohaul focuses on photographer-oriented folder semantics and deduplication tuned for photography workflows.
- **Gap Analysis:** To match `rclone`'s breadth, ensure robust backend drivers and extensive retry/timeout tuning; to differentiate, expose rich folder-rule DSL and EXIF-first organization.

## 4. Experiments & Metrics

- **Throughput:** files migrated / second with various concurrency settings and backends.
- **Hash accuracy & collisions:** measure deduplication false-positive/negative rates on real datasets.
- **Resumability:** average recovery time after simulated failures and percent of duplicated uploads avoided.

## 5. Risks & Mitigations

- **Data loss during migration:** always run in `--dry-run` mode with manifest generation; verify checksums post-migration.
- **API rate limits for cloud backends:** implement exponential backoff and per-backend throttling.
- **EXIF/metadata stripping:** preserve metadata by default and add configurable transformations; test against representative camera outputs.

## Related Principles

- [Migration & Deduplication](/principles/migration-dedup): Idempotent operations, content hashing, resumability, and dry-run verification.
- [Extensibility](/principles/extensibility): Pluggable migrator backends (S3, Dropbox, SFTP) via trait/interface contracts.
- [Media Analysis](/principles/media-analysis): Metadata preservation, performance engineering, and packaging.
