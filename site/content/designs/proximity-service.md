---
title: "Proximity Service for Maps"
description: "High-performance location-based search using geospatial indexing."
summary: "Design for finding nearby points of interest with low latency, focusing on geospatial data structures like Geohashing or Quadtrees."
tags: ["algorithms", "caching", "database"]
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

Mobile clients route through a Load Balancer that splits Read and Write traffic. Read APIs check a fast Geo-Cache before falling back to a Spatial Database for search queries. Write APIs asynchronously ingest location updates from moving entities, eventually updating the Spatial Database.

## Data Design

The Spatial Index maps 2D coordinates into 1D strings (Geohashes) stored in a B-Tree for fast prefix-proximity searches. A secondary NoSQL database stores heavily-indexed POI Metadata for full-text search, filtering, and ranking.

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

{{< pseudocode id="geohash-search" title="Geohash Radius Search" >}}
```python
def get_nearby_pois(lat, lon, radius_km):
    # 1. Determine optimal geohash precision based on radius
    # e.g., radius 5km -> precision 5 (approx 4.9km x 4.9km cell)
    precision = calculate_precision(radius_km)

    # 2. Compute the center geohash
    center_hash = geohash.encode(lat, lon, precision)

    # 3. Get the center cell AND its 8 neighbors to handle edge cases
    # (where the user is near the boundary of a geohash cell)
    search_hashes = geohash.get_neighbors(center_hash)
    search_hashes.append(center_hash)

    results = []

    # 4. Query the Spatial DB (B-Tree) for POIs in these 9 prefixes
    for g_hash in search_hashes:
        # Fast prefix scan: SELECT * FROM spatial_db WHERE geohash LIKE 'g_hash%'
        pois_in_cell = db.prefix_search(g_hash)

        # 5. Post-filter exact distances (Haversine formula)
        for poi in pois_in_cell:
            if haversine_distance(lat, lon, poi.lat, poi.lon) <= radius_km:
                results.append(poi)

    return sort_by_rating_and_relevance(results)
```
{{< /pseudocode >}}

### Deep Dive

- **Geospatial Indexing:** Geohashing maps 2D coordinates to hierarchical string prefixes, enabling fast range queries directly on standard B-trees.

- **Expanding Ring Search:** Queries start at high precision, only "ringing out" if results are sparse, avoiding over-fetching in dense centers.

- **Location Pipeline:** Moving entities stream batched gRPC updates. Coalesced latest-wins flushing minimizes write amplification while maintaining tracking freshness.

- **Geo-caching:** Redis (`GEOADD`) pre-warms hot geohash cells. TTLs are strictly tuned to cell churn (e.g., 1m for movers, 10m for static businesses).

- **Ranking & Filtering:** Spatial results are post-filtered by operational metadata (ratings, hours), then ordered via personalization and business quality signals.

- **Sharding by Prefix:** Partitioning the spatial DB on geohash prefixes physically co-locates nearby POIs, eliminating cross-shard fan-out for local searches.

- **Multi-resolution Support:** The API dynamically maps requested radii to optimal geohash precisions, preventing excessive point scans during wide-area searches.

### Trade-offs

- **Geohash vs. Quadtree:** Geohash is simpler and shatters well for sharding but has boundary "blind spots"; Quadtrees are density-aware but harder to distribute.

- **Cache Full Results vs. Raw POIs:** Caching results is faster for repetition but memory-heavy; Caching raw POIs is flexible for ranking but increases per-request compute.

## Operational Excellence

### SLIs / SLOs

- SLO: 99.9% of search queries return results within 200 ms.
- SLO: Location updates reflected in search results within 30 seconds (eventual consistency target).
- SLIs: search_latency_p99, cache_hit_ratio_by_cell_precision, location_update_lag_p95, query_result_count_avg, shard_hotspot_qps.

### Reliability & Resiliency

- **Accuracy**: Validate geospatial distance accuracy via pre-computed golden sets.
- **Realistic Load**: Test with zipfian query distribution over dense city centers.
- **Geofail**: Chaos-test shard outages to verify graceful partial results.
