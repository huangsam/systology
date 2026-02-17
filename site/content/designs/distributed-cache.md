---
title: "Distributed Caching Layer for a VCS-like System"
description: "Performance optimization for version control"
summary: "Design a distributed cache to reduce I/O and speed up VCS operations by caching objects and hashes with high concurrency and low latency."
tags: ["performance","monitoring"]
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Implement a distributed caching layer for a version control system to cache frequently accessed objects and hashes, reducing I/O operations and improving performance. The cache must handle high concurrency, provide thread-safe access, and dynamically manage memory usage while maintaining low latency for read-heavy workloads.

- **Functional Requirements:** Cache objects, hashes for VCS operations.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 100k ops/sec.
    - **Availability:** 99.9%.
    - **Consistency:** Eventual.
    - **Latency Targets:** P99 < 10ms.

## 2. High-Level Architecture

{{< mermaid >}}
graph LR
  Client[VCS Client] --> LB[Load Balancer]
  LB --> AppServer[App Server]
  AppServer -->|cache-aside| Cache[(Redis Cluster)]
  AppServer -->|miss| Backend[(Git Object Store)]
  Cache -.->|replication| CacheReplica[(Read Replica)]
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Data model and key design:** cache Git objects (blobs, trees, commits) and pack-index lookups keyed by their SHA hash. Use prefixed keys (`obj:<sha>`, `tree:<sha>`, `ref:<branch>`) to namespace object types and allow targeted eviction or monitoring per category.
- **Consistent hashing and sharding:** partition the keyspace across cache nodes using consistent hashing with virtual nodes to minimise key redistribution when nodes join or leave. This keeps rebalancing to ~1/N of keys rather than a full reshuffle.
- **Eviction policy:** use an LRU eviction policy for general objects. For hot metadata (branch tips, HEAD refs) pin entries with longer TTLs or use an LFU variant to keep frequently accessed items resident.
- **Cache-aside pattern:** the application checks the cache first; on a miss it reads from the Git object store, populates the cache, and returns. Writes go directly to the backend store and invalidate the cache key. This avoids write amplification in the cache layer and keeps the store as the source of truth.
- **Hot-key mitigation:** for extremely popular repositories or refs, replicate hot keys across multiple shards (key replication) or use a local in-process L1 cache (bounded LRU, 1–5 s TTL) in front of the distributed cache to absorb thundering-herd reads.
- **Serialisation and compression:** store objects in compressed form (zstd or LZ4) to reduce memory footprint. The CPU cost of decompression is negligible compared to a network round-trip to the backend store.
- **Thread safety and concurrency:** use pipelining and connection pooling (one pool per app server) to maximise throughput. Employ `SETNX`-style locks or read-through cache-fill fences to prevent stampeding multiple backend fetches for the same cold key.

### Tradeoffs

- Cache-aside vs write-through: cache-aside is simpler and avoids unnecessary cache writes, but risks brief staleness after backend updates; write-through ensures freshness at the cost of added write latency and cache churn for infrequently-read objects.
- LRU vs LFU: LRU is simple and works well for recency-driven access patterns; LFU retains long-term popular objects better but is more complex to implement and slower to adapt to shifting workloads.
- Compression: reduces memory usage by 2–4× but adds CPU overhead per request; on cache-heavy workloads the tradeoff is almost always worthwhile.

## 4. Operational Excellence

### SLIs / SLOs
- SLO: Cache hit ratio ≥ 95% for object lookups.
- SLO: P99 cache read latency < 5 ms; P99 cache write latency < 10 ms.
- SLIs: cache_hit_ratio, cache_latency_p99, eviction_rate, memory_utilisation_percent, connection_pool_utilisation.

### Monitoring & Alerts (examples)

Alerts:

- `cache_hit_ratio < 90%` for 5m
    - Severity: P2 (investigate eviction pressure or workload change).
- `cache_memory_utilisation > 85%`
    - Severity: P2 (scale cluster or review TTLs / eviction thresholds).
- `cache_latency_p99 > 15ms` for 3m
    - Severity: P1 (check network, slow commands, or hot keys).

### Testing & Reliability
- Run chaos tests: kill individual cache nodes and verify consistent-hashing redistributes keys with minimal miss spike.
- Load-test with realistic VCS workloads (clone, fetch, push) to validate throughput and latency under 2× peak traffic.
- Integration-test cache invalidation paths to ensure stale objects are never served after a push.

### Backups & Data Retention
- The cache is ephemeral by design; the Git object store is authoritative. No cache backups are needed.
- Enable Redis RDB snapshots only for faster warm-up after planned maintenance restarts.
- Retain cache metrics and slow-log data for 30 days for capacity planning and debugging.
