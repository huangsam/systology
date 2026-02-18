---
title: "End-to-End Migration & Deduplication"
description: "Large-scale data migration and dedup."
summary: "System design for migrating large datasets with deduplication, integrity checks, resumability, and idempotence."
tags: ["networking"]
categories: ["designs"]
draft: false
---

## 1. Problem Statement & Constraints

Create a system to migrate large volumes of data between systems while performing deduplication to eliminate redundant entries, ensuring data integrity and efficiency. The process must be idempotent, support rollback capabilities, and complete within specified timeframes, handling potential failures gracefully in a scalable manner.

- **Functional Requirements:** Migrate data with deduplication.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 10TB migration.
    - **Availability:** 99.9%.
    - **Consistency:** Idempotent.
    - **Latency Targets:** Migration < 24 hours.

## 2. High-Level Architecture

{{< mermaid >}}
graph LR
  Source --> Scanner
  Scanner --> HashIndex[Hash Index]
  Scanner --> Migrator
  HashIndex --> Migrator
  Migrator --> Target
  Migrator -.->|checkpoint| StateDB[State DB]
  Reconciler --> Source
  Reconciler --> Target
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Chunking and scanning:** divide the source dataset into logical chunks (by primary-key range, date partition, or fixed-size blocks). Each chunk is an independent unit of work that can be migrated, retried, or skipped without affecting other chunks. Chunks are sized to fit in memory (e.g., 100 MB) to limit per-worker resource usage.
- **Content-hash deduplication:** compute a content hash (SHA-256 or xxHash) for each record or object. Maintain a hash index (Bloom filter for fast negative lookups, backed by a persistent hash-to-location map) to detect duplicates. When a duplicate is found, write a reference to the existing copy instead of re-migrating the data.
- **Idempotent writes and upserts:** use upsert semantics (INSERT ON CONFLICT UPDATE) in the target system so that re-running a chunk produces the same final state. Tag each record with a `migration_run_id` to distinguish fresh writes from replayed ones.
- **Resumable checkpoints:** after each chunk completes, persist a checkpoint record (`chunk_id`, `status`, `row_count`, `hash`) to a state database. On restart, the system skips already-completed chunks and resumes from the last incomplete one. This makes the entire migration restartable without re-processing.
- **Reconciliation and validation:** after the bulk migration, run a reconciliation pass that reads both source and target in parallel, comparing row counts, checksums, and sampled record values. Report mismatches and optionally re-migrate only the divergent chunks.
- **Rollback strategy:** before migration, snapshot or version the target dataset (e.g., database snapshot, object-store versioning). If post-migration validation reveals corruption, restore from the snapshot. For append-only targets, tag migrated records so they can be bulk-deleted.
- **Parallelism and throttling:** run multiple migration workers in parallel, each assigned a set of chunks. Apply rate limiting and backpressure to avoid overwhelming the source or target systems. Use adaptive throttling that backs off when source read latency or target write latency exceeds a threshold.

### Trade-offs

- Inline dedup vs. post-migration dedup: inline dedup (hash-check before write) avoids writing duplicates at all but requires a fast hash index in the critical path; post-migration dedup is simpler to implement but wastes write bandwidth and storage temporarily.
- Full reconciliation vs. sampling: full reconciliation guarantees correctness but is expensive (reads the entire dataset twice); sampling-based reconciliation is faster but can miss localised corruption.
- Snapshot rollback vs. record-level rollback: snapshots are simple and atomic but require enough storage headroom for a full copy; record-level rollback is space-efficient but more complex and slower to execute.

## 4. Operational Excellence

### SLIs / SLOs
- SLO: Complete 10 TB migration within 24 hours.
- SLO: Post-migration reconciliation shows 0 mismatches (100% data integrity).
- SLIs: migration_throughput_gbps, chunk_completion_rate, dedup_ratio, reconciliation_mismatch_count, checkpoint_lag.

### Monitoring & Alerts (examples)

Alerts:

- `migration_throughput < 100 GB/hr` for 30m
    - Severity: P1 (SLA at risk; investigate bottleneck workers or throttling).
- `reconciliation_mismatch_count > 0`
    - Severity: P1 (data integrity issue; halt migration and investigate).
- `chunk_failure_rate > 5%`
    - Severity: P2 (investigate source connectivity or target write errors).

### Testing & Reliability
- Run a dry-run migration against a staging copy of the target to validate transforms, dedup logic, and reconciliation before touching production.
- Chaos-test by killing workers mid-chunk and verify that checkpoint-based resumption produces identical results.
- Benchmark dedup hash index under realistic key counts (billions of hashes) to validate memory and lookup latency.

### Backups & Data Retention
- Retain the source dataset unmodified until reconciliation passes and a post-migration bake-in period (7–14 days) completes.
- Keep checkpoint and state DB records for 90 days for debugging and auditing.
- Archive migration logs and reconciliation reports for compliance (1 year minimum).
