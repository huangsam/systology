---
title: "Photohaul"
description: "Java-based photo migration tool with content-hash deduplication and multi-backend targets."
summary: "A robust Java-based tool engineered for seamlessly organizing and migrating extensive photo collections; featuring rigorous deduplication, automatic metadata preservation, and resumable execution."
tags: [deduplication, extensibility, media, traffic-control]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/photohaul"
draft: false
date: "2026-02-16T10:22:20-08:00"
---

## Context & Motivation

**Context:** `Photohaul` is a Java/Gradle tool for organizing and migrating large photo collections to local or cloud targets with configurable folder rules and deduplication.

**Motivation:** I was not able to apply my Lightroom-based photo organization patterns to my older photos, which are scattered across various folders and drives. I wanted a tool that could traverse my existing photo collection, identify duplicates based on content hashing, and migrate them to a new organized structure (e.g., by date or event) while preserving metadata. Additionally, I wanted the ability to migrate to cloud storage providers like Google Drive without manual drag-and-drop, and to have resumable jobs in case of interruptions.

## The Local Implementation

- **Current Logic:** Photohaul is built using Gradle (migrated from Groovy to Kotlin DSL) with code quality enforced via JSpecify nullability annotations. It traverses file paths using a configured `PathRuleSet`, computes SHA-256 photo content hashes for deduplication, and migrates files using `PathMigrator` implementations (local path, S3, Dropbox, Google Drive, SFTP). It supports dry-runs and skipping unchanged files.
- **Bottleneck:** IO-bound traversal and remote API latencies for cloud backends; deduplication hashing cost for large binary sets; ensuring metadata (EXIF) preservation across backends.

## Comparison to Industry Standards

- **My Project:** Focus on customizable folder rules, local-first processing, and multiple backend migrators.
- **Industry:** Managed migration tools (rclone, cloud migration services) scale well and provide broad backend coverage; Photohaul focuses on photographer-oriented folder semantics and deduplication tuned for photography workflows.
- **Gap Analysis:** To match `rclone`'s breadth, ensure robust backend drivers and extensive retry/timeout tuning; to differentiate, expose rich folder-rule DSL and EXIF-first organization.

## Risks & Mitigations

- **Data loss during migration [IMPLEMENTED]:** Dry-run support has been fully integrated across all `PathMigrator` implementations, allowing users to generate a migration manifest and verify changes prior to executing any destructive operations.
- **API rate limits for cloud backends:** implement exponential backoff and per-backend throttling.
- **EXIF/metadata stripping:** preserve metadata by default and add configurable transformations; test against representative camera outputs.
