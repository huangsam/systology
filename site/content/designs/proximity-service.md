---
title: "Proximity Service (Yelp/Maps)"
description: "High-performance location-based search using geospatial indexing."
summary: "Design for finding nearby points of interest with low latency, focusing on geospatial data structures like Geohashing or Quadtrees."
tags: ["caching", "database", "geo"]
categories: ["designs"]
draft: false
---

## 1. Problem Statement & Constraints

Design a service that allows users to search for businesses or points of interest (POIs) based on their current geographic location (latitude/longitude). The system must support high-frequency updates (for moving POIs) and extremely low-latency read requests for static business data.

- **Functional Requirements:** Add/delete/update POI locations, search nearby POIs within a given radius or box.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 100 million POIs globally; 50k queries per second (QPS).
    - **Latency:** Search results returned in < 200ms.
    - **Availability:** 99.99% (read-heavy workload).
    - **Accuracy:** Precision decreases as distance increases; eventual consistency for location updates is acceptable.

## 2. High-Level Architecture

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

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Geospatial indexing — Geohash vs. Quadtree:** use Geohash encoding to convert latitude/longitude into a hierarchical string prefix (e.g., `9q8yyk`). Nearby POIs share a common prefix, enabling range queries on a standard B-tree index. Alternatively, a Quadtree recursively subdivides 2-D space into quadrants until each leaf contains fewer than N POIs, supporting variable-density regions. Geohash is simpler and works well with key-value stores; Quadtree is better for highly non-uniform density (e.g., city centres vs. rural areas).
- **Search with expanding rings:** a proximity query at precision level P fetches all POIs in the user's geohash cell and its 8 neighbours. If fewer than K results are found, the search "rings out" by reducing precision (expanding the cell size) and re-querying. This adaptive approach avoids over-fetching in dense areas while still returning results in sparse regions.
- **Read/write path separation:** reads (search queries) are served from read replicas and a Redis-backed geo-cache to minimise latency (target < 200 ms). Writes (location updates, new POIs) go to the primary Spatial Index DB and asynchronously invalidate or update affected cache cells. This separation allows independent scaling of the read-heavy workload (50 k QPS) from the low-throughput write path.
- **Location update pipeline:** for moving POIs (e.g., delivery drivers), a dedicated ingestion service accepts batched GPS updates over a persistent connection (WebSocket or gRPC stream). Updates are coalesced (latest-wins per entity within a 5-second window) and flushed to the Spatial DB in bulk, reducing write amplification. Stale locations (no update in > 10 minutes) are flagged and excluded from search results.
- **Caching hot geohash cells:** popular cells (city centres, tourist areas) are pre-warmed in Redis using the `GEOADD` / `GEORADIUS` commands. Cache entries are keyed by `geo:<precision>:<cell>` with a TTL proportional to the cell's write frequency (e.g., 60 s for high-churn, 10 min for static business listings). Cache-aside pattern ensures cache freshness without write-through overhead.
- **Result ranking and filtering:** raw spatial results are post-filtered by category, rating, open-now status, and user preferences. Ranking incorporates distance, relevance score (text match if keyword search is combined), and business quality signals. Final results are paginated and returned with distance annotations.
- **Sharding by geohash prefix:** the Spatial Index DB is sharded on the first N characters of the geohash key. This co-locates geographically nearby POIs on the same shard, enabling single-shard neighbour queries. Hot shards (e.g., Manhattan) are split further or assigned to higher-capacity nodes.
- **Multi-resolution support:** the API accepts a `radius` parameter and dynamically selects the appropriate geohash precision level. Small radii (< 1 km) use precision 6–7; large radii (50 km) use precision 4–5. This avoids scanning an excessive number of cells for wide searches.

### Trade-offs

- Geohash vs. Quadtree: Geohash is simpler to implement on top of existing sorted indexes and distributes well across shards, but suffers from edge effects at cell boundaries (two physically close POIs can fall into non-adjacent cells); Quadtrees handle variable density gracefully but require custom in-memory data structures and are harder to distribute.
- Caching full result sets vs. caching raw POI data: caching pre-built result pages per cell is faster for repeated queries but wastes memory on low-traffic cells and makes personalised ranking harder; caching individual POI records is more flexible but requires assembling and ranking results on every request.
- Precision vs. recall in expanding ring search: starting at high precision returns fewer, more relevant results quickly but may miss nearby POIs across cell boundaries; starting at low precision guarantees completeness but returns more data that must be filtered and sorted.

## 4. Operational Excellence

### SLIs / SLOs
- SLO: 99.9% of search queries return results within 200 ms.
- SLO: Location updates reflected in search results within 30 seconds (eventual consistency target).
- SLIs: search_latency_p99, cache_hit_ratio_by_cell_precision, location_update_lag_p95, query_result_count_avg, shard_hotspot_qps.

### Monitoring & Alerts (examples)

Alerts:

- `search_latency_p99 > 500ms` for 3m
    - Severity: P1 (investigate cache misses, slow shard, or query fan-out issues).
- `cache_hit_ratio < 80%` (5m)
    - Severity: P2 (hot cells may have been evicted; review TTL policy or scale cache).
- `location_update_lag_p95 > 60s`
    - Severity: P2 (ingestion pipeline may be backlogged; scale consumers or check DB write throughput).

### Testing & Reliability
- Validate spatial accuracy by running a suite of known-distance test cases (golden set of POI pairs with pre-computed distances) against the search API.
- Load-test with geographically realistic query distributions (zipfian over city centres) at 2× peak QPS to verify cache effectiveness and tail latency.
- Chaos-test shard failover: take one geohash shard offline and verify queries gracefully degrade (return partial results or expand to neighbouring shards).

### Backups & Data Retention
- Replicate the Spatial Index DB across availability zones; take daily snapshots for disaster recovery.
- Retain raw GPS update logs for 7 days in a streaming store for replay and debugging.
- Archive historical POI data (closures, relocations) for analytics and data quality auditing.
