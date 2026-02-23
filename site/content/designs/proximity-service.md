---
title: "Proximity Service for Maps"
description: "High-performance location-based search using geospatial indexing."
summary: "Design for finding nearby points of interest with low latency, focusing on geospatial data structures like Geohashing or Quadtrees."
tags: ["caching", "database"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design a service that allows users to search for businesses or points of interest (POIs) based on their current geographic location (latitude/longitude). The system must support high-frequency updates (for moving POIs) and extremely low-latency read requests for static business data.

### Functional Requirements

- Search for POIs within a radius or bounding box.
- Add, update, and delete POI locations.
- Support real-time location updates for mobile entities.

### Non-Functional Requirements

- **Scale:** 100M POIs globally; 50k queries/sec (read-heavy).
- **Availability:** 99.99% uptime; read-focused SLA.
- **Consistency:** Eventual consistency for location updates; immediate for static POI data.
- **Latency:** Search results < 200ms; location updates < 5 seconds to visible.
- **Workload Profile:**
    - Read:Write ratio: ~98:2
    - Peak throughput: 50k searches/sec
    - Retention: current POI state; 30-day update history

## High-Level Architecture

{{< mermaid >}}
graph TD
    Mobile --> LB
    LB --> Read[Read API]
    LB --> Write[Write API]
    Read --> Cache[(Cache)]
    Cache -.->|miss| Spatial[(Spatial DB)]
    Write --> Spatial
    Write --> Ingest
    Ingest --> Spatial
{{< /mermaid >}}

## Data Design

### Spatial Index (B-Tree + Geohash)
| Key (Geohash) | Value | Shard Strategy | Purpose |
| :--- | :--- | :--- | :--- |
| `9q8yyk...` | `poi_id` | Prefix `9q8` | Hierarchical 2D space mapping. |
| `9q8yyn...` | `poi_id` | Prefix `9q8` | Adjacent cell indexing. |

### POI Metadata (NoSQL/Document)
| Field | Type | Description | Indexing |
| :--- | :--- | :--- | :--- |
| `id` | UUID (PK) | Unique provider ID. | Hash |
| `name` | String | Business/Place name. | Full-text |
| `category` | Enum | `restaurant`, `park`, etc. | Bitmap |
| `rating` | Float | 0.0 to 5.0 score. | Range |

## Deep Dive & Trade-offs

### Deep Dive

- **Geospatial Indexing:** Uses Geohashing to map 2D coordinates to hierarchical string prefixes. Enables fast range queries on standard B-trees; Quadtrees as an alternative for variable density.

- **Expanding Ring Search:** Queries start at high precision and "ring out" if results are sparse. Avoids over-fetching in dense centers while ensuring results in rural areas.

- **Read/Write Path Separation:** Read-heavy traffic (50k QPS) served from replicas and Geo-caches. Writes bypass the hot path, asynchronously updating the spatial index.

- **Location Pipeline:** Moving entities stream batched GPS updates via gRPC. Coalesced latest-wins flushing reduces write amplification while maintaining freshness.

- **Geo-caching:** Hot geohash cells pre-warmed in Redis (`GEOADD`). TTLs are tuned based on cell churn (e.g., 1m for moving entities, 10m for static businesses).

- **Ranking & Filtering:** Spatial results post-filtered by rating, "open now", and categories. Personalization and business quality signals drive final ordering.

- **Sharding by Prefix:** Partitions the spatial DB on geohash prefixes. Co-locates nearby POIs on the same shard to minimize cross-shard fan-out for local searches.

- **Multi-resolution Support:** API maps requested radii to optimal geohash precision. Dynamic selection prevents scanning excessive points for wide-area searches.

### Trade-offs

- **Geohash vs. Quadtree:** Geohash is simpler and shatters well for sharding but has boundary "blind spots"; Quadtrees are density-aware but harder to distribute.

- **Cache Full Results vs. Raw POIs:** Caching results is faster for repetition but memory-heavy; Caching raw POIs is flexible for ranking but increases per-request compute.

## Operational Excellence

### SLIs / SLOs

- SLO: 99.9% of search queries return results within 200 ms.
- SLO: Location updates reflected in search results within 30 seconds (eventual consistency target).
- SLIs: search_latency_p99, cache_hit_ratio_by_cell_precision, location_update_lag_p95, query_result_count_avg, shard_hotspot_qps.

### Monitoring & Alerts

- `search_latency_p99 > 500ms`: Check shard fan-out or cache misses (P1).
- `cache_hit_ratio < 80%`: Review TTL policy or scale hot-cell cache (P2).
- `location_update_lag > 60s`: Scale ingestion consumers or check DB (P2).

### Reliability & Resiliency

- **Accuracy**: Validate geospatial distance accuracy via pre-computed golden sets.
- **Realistic Load**: Test with zipfian query distribution over dense city centers.
- **Geofail**: Chaos-test shard outages to verify graceful partial results.

### Retention & Backups

- **Index**: Multi-AZ replication with daily snapshots for DR.
- **Logs**: 7-day raw GPS update retention for replay and debugging.
- **Archive**: Historical POI lifecycle data (closures/relocations) for auditing.
