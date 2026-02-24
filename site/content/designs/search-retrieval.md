---
title: "Search & Retrieval Engine"
description: "High-performance document search."
summary: "Design a high-performance search and retrieval engine for large document/media collections with low-latency ranking and scalable indexing."
tags: ["monitoring", "privacy", "retrieval"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design a high-performance search and retrieval engine to index and query large volumes of documents or media, providing fast and relevant results. The system must handle massive query loads, ensure eventual consistency for updates, and maintain sub-millisecond response times while supporting advanced ranking and filtering features.

### Functional Requirements

- Index and search large document/media collections.
- Support full-text search, filtering, and faceting.
- Provide relevance ranking and result explanations.
- Handle real-time index updates.

### Non-Functional Requirements

- **Scale:** 1M queries/sec; index 1B+ documents.
- **Availability:** 99.99% query availability.
- **Consistency:** Eventual consistency for index updates (1–5 second delay).
- **Latency:** P99 < 50ms for query response.
- **Workload Profile:**
    - Read:Write ratio: ~99:1
    - Peak throughput: 1M queries/sec
    - Retention: indefinite search index; document versioning

## High-Level Architecture

{{< mermaid >}}
graph TD
    Query["Query Input"] --> QP["Query Parser"]
    QP --> Scatter["Scatter (Parallel)"]
    Scatter --> Shard1["Shard 1 (Local RankK)"]
    Scatter --> Shard2["Shard 2 (Local RankK)"]
    Scatter --> ShardN["Shard N (Local RankK)"]
    Shard1 --> Gather["Gather & Merge"]
    Shard2 --> Gather
    ShardN --> Gather
    Gather --> Ranker["Re-Ranker"]
    Ranker --> Results["Top-K Results"]
    Indexer["Index Writer"] -.->|updates| Shard1
    Indexer -.->|updates| Shard2
    Indexer -.->|updates| ShardN
{{< /mermaid >}}

A Query Parser scatters inputs across multiple shards. Each shard executes parallel Local Rank-K retrievals combining lexical and semantic signals. A Scatter-Gather coordinator merges shard results, passing candidates through an ML Re-Ranker to optimize the final Top-K absolute order. An independent Index Writer continuously streams updates into shards.

## Data Design

An Inverted Index combines an in-memory dictionary with compressed on-disk posting lists for rapid keyword search. A Vector Store leverages HNSW proximity graphs for dense semantic search alongside JSON metadata for exact faceting.

### Inverted Index (SSTables/Segments)
| Component | Structure | Description | Storage |
| :--- | :--- | :--- | :--- |
| **Dictionary** | Sorted Term Map | Term string to Offset lookup. | Memory/Cache |
| **Postings** | PForDelta List | Compressed document IDs + counts. | Disk |
| **Positions** | Delta-coded | Token offsets for phrase queries. | Disk |

### Vector Store (HNSW/IVF)
| Field | Type | Dim | Purpose |
| :--- | :--- | :--- | :--- |
| **doc_embedding** | Float16 Vector| 768 | Semantic similarity search. |
| **hnsw_graph** | Proximity Graph| N/A | Fast approximate NN search. |
| **doc_metadata** | JSON | N/A | Filtering/Faceting after retrieval. |

## Deep Dive & Trade-offs

### Deep Dive

- **Inverted index:** PForDelta-compressed posting lists with positional data use immutable segments and LSM merges to guarantee non-blocking reads.

- **Hybrid ranking:** BM25 lexical candidate generation combines with dense vector semantic embeddings in a two-stage cross-encoder re-ranking pipeline.

- **NRT index refresh:** In-memory segments backed by a WAL refresh every 1–5 seconds, providing near real-time searchability without synchronous commit costs.

- **Query pipeline:** Resolves synonyms and spelling before utilizing bit-set intersections for facets and ACLs to densely prune before scoring.

- **Relevance feedback loops:** Click-through telemetry implicitly trains learning-to-rank models, aided by an explicit `explain` API for tuning breakdowns.

- **Security & Multi-tenancy:** Shard-level tenant isolation pairs with Bloom filters on document ACLs to rapidly skip unauthorized tokens during traversal.

### Trade-offs

- **Lexical vs. Semantic Search:** Lexical (BM25) is fast/interpretable; Semantic (Vector) captures meaning but is GPU-heavy. Hybrid balances both at the cost of complexity.

- **NRT vs. Batch Indexing:** NRT (1–5s) provides immediate visibility but adds memory/compaction pressure; Batch is more efficient but delays document availability.

- **Scatter-Gather vs. Single-Node:** Scatter-Gather scales horizontally for massive corpora but adds network hops; Single-Node is simpler but limited by machine capacity.

## Operational Excellence

### SLIs / SLOs

- SLO: P99 query latency < 50 ms for keyword search; < 150 ms for hybrid (keyword + vector) search.
- SLO: 99.99% availability of the search API.
- SLIs: query_latency_p99, index_freshness_lag, query_error_rate, recall_at_k, shard_replica_lag.

### Monitoring & Alerts

- `query_latency_p99 > 40ms`: Investigate slow shards or heavy queries (P2).
- `shard_replica_lag > 30s`: Check replication health and network (P2).
- `query_error_rate > 0.1%`: Check shard health and query parsing (P1).

### Reliability & Resiliency

- **Relevance**: Nightly evaluation (NDCG, MAP) against labelled query sets.
- **Load**: Test at 2x peak QPS with representative query distributions.
- **Chaos**: Kill shard replicas to verify transparent scatter-gather routing.

### Retention & Backups

- **Index**: Authoritative source allows rebuilds; snapshots for < 1h recovery.
- **Logs**: Anonymized query logs kept 90 days for tuning and analytics.
- **A/B**: Archive click-through and test data indefinitely for model training.
