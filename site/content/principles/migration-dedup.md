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

## Efficient Deduplication

Use robust hashing (SHA-256, perceptual hashes) with collision detection and balance speed against false positive rates. Different dedup needs (file vs. image) may need different hash types.

## Resumability & Checkpoints

Partition work into shards with persistent progress manifests and store checkpoints at intervals. Resumability from checkpoints turns hours-long jobs into recoverable steps.

## Metadata Fidelity

Preserve EXIF data, timestamps, and original filenames during migration. Metadata often matters for downstream use cases and audit trails.

## Backend-specific Robustness

Implement retry strategies with exponential backoff for API failures and handle rate limits with adaptive delays. Each backend (S3, GCS, Dropbox) has its own quirks; abstract them.

## Dry-run & Verification

Support --dry-run mode with detailed operation manifests and include post-migration checksum verification. Dry-run turns risky operations into safe previews.

## Parallelism & IO

Use configurable concurrency for hashing and uploads and apply rate limiting to avoid saturating network or disk. Parallelism helps but synchronization overhead grows with concurrency.

## Safe Defaults

Default to conservative operations that preserve originals and require explicit confirmation for destructive actions. Reversibility is a feature.
