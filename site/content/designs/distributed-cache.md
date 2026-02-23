---
title: "Distributed Caching Layer for VCS"
description: "Performance optimization for version control."
summary: "Design a distributed cache to reduce I/O and speed up VCS operations by caching objects and hashes with high concurrency and low latency."
tags: ["caching", "concurrency", "distributed-systems", "monitoring", "performance", "vcs"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Implement a distributed caching layer for a version control system to cache frequently accessed objects and hashes, reducing I/O operations and improving performance. The cache must handle high concurrency, provide thread-safe access, and dynamically manage memory usage while maintaining low latency for read-heavy workloads.

### Functional Requirements

- Cache Git objects (blobs, trees, commits) and metadata.
- Support cache invalidation and eviction policies.
- Provide thread-safe concurrent access.

### Non-Functional Requirements

- **Scale:** 100k cache operations/sec; multi-node sharding.
- **Availability:** 99.9% cache hit availability.
- **Consistency:** Eventual consistency (cache-aside pattern).
- **Latency:** P99 < 10ms for cache hits; P99 < 100ms on miss.
- **Workload Profile:**
    - Read:Write ratio: ~95:5
    - Peak throughput: 100k ops/sec
    - Retention: dynamic LRU eviction

## High-Level Architecture

{{< mermaid >}}
graph LR
    Client --> LB[Load Balancer]
    LB --> AppServer[App Server]
    AppServer -->|cache-aside| Cache
    AppServer -->|miss| Backend
    Cache -.->|replication| CacheReplica[Replica]
{{< /mermaid >}}

## Data Design

### Cache Key-Space (KV)
| Prefix | Key Format | Value Type | Description |
| :--- | :--- | :--- | :--- |
| `obj:` | `obj:<sha1>` | Compressed Blob | Git objects (blobs, trees, commits). |
| `idx:` | `idx:<pack_id>` | Byte Array | Pack-index offsets for object lookups. |
| `ref:` | `ref:<branch_path>`| SHA1 String | Branch heads and lightweight tags. |

### Node Metadata (Shared State/Config)
| Field | Type | Description |
| :--- | :--- | :--- |
| `consistent_hash_ring` | Range Map | Mapping of hash ranges to physical node IDs. |
| `node_status` | Hash Map | Health and load metrics per node (Heartbeat). |

## Deep Dive & Trade-offs

### Deep Dive

- **Data model:** Prefixed keys (`obj:`, `tree:`, `ref:`) namespace Git objects by SHA hashes. Enables targeted monitoring and category-specific eviction policies.

- **Consistent hashing:** Sharding across nodes using virtual nodes to minimize redistribution when cluster scale changes. Limits rebalancing to ~1/N of keyspace.

- **Eviction policies:** Standard LRU for general objects. Hot metadata (branch tips, HEAD) uses LFU or pinned entries to ensure high-priority data remains resident.

- **Cache-aside pattern:** Apps check cache first, then read-through to store on miss. Writes bypass cache and invalidate keys, ensuring the store is the source of truth.

- **Hot-key mitigation:** Key replication across shards for viral repos. Local L1 in-process caches absorb thundering herds before queries reach the distributed layer.

- **Storage optimization:** Objects are zstd/LZ4 compressed in-memory. Decompression CPU costs are negligible compared to the network I/O saved from misses.

- **Concurrency:** Connection pooling and pipelining maximize throughput. `SETNX` locks or fill-fences prevent multiple servers from fetching the same cold key.

### Trade-offs

- **Cache-aside vs. Write-through:** Cache-aside is simpler and lighter but risks minor staleness; Write-through ensures freshness but adds write latency.

- **LRU vs. LFU:** LRU is efficient for recency-based workloads; LFU excels at retaining long-term popular items but is slower to adapt to changing traffic.

- **Compression Overhead:** Reduces memory costs by 2–4x but increases request-time CPU; typically a net win given network and memory constraints.

## Operational Excellence

### SLIs / SLOs

- SLO: Cache hit ratio ≥ 95% for object lookups.
- SLO: P99 cache read latency < 5 ms; P99 cache write latency < 10 ms.
- SLIs: cache_hit_ratio, cache_latency_p99, eviction_rate, memory_utilization_percent, connection_pool_utilization.

### Monitoring & Alerts

- `cache_hit_ratio < 90%`: investigate eviction pressure (P2).
- `memory_utilization > 85%`: scale cluster or review TTLs (P2).
- `cache_latency_p99 > 15ms`: check network or hot keys (P1).

### Reliability & Resiliency

- **Chaos/Load**: Kill nodes to verify hash ring redistribution; load-test at 2x peak traffic.
- **Verification**: Integration-test cache invalidation paths for strict object freshness.

### Retention & Backups

- **Data Policy**: Ephemeral by design (authoritative store in Git); snapshots for maintenance warm-up.
- **Retention**: 30d metrics retention for capacity planning and debugging.
