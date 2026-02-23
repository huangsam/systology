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

### Monitoring & Alerts

- `cache_hit_ratio < 85%`: Investigate invalidation storms or config drift (P2).
- `origin_5xx_rate > 1%`: Check origin storage and compute health (P1).
- `transcoding_queue > 1000`: Scale transcoder workers or check for stuck jobs (P2).

### Reliability & Resiliency

- **Synthetic**: Global probes to measure edge latency and multi-region availability.
- **Failover**: Regular multi-CDN failover drills to validate DNS switchover.
- **Load**: Test upload-to-delivery pipeline at 10x normal traffic.

### Retention & Backups

- **Originals**: Cross-region replicated object store with versioning.
- **Renditions**: Transcoded variants managed via 90-day lifecycle rules.
- **Logs**: 30-day access logs for debugging; aggregated for long-term analytics.
