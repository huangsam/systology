---
title: "Migration & Deduplication"
description: "Integrity and efficiency in migration/deduplication."
summary: "Practices for safe, idempotent, and efficient large-scale data migration and deduplication."
tags: ["deduplication"]
categories: ["principles"]
draft: false
---

## Idempotent Operations

Design migrations to be idempotent using manifests and checksums with destination markers to skip processed items. Idempotence makes retries safe and enables resumability without special cases.

Concretely, before processing each item, check the destination for a marker (a checksum file, a database flag, or the item itself). If the marker exists and the checksum matches, skip. If it's missing or stale, process and write the marker atomically. This turns your migration into a convergent operation—you can run it 10 times and get the same result as running it once.

See how [Photohaul]({{< ref "/deep-dives/photohaul" >}}) implements destination-side dedup markers to make multi-backend migrations safely resumable.

**Anti-pattern — "Just Don't Run It Twice":** Relying on human discipline to avoid re-running a migration. Network glitches, OOM kills, and operator error will cause re-runs. If your migration creates duplicates when retried, you haven't built a migration—you've built a footgun. Idempotence is not optional for production migrations.

## Efficient Deduplication

Use robust hashing (SHA-256, perceptual hashes) with collision detection and balance speed against false positive rates. Different dedup needs (file vs. image) may need different hash types.

For exact file dedup, SHA-256 is the standard—collisions are astronomically unlikely and the hash is well-supported everywhere. For near-duplicate image detection (same photo with different crops, compression, or watermarks), use perceptual hashes like pHash or dHash that tolerate visual similarity. For very large file sets, use a two-stage approach: fast hash (xxHash, CRC32) for a first pass, then SHA-256 only for potential duplicates.

**Anti-pattern — MD5 for Dedup:** Using MD5 because "it's fast enough." MD5 has known collision vulnerabilities, and while accidental collisions are rare, adversarial collisions are trivial to construct. For any security-sensitive dedup (financial records, legal documents), use SHA-256. For non-sensitive dedup, xxHash is faster and collision-resistant.

**Anti-pattern — Hash Only, No Verification:** Treating hash matches as definitive proof of duplication without secondary verification. For critical data, compare file sizes and sample bytes after a hash match. The cost of a false positive (deleting a unique file) can far exceed the cost of a secondary check.

## Resumability & Checkpoints

Partition work into shards with persistent progress manifests and store checkpoints at intervals. Resumability from checkpoints turns hours-long jobs into recoverable steps.

Split the input into logical shards (by directory, by file prefix, by date range) and track each shard's progress independently. Write progress to a manifest file (JSON or SQLite) after each shard completes. On restart, read the manifest, skip completed shards, and resume from where you left off. For large shards, checkpoint progress within each shard at intervals (e.g., every 1000 files).

See the [Service Resilience]({{< ref "/principles/service-resilience" >}}) principles for how job-level checkpointing and visibility timeouts enable reliable processing of large workloads with retries.

**Anti-pattern — All-or-Nothing Migration:** Processing 100,000 files in a single transaction that either fully succeeds or fully fails. A single error at file 99,999 forces you to reprocess everything from scratch. Shard the work and checkpoint progress so failures only affect the current shard.

## Metadata Fidelity

Preserve EXIF data, timestamps, and original filenames during migration. Metadata often matters for downstream use cases and audit trails.

Create a metadata sidecar (JSON, SQLite) that maps each migrated file to its original path, creation timestamp, EXIF data, and migration timestamp. This enables auditing ("where did this file come from?"), rollbacks ("put it back where it was"), and dedup refinement ("are these the same file from different sources?"). When the destination format supports metadata (S3 object tags, Google Drive properties), write it there too.

See the [Media Analysis]({{< ref "/principles/media-analysis" >}}) principles for related guidance on preserving EXIF and codec metadata during processing pipelines.

**Anti-pattern — Rename to UUID:** Renaming files to UUIDs during migration for simplicity. Original filenames often carry semantic meaning (dates, descriptions, project names) that's impossible to reconstruct. Preserve the original name in metadata even if you need a system-assigned ID for storage.

## Backend-specific Robustness

Implement retry strategies with exponential backoff for API failures and handle rate limits with adaptive delays. Each backend (S3, GCS, Dropbox) has its own quirks; abstract them.

