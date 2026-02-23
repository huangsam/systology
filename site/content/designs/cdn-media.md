---
title: "Global CDN Media Serving"
description: "Distributed media delivery worldwide."
summary: "CDN-backed media delivery architecture for low-latency, highly-available global media serving with background upload processing."
tags: ["caching", "media", "monitoring", "networking", "performance"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Develop a global media serving system that efficiently delivers static and dynamic assets worldwide using a content delivery network, while handling background processing for user uploads. The architecture must optimize for low latency, high availability, and cost-effectiveness, ensuring secure and reliable access to media content across diverse geographic regions.

### Functional Requirements

- Serve static and media assets globally.
- Support background processing and transcoding for uploads.
- Provide signed URLs and access control for private content.

### Non-Functional Requirements

- **Scale:** 1M requests/sec, global distribution; multi-region deployment.
- **Availability:** 99.99% uptime with multi-CDN failover.
- **Consistency:** Eventual consistency for media updates.
- **Latency:** P99 < 100ms to edge; P99 < 500ms origin.
- **Workload Profile:**
    - Read:Write ratio: ~98:2
    - Peak throughput: 1M requests/sec
    - Retention: indefinite (hot); archive to cold storage after 1y

## High-Level Architecture

{{< mermaid >}}
graph LR
    Users --> CDN
    CDN -->|miss| Shield
    Shield -->|miss| Origin
    Origin --> Storage
    Uploader --> Transcoder
    Transcoder --> Storage
    Transcoder --> CDN
{{< /mermaid >}}

## Data Design

### Object Storage Layout (S3)
| Bucket | Prefix / Path | Retention | Description |
| :--- | :--- | :--- | :--- |
| `raw-uploads`| `user_id/YYYY-MM-DD/` | 30 days | Original untouched files. |
| `media-assets`| `asset_id/rendition/` | Indefinite | Post-transcoding optimal variants. |
| `static-logs` | `cdn/pop_id/HH_MM/` | 90 days | Aggregated edge access logs. |

### Cache Key & Logic (CDN)
| Item | Cache Key Pattern | TTL (Default) | Invalidation Tag |
| :--- | :--- | :--- | :--- |
| **Images** | `host/path?w=100&q=80` | 30 days | `img:<asset_id>` |
| **Videos** | `host/path/playlist.m3u8`| 1 year | `vid:<asset_id>` |
| **Manifests**| `host/config.json` | 60 seconds | `config:global` |

## Deep Dive & Trade-offs

### Deep Dive

- **Multi-tier caching:** Edge PoPs provide L1 cache. A regional Origin Shield (L2) collapses concurrent misses into a single fetch, protecting origin from viral traffic.

- **Invalidation strategy:** Surrogate keys (tags) enable purging all resolution/format variants at once. Uses short TTLs with `stale-while-revalidate` for metadata.

- **Upload pipeline:** Upload service writes raw files to S3 and enqueues transcoding. Workers generate renditions (720p, 1080p, etc.) and pre-warm the CDN edge via prefetch.

- **Security & Access:** Time-limited signed URLs or cookies verified at the edge. Rotatable signing keys allow for zero-downtime security updates.

- **Content Optimization:** Modern formats (WebP, AVIF, H.265) served via `Accept` header negotiation. Real-time resizing handles rare dimensions at the edge.

- **Multi-CDN Failover:** Anycast or DNS-based routing distributes traffic. Health-check probes trigger automatic failover to healthy PoPs if a provider degrades.

### Trade-offs

- **Origin Shield vs. Direct:** Shield reduces load significantly but adds a latency hop for cold-cache requests; direct is faster for misses but risks origin collapse.

- **On-the-fly vs. Pre-generation:** Transforms save storage but increase edge CPU and latency; Pre-generation is faster to serve but increases storage costs.

- **Multi-CDN vs. Single Provider:** Multi-CDN increases resilience but doubles configuration overhead and complicates cache invalidation sync.

## Operational Excellence

### SLIs / SLOs
- SLO: 99.99% of media requests served successfully (2xx/3xx) from edge or origin.
- SLO: P99 latency < 100 ms for cached content, < 500 ms for cache misses through origin shield.
- SLIs: cache_hit_ratio, origin_request_rate, edge_latency_p99, upload_success_rate, transcoding_duration_p95.

### Monitoring & Alerts (examples)

Alerts:

- `cache_hit_ratio < 85%` for 10m
    - Severity: P2 (investigate invalidation storms or config drift).
- `origin_5xx_rate > 1%` (5m)
    - Severity: P1 (origin health degraded; check storage and compute).
- `transcoding_queue_depth > 1000`
    - Severity: P2 (scale transcoder workers or check for stuck jobs).

### Testing & Reliability
- Run synthetic probes from multiple regions to continuously measure edge latency and availability.
- Perform periodic failover drills between CDN providers to validate DNS switchover timing.
- Load-test the upload-to-delivery pipeline under peak conditions (e.g., 10× normal upload rate).

### Backups & Data Retention
- Store all original uploads in a cross-region replicated object store with versioning enabled.
- Retain transcoded variants with lifecycle rules (e.g., delete unused renditions after 90 days).
- Keep CDN access logs for 30 days for debugging and aggregate to long-term analytics storage.
