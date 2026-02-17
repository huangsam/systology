---
title: "Migration & Deduplication"
description: "Integrity and efficiency in large-scale data migration and deduplication."
summary: "Practices for safe, idempotent, and efficient large-scale data migration and deduplication."
tags: ["migration","deduplication"]
categories: ["principles"]
---

1. Idempotent Operations
    - Design migrators to be idempotent using manifests and checksums.
    - Use destination markers to detect and skip already-processed items.
    - Implement atomic operations to avoid partial state on failures.

2. Efficient Deduplication
    - Use robust hashing (SHA-256, perceptual hashes) with collision detection.
    - Balance hash speed against false positive rates for large datasets.
    - Support multiple hash types for different deduplication needs.

3. Resumability & Checkpoints
    - Partition work into shards with persistent progress manifests.
    - Store checkpoints at regular intervals for failure recovery.
    - Enable resuming from the last successful checkpoint.

4. Metadata Fidelity
    - Preserve EXIF data, timestamps, and original filenames during migration.
    - Provide configurable metadata mapping and transformation rules.
    - Maintain metadata integrity checks and validation.

5. Backend-specific Robustness
    - Implement retry strategies with exponential backoff for API failures.
    - Handle rate limits and throttling with adaptive delays.
    - Support backend-specific error handling and recovery procedures.

6. Dry-run & Verification
    - Support --dry-run mode that generates detailed operation manifests.
    - Include post-migration checksum verification for integrity.
    - Provide diff reports comparing source and destination states.

7. Parallelism & IO
    - Parallelize hashing and uploads with configurable concurrency limits.
    - Avoid saturating network or disk IO through rate limiting.
    - Use async IO patterns for efficient resource utilization.

8. Safe Defaults
    - Default to conservative operations preserving all originals.
    - Require explicit confirmation for destructive actions like deletion.
    - Provide preview modes showing planned changes before execution.
