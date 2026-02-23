---
title: "End-to-End Migration & Deduplication"
description: "Large-scale data migration and dedup."
summary: "System design for migrating large datasets with deduplication, integrity checks, resumability, and idempotence."
tags: ["deduplication", "networking"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Create a system to migrate large volumes of data between systems while performing deduplication to eliminate redundant entries, ensuring data integrity and efficiency. The process must be idempotent, support rollback capabilities, and complete within specified timeframes, handling potential failures gracefully in a scalable manner.

### Functional Requirements

- Migrate data between source and target systems.
- Detect and eliminate duplicate records during migration.
- Provide resumability and rollback capabilities.
- Reconcile source and target post-migration.

### Non-Functional Requirements

- **Scale:** 10 TB data migration; handle 100s of millions of records.
- **Availability:** 99.9%; graceful handling of partial failures.
- **Consistency:** Idempotent writes; no duplicate records post-migration.
- **Latency:** Full migration completion < 24 hours.
- **Workload Profile:**
    - Read:Write ratio: ~50:50
    - Throughput: 100–500 MB/sec
    - Retention: 7-day retention for reconciliation

## High-Level Architecture

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

## Data Design

### Hash Index (Bloom Filter + KV Map)
| Store | Purpose | Key / Pattern | Value |
| :--- | :--- | :--- | :--- |
| **Bloom** | First-pass membership check. | `content_hash` | N/A (Probabilistic) |
| **Map** | Exact location lookup. | `h:<sha256>` | `target_location_uri` |

### Migration State (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **checkpoints** | `chunk_id` | String (PK) | Partition or PK-range identifier. |
| | `status` | Enum | `pending`, `syncing`, `failed`, `verified`. |
| | `checksum` | String | Hash of migrating chunk for integrity. |
| | `run_id` | UUID | To handle idempotent re-runs. |

## Deep Dive & Trade-offs

### Deep Dive

- **Chunking & Scanning:** Data divided into independent units (100MB ranges). Allows parallel processing, resumes on failure, and limits per-worker memory usage.

- **Content-hash Dedup:** Uses SHA-256 for record fingerprinting. A Bloom filter combined with a persistent KV map detects existing targets to prevent redundant writes.

- **Idempotent Upserts:** Employs `INSERT ON CONFLICT UPDATE` semantics. Tags records with `migration_run_id` so re-running a chunk safely converges to the correct state.

- **Resumable Checkpoints:** Persists chunk status (`pending`, `syncing`, `verified`) to a State DB. System skips completed chunks on restart, enabling zero-waste recovery.

- **Reconciliation:** Parallel pass compares source and target checksums/counts. Identifies divergent chunks for targeted re-migration, ensuring 100% data integrity.

- **Rollback Strategy:** Uses target snapshots or record-tagging. Enables atomic restoration if post-migration validation fails, protecting data against corruption.

- **Throttling:** Adaptive controls back off based on source/target latency. Prevents the migration from impacting production system performance.

### Trade-offs

- **Inline vs. Post-migration Dedup:** Inline saves bandwidth/storage but adds latency; Post-migration simplifies the write path but generates temporary waste.

- **Full vs. Sampled Reconciliation:** Full guarantees bit-identical results but is expensive; Sampling is faster but can miss small-scale or localized data corruption.

## Operational Excellence

### SLIs / SLOs

- SLO: Complete 10 TB migration within 24 hours.
- SLO: Post-migration reconciliation shows 0 mismatches (100% data integrity).
- SLIs: migration_throughput_gbps, chunk_completion_rate, dedup_ratio, reconciliation_mismatch_count, checkpoint_lag.

### Monitoring & Alerts

- `migration_throughput < 100GB/hr`: Investigate bottlenecks (P1).
- `reconciliation_mismatches > 0`: Halt migration and investigate data integrity (P1).
- `chunk_failure_rate > 5%`: Check source connectivity or target errors (P2).

### Reliability & Resiliency

- **Dry-run**: Run against staging target to validate dedup and transforms.
- **Chaos**: Kill workers mid-chunk and verify checkpoint-based resumption.
- **Benchmark**: Test hash index at billion-key scale for memory and latency.

### Retention & Backups

- **Source**: Retained unmodified until 7–14 day post-migration bake-in passes.
- **State**: Checkpoint records kept for 90 days for debugging/audit.
- **Compliance**: Archive logs and reconciliation reports for 1 year minimum.
