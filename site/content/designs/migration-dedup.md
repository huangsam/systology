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

A Scanner reads Source data chunks, consulting a Hash Index to filter out already-migrated records. A Migrator writes unique records to the Target system while checkpointing progress to a State DB. Concurrently, a Reconciler compares Source and Target blocks to ensure data integrity.

## Data Design

A Hash Index combining a Bloom filter and a Key-Value map accelerates duplicate detection. A relational State Database tracks the exact status of each chunk (pending, syncing, verified) to guarantee idempotent resumption.

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

- **Chunking & Scanning:** Dividing data into independent ranges enables parallel processing, bounded memory usage, and granular resumption.

- **Content-hash Dedup:** SHA-256 fingerprinting using a Bloom filter and persistent KV map detects and prevents redundant target writes.

- **Idempotent Upserts:** `INSERT ON CONFLICT UPDATE` semantics and `migration_run_id` tags ensure chunk re-runs converge to the correct state safely.

- **Resumable Checkpoints:** Persisting chunk statuses to a State DB allows the system to skip completed chunks on restart, enabling zero-waste recovery.

- **Reconciliation:** A parallel process compares checksums and counts, identifying divergent chunks for targeted re-migration.

- **Rollback Strategy:** Target snapshots or record-tagging enables atomic restoration if validation fails, protecting against corruption.

- **Throttling:** Adaptive throttling backs off dynamically based on source/target latency to protect live production performance.

### Trade-offs

- **Inline vs. Post-migration Dedup:** Inline saves bandwidth/storage but adds latency; Post-migration simplifies the write path but generates temporary waste.

- **Full vs. Sampled Reconciliation:** Full guarantees bit-identical results but is expensive; Sampling is faster but can miss small-scale or localized data corruption.

## Operational Excellence

### SLIs / SLOs

- SLO: Complete 10 TB migration within 24 hours.
- SLO: Post-migration reconciliation shows 0 mismatches (100% data integrity).
- SLIs: migration_throughput_gbps, chunk_completion_rate, dedup_ratio, reconciliation_mismatch_count, checkpoint_lag.

### Reliability & Resiliency

- **Dry-run**: Run against staging target to validate dedup and transforms.
- **Chaos**: Kill workers mid-chunk and verify checkpoint-based resumption.
- **Benchmark**: Test hash index at billion-key scale for memory and latency.