Create a backend interface with `upload`, `download`, `exists`, and `list` operations. Behind each implementation, handle the provider's specific error codes: S3's `SlowDown` errors, Dropbox's `too_many_write_operations`, Google Drive's `rateLimitExceeded`. Use exponential backoff with jitter (start at 1s, cap at 60s) and circuit-breaker patterns for sustained failures.

See the [Networking & Services]({{< ref "/principles/networking-services" >}}) principles for complete guidance on retry strategies, rate limiting, and connection management that applies to all backend integrations.

**Anti-pattern — Retry Everything Identically:** Using the same retry strategy for all backends (e.g., 3 retries with 1s delay). S3 handles 3,500 PUT requests per second per prefix; Dropbox allows 6 concurrent uploads. Your retry strategy needs to respect per-backend rate limits and adapt delays accordingly.

## Dry-run & Verification

Support --dry-run mode with detailed operation manifests and include post-migration checksum verification. Dry-run turns risky operations into safe previews.

In dry-run mode, walk through every step the migration would perform and write a manifest of planned operations: `{action: "copy", source: "/photos/2024/img001.jpg", dest: "s3://bucket/2024/img001.jpg", size: 4823619}`. Let the operator review the manifest before committing. After the actual migration, run a verification pass that checksums every file at the destination against the source.

**Anti-pattern — YOLO Migration:** Running a migration against production data without a dry-run first. "It worked on staging" means nothing when staging has 100 files and production has 100,000 with different edge cases (special characters in filenames, zero-byte files, symlinks). Always preview, verify, then commit.

## Parallelism & IO

Use configurable concurrency for hashing and uploads and apply rate limiting to avoid saturating network or disk. Parallelism helps but synchronization overhead grows with concurrency.

Optimal concurrency depends on the bottleneck: for CPU-bound hashing, use `num_cpus` workers; for network-bound uploads, experiment with 4–32 concurrent connections (more may cause provider throttling); for local disk IO, 2–4 parallel readers typically saturate an SSD. Expose concurrency as a `--workers N` flag and log throughput per-worker to help users tune.

See the [Algorithms & Performance]({{< ref "/principles/algorithms-performance" >}}) principles for deeper guidance on parallelism measurement and tuning worker counts.

**Anti-pattern — Max Parallelism:** Setting worker count to 128 because "more threads = faster." Beyond the bottleneck saturation point, additional workers add contention (lock contention, network congestion, disk seeks) without increasing throughput. Benchmark with 1, 4, 16, 32 workers and find the knee of the curve.

## Safe Defaults

Default to conservative operations that preserve originals and require explicit confirmation for destructive actions. Reversibility is a feature.

The default mode should be copy-not-move: keep originals intact until the migration is verified. Destructive operations (deleting originals, overwriting conflicts) require explicit flags (`--delete-originals`, `--overwrite`). Show a summary and require confirmation before destructive actions: `"This will delete 47,832 files from /photos/. Type 'yes' to confirm."`.

**Anti-pattern — Delete on Success:** Automatically deleting source files as soon as they're uploaded. A network corruption during upload could go undetected, leaving you with a corrupted copy and no original. Keep originals until a separate verification pass confirms every file was transferred intact. Only then offer deletion as an explicit, separate step.

## Decision Framework

Choose your migration strategy based on the data volume and the required uptime for the system:

{{< mermaid >}}
graph LR
    Write[Write Path] --> OldDB[(Old DB)]
    Write --> NewDB[(New DB)]
    Read[Read Path] -->|primary| OldDB
    Read -.->|shadow reads| NewDB
    NewDB --> Verify{Results Match?}
    Verify -->|yes| Cutover[Cutover Reads to New DB]
    Verify -->|no| Debug[Debug and Fix]
{{< /mermaid >}}

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Zero Downtime** | Dual-Write / Shadow-Read| Verifies data in parallel before switching over the read path. |
| **Operational Simplicity**| Offline Batch Move | Cleanest approach; avoids complex dual-write logic if downtime is okay. |
| **High Data Integrity** | Snapshot Comparison | Directly compares source and sink to catch silent corruption. |
| **Resumeability** | Checkpointed Markers | Ensures large migrations can restart from where they left off after failure. |

**Decision Heuristic:** "Choose **Shadow-Reads** before committing to a full cutover. Seeing real traffic fail on the new system is better than finding out after the old one is deleted."
