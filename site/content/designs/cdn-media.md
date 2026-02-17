---
title: "Global CDN-Backed Media Serving System"
description: "Distributed media delivery worldwide"
summary: "CDN-backed media delivery architecture for low-latency, highly-available global media serving with background upload processing."
tags: ["performance","networking","monitoring","caching"]
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Develop a global media serving system that efficiently delivers static and dynamic assets worldwide using a content delivery network, while handling background processing for user uploads. The architecture must optimize for low latency, high availability, and cost-effectiveness, ensuring secure and reliable access to media content across diverse geographic regions.

- **Functional Requirements:** Serve static/media assets globally, with background processing for uploads.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 1M requests/sec, global distribution.
    - **Availability:** 99.99%.
    - **Consistency:** Eventual for media updates.
    - **Latency Targets:** P99 < 100ms.

## 2. High-Level Architecture

{{< mermaid >}}
graph LR
  Users[Users] --> CDN[CDN Edge PoPs]
  CDN -->|miss| Shield[Origin Shield]
  Shield -->|miss| Origin[Origin Server]
  Origin --> ObjectStore[(Object Storage)]
  Uploader[Upload Service] --> Transcoder[Transcoder Workers]
  Transcoder --> ObjectStore
  Transcoder --> CDN
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Multi-tier cache hierarchy:** deploy edge PoPs close to users for L1 cache, with a regional origin shield (L2) that collapses concurrent cache misses into a single origin fetch. This dramatically reduces origin load and bandwidth costs when content goes viral.
- **Cache invalidation strategy:** use surrogate keys (tags) on objects so that a single purge command can invalidate all variants of a resource (different resolutions, formats). Prefer short TTLs (30–60 s) with `stale-while-revalidate` for dynamic metadata, and long TTLs (30 d+) with explicit purge for immutable media assets.
- **Upload and transcoding pipeline:** accept uploads through a dedicated upload service that writes raw files to object storage and enqueues a transcoding job. Workers produce multiple renditions (resolution, codec, thumbnail) and write outputs back to object storage, then warm the CDN by issuing a prefetch to the edge.
- **Signed URLs and access control:** generate time-limited signed URLs or signed cookies for private content. Enforce token verification at the edge so that unauthorized requests never reach the origin. Rotate signing keys periodically and support key overlap windows for zero-downtime rotation.
- **Image and video optimization:** serve modern formats (WebP, AVIF, H.265) with content negotiation via `Accept` headers. Apply on-the-fly image resizing at the edge for rarely-requested dimensions, and pre-generate popular variants.
- **Multi-CDN and failover:** use DNS-based or anycast routing to distribute traffic across multiple CDN providers. Implement health-check probes and automatic failover so that an edge outage redirects users to healthy PoPs within seconds.

### Tradeoffs

- Origin shield: reduces origin traffic significantly but adds an extra hop of latency on cold-cache requests; without it, origin can be overwhelmed during cache-busting events.
- On-the-fly transforms: flexible and storage-efficient but CPU-intensive at the edge and risk latency spikes; pre-generating variants eliminates edge compute cost but increases storage and transcoding time.
- Multi-CDN: improves resilience and allows vendor negotiation but increases operational complexity and makes cache invalidation harder to coordinate across providers.

## 4. Operational Excellence

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
