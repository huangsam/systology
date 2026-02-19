---
title: "Search & Retrieval Engine"
description: "High-performance document search."
summary: "Design a high-performance search and retrieval engine for large document/media collections with low-latency ranking and scalable indexing."
tags: ["monitoring", "privacy", "retrieval"]
categories: ["designs"]
draft: false
---

## 1. Problem Statement & Constraints

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
    - Read:Write ratio: ~99:1 (searches >> document updates)
    - QPS: avg 500k / peak 1M queries/sec
    - Avg payload: 100 B–5 KB per query; 10–100 KB per result page
    - Key skew: extreme (popular queries get 80% traffic)
    - Retention: indefinite (search index); document snapshots for versioning

## 2. High-Level Architecture

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

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Inverted index:** build a term-to-posting-list index for full-text search. Store positional information for phrase queries and proximity scoring. Use immutable segments with periodic merges (LSM-tree style) to support efficient writes without blocking reads. Compress posting lists with variable-byte or PForDelta encoding to reduce I/O.
- **Hybrid ranking (BM25 + embeddings):** combine lexical scoring (BM25 / TF-IDF) with semantic scoring from dense vector embeddings. First-stage retrieval uses the inverted index for candidate generation (top-1000), then a re-ranker applies a cross-encoder or learned-to-rank model on the candidate set to produce the final top-K results. This two-stage approach balances recall and precision efficiently.
- **Sharding and replication:** partition the index by document hash across N shards. Each shard has R replicas for fault tolerance and read throughput. Use a scatter-gather pattern: the query is sent to all shards in parallel, each returns its local top-K, and the gather layer merges and re-ranks across shards.
- **Index refresh and near-real-time search:** new or updated documents are written to a write-ahead log and a small in-memory segment (refreshed every 1–5 seconds). Periodic background merges compact small segments into larger ones. This provides near-real-time searchability without the cost of per-document index commits.
- **Query processing pipeline:** parse the query, expand with synonyms, apply spell correction, and rewrite using learned query-rewriting models. Support filters (facets, date ranges, ACLs) as bit-set intersections applied before scoring to reduce the candidate set early.
- **Relevance tuning and feedback:** log click-through data and use it to train learning-to-rank models. Run online A/B tests on ranking changes. Provide an explain API that returns the scoring breakdown for debugging relevance issues.
- **Multi-tenancy and access control:** enforce per-tenant index isolation (separate shards or filtered aliases) and document-level ACLs evaluated at query time. Use Bloom filters on ACL fields to quickly skip unauthorised documents during posting-list traversal.

### Trade-offs

- Lexical vs. semantic search: BM25 is fast, interpretable, and requires no GPU, but misses semantic similarity (synonyms, paraphrases); dense vector search captures meaning but is compute-intensive and harder to debug. Hybrid balances both at the cost of pipeline complexity.
- Near-real-time vs. batch indexing: NRT indexing (1–5 s refresh) satisfies most use cases but adds memory pressure and compaction overhead; batch indexing (minutes/hours) is simpler but delays document visibility.
- Scatter-gather vs. single-node: scatter-gather scales horizontally and handles larger corpora but adds network hops and merge overhead; a single large node is simpler when the index fits in memory.

## 4. Operational Excellence

### SLIs / SLOs
- SLO: P99 query latency < 50 ms for keyword search; < 150 ms for hybrid (keyword + vector) search.
- SLO: 99.99% availability of the search API.
- SLIs: query_latency_p99, index_freshness_lag, query_error_rate, recall_at_k, shard_replica_lag.

### Monitoring & Alerts (examples)

Alerts:

- `query_latency_p99 > 40ms` for 5m
    - Severity: P2 (approaching SLO; investigate slow shards or heavy queries).
- `shard_replica_lag > 30s`
    - Severity: P2 (replica falling behind; check replication health and network).
- `query_error_rate > 0.1%` (5m)
    - Severity: P1 (search API errors; check shard health and query parsing).

### Testing & Reliability
- Run nightly relevance evaluation suites (NDCG, MAP, recall@K) against labelled query-document pairs; fail CI if metrics drop below baseline.
- Load-test at 2× peak QPS with representative query distributions; verify latency SLOs hold and no shard becomes a bottleneck.
- Chaos-test: take down individual shard replicas and verify that the scatter-gather layer routes around failures transparently.

### Backups & Data Retention
- Source documents are authoritative; the index can be rebuilt from source. Keep index snapshots for fast recovery (rebuild time < 1 hour for full corpus).
- Retain search query logs (anonymised) for 90 days for relevance tuning and analytics.
- Archive click-through and A/B test data indefinitely for long-term ranking model training.
