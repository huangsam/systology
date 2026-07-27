---
title: "Photohaul"
description: "Java photo migration engine with metadata folder DSL, XMP sidecars, and parallel transfer."
summary: "A robust Java-based photo organization and migration engine featuring content-hash deduplication, a metadata-driven folder structure DSL with fallback chains, XMP sidecar discovery, parallel transfer pipelines, and multi-backend cloud targets."
tags: [deduplication, extensibility, media, parallelization, traffic-control]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/photohaul"
draft: false
date: "2026-02-16T10:22:20-08:00"
---

## Context & Motivation

**Context:** `Photohaul` is a Java/Gradle tool for organizing and migrating large photo collections to local or cloud targets (S3, Dropbox, Google Drive, SFTP) with customizable folder rules, XMP sidecar parsing, concurrent transfers, and content-hash deduplication.

**Motivation:** I was not able to apply my Lightroom-based photo organization patterns to my older photos, which are scattered across various folders and drives. I wanted a tool that could traverse my existing photo collection, identify duplicates based on content hashing, and migrate them to a new organized structure (e.g., by date, camera make/model, or subject tags) while preserving metadata and XMP sidecars. Additionally, I wanted the ability to migrate to cloud storage providers without manual drag-and-drop, leverage parallel worker threads for high-throughput migrations, and have resumable jobs in case of interruptions.

## The Local Implementation

- **Current Logic:** Photohaul is built using Java and Gradle (Kotlin DSL) with code quality enforced via JSpecify nullability annotations. It traverses files using a configured `PathRuleSet`, computes SHA-256 photo content hashes for deduplication, and streams files using `PathMigrator` implementations (Local Path, S3, Dropbox, Google Drive, SFTP).
- **Customizable Folder Layout DSL:** The organization hierarchy is defined via a `folder.structure` DSL (e.g. `yearTaken|yearModified/make|Unknown`). It extracts EXIF attributes (`yearTaken`, `make`, `model`, `focalLength`, `iso`) and supports **fallback chains** (`|`) to handle missing headers gracefully, defaulting to a configurable fallback folder (`folder.fallback`).
- **XMP Sidecar & Keyword Resolution:** Beyond EXIF headers, Photohaul resolves `tags` by scanning for external XMP sidecar files (`[name].xmp` or `[name].[ext].xmp`) or embedded IPTC/XMP keywords, allowing photos to be organized into subject-based folders. XML parsing incorporates explicit XXE (XML External Entity) protection.
- **Concurrent Migration Engine:** Multi-threaded migration (`migration.threads`) allows parallel file transfers across local disks and cloud endpoints. The worker pool is safely integrated with dry-runs (migration manifest audit) and delta tracking (`.photohaul_state.json`), ensuring atomic, thread-safe updates to the resume state.
- **Runtime Performance & ZGC:** The JVM runtime configuration leverages ZGC (Generational Z Garbage Collector) for low-latency heap management during large-scale directory traversals and multi-gigabyte photo batch processing.
- **Bottleneck:** Cloud API rate limits (HTTP 429) when running high concurrency against Google Drive or Dropbox; IO-bound traversal and hashing overhead for multi-terabyte binary datasets.

## Comparison to Industry Standards

- **My Project:** Focuses on photographer-oriented folder semantics, EXIF + XMP sidecar metadata resolution, and local-first deduplication combined with multi-cloud migration.
- **Industry:** General-purpose migration utilities (e.g., `rclone`) offer raw performance and dozens of storage backends, but lack domain-specific photo metadata parsing, EXIF fallback chaining, and XMP sidecar association.
- **Gap Analysis:** To match `rclone`'s raw throughput across WANs, tune backend-specific chunking and HTTP connection pooling; to differentiate, expand the metadata DSL to support geo-location reverse-geocoding and RAW file sidecar pairing.

## Risks & Mitigations

- **Data loss during migration:** Dry-run mode (`dryrun.enabled=true`) generates an audit manifest without executing transfers. Delta state tracking records successfully migrated files to prevent redundant re-uploads.
- **Cloud API rate limiting (429):** High worker thread counts against cloud APIs can trigger rate limits. **Mitigation:** Document conservative concurrency defaults for cloud modes and implement exponential backoff retry policies.
- **XMP XXE Security Vulnerabilities:** Parsing untrusted XMP sidecar files could expose the JVM to XML External Entity attacks. **Mitigation:** Explicitly disable DTDs and external entity resolution in the XML parser configuration.
- **EXIF/metadata stripping:** Preserve metadata by default during transfer and validate against camera test samples in CI.
