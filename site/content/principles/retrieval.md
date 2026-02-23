---
title: "Retrieval & RAG"
description: "Building robust retrieval systems and RAG pipelines."
summary: "Core principles for robust retrieval and RAG: hybrid retrieval, embedding stability, evaluation, and privacy-aware indexing."
tags: ["retrieval"]
categories: ["principles"]
draft: false
---

## Local Vector Store Hygiene

Version vector indices to enable rollbacks and prune stale vectors to control storage costs. Maintain provenance metadata for audit and understand what you're indexing.

Treat your vector index like a database: it has versions, needs backups, and accumulates cruft. Use a naming convention like `index_v{N}_{timestamp}` and maintain a manifest that maps each index version to the embedding model, chunking strategy, and source document set that produced it. Prune vectors for deleted or updated documents on a schedule. Without provenance metadata, you can't answer "why did the system retrieve this irrelevant result?"—which makes debugging retrieval quality nearly impossible.

See [Ragchain]({{< ref "/deep-dives/ragchain" >}}) for a local-first RAG implementation that manages vector indices alongside BM25 indices.

**Anti-pattern — Append-only Index Forever:** Adding new vectors without ever removing stale ones. Over time, the index accumulates outdated, deleted, or superseded documents that pollute search results with irrelevant content. A user deletes a page, but the vector persists and surfaces it in searches. Implement garbage collection tied to your document lifecycle.

## Hybrid Retrieval Strategy

Combine lexical (BM25) and semantic retrieval for robustness—neither alone handles all query types well. Tune fusion weights per query intent class and experiment with expansion and reranking.

BM25 excels at exact keyword matches and rare terms (proper nouns, error codes, product IDs). Semantic search handles paraphrases, conceptual queries, and fuzzy matches. For a query like "Python connection pool timeout error," BM25 finds documents containing those exact terms while semantic search finds documents about "database client configuration" that discuss the same concept differently. Reciprocal rank fusion (RRF) or weighted linear combination of scores provides a simple, effective fusion strategy.

See the [Search & Retrieval]({{< ref "/designs/search-retrieval" >}}) design for a production architecture combining BM25 and vector retrieval with reranking at scale.

**Anti-pattern — Semantic-only Retrieval:** Relying exclusively on vector search. Embeddings are great for conceptual similarity but terrible for exact matches: searching for the error code `ERR_CONNECTION_REFUSED` via semantic search returns results about "network problems" rather than the exact error. Hybrid retrieval covers both precision and recall.

## Embedding Stability

Pin embedding model versions to ensure consistent representations and only re-embed when models or schemas change. Unstable embeddings make debugging retrieval mysterious.

An embedding model maps text to a vector space. If you switch models or even update to a new version, the vector space changes—distances between documents shift, and retrieval quality can degrade unpredictably. Pin the exact model version (`sentence-transformers/all-MiniLM-L6-v2@v1.0.0`) and only re-embed the entire corpus when you deliberately upgrade. Test retrieval quality before and after to validate the upgrade.

**Anti-pattern — Auto-updating Embedding Models:** Using `latest` tags for embedding models in production. A model update silently changes the vector space, new documents are embedded differently than old ones, and retrieval quality degrades over weeks as the index becomes a mix of two incompatible vector spaces. Pin versions and re-embed atomically.

## Evaluation & Benchmarks

Automate MAP@k and MRR metrics with synthetic test suites and use LLM-as-judge for qualitative evaluation but validate against human labels. Maintain small dev sets for quick iteration without overfitting.

Build an evaluation suite with: (1) a curated set of 50–200 query-relevance pairs with human-labeled relevance grades, (2) automated metrics (MAP@10, MRR, NDCG@10) computed after each index or model change, and (3) regression tests that fail if metrics drop below a threshold. For RAG systems, evaluate both retrieval (did we fetch the right documents?) and generation (is the answer correct?) separately—a wrong answer from correct documents is a generation problem, not a retrieval problem.

**Anti-pattern — Vibes-based Evaluation:** Testing retrieval by manually typing a few queries and eyeballing results. This catches obvious failures but misses systematic issues (e.g., retrieval works for short queries but fails for long ones, or works for English but fails for other languages). Automated evaluation with diverse query sets catches these patterns.

See the [ML Experiments]({{< ref "/principles/ml-experiments" >}}) principles for guidance on deterministic evaluation and reproducible benchmarking.

## Latency vs. Quality Trade-offs

Cache frequent queries and use approximate nearest neighbors for large-scale search, but time the tradeoff. Rerank only the top-k results to balance quality and speed.

For indices over ~1M vectors, exact nearest neighbor search becomes too slow for real-time queries. Use ANN algorithms (HNSW, IVF) that trade a small recall loss (~2–5%) for 100x speedup. Layer a cross-encoder reranker on top of the ANN's top-50 results to recover quality—the reranker is expensive per-document but cheap when applied to only 50 candidates. Cache the full pipeline result for frequent queries (search logs reveal that 20% of queries account for 80% of traffic).

**Anti-pattern — Exact Search at Scale:** Running brute-force exact nearest neighbor on 10M vectors for every query. Response times of 5–10 seconds destroy user experience. ANN indices sacrifice negligible recall for orders-of-magnitude speedup—the quality difference is invisible to users while the latency difference is not.

## Privacy & Locality

Default to local embeddings and LLMs to minimize data exposure outside your infrastructure. Require explicit opt-in for cloud services with clear data flow documentation.

Run embedding models locally using ONNX Runtime, llama.cpp, or similar lightweight inference runtimes. For LLM generation, local models (Llama, Mistral, Phi) running on-device provide privacy guarantees that cloud APIs cannot. When cloud LLMs are needed for quality (GPT-4, Claude), document the data flow explicitly: which user data is sent, to which endpoint, is it logged by the provider, and what's the retention policy?

See the [Privacy & Agents]({{< ref "/principles/privacy-agents" >}}) principles for comprehensive guidance on local-first defaults and data minimization.

**Anti-pattern — Embedding via Cloud API by Default:** Sending every user query and document chunk to an external embedding API. Even if the provider's privacy policy is acceptable, this creates a dependency on network availability, introduces latency, incurs per-call costs, and sends potentially sensitive content over the wire. Local embedding models eliminate all four concerns.

## Ingestion & Incrementality

Support incremental indexing to avoid rebuilds on every update and ensure ingest operations are idempotent. Use diff detection to identify changed documents efficiently.

For large document collections, full re-indexing is prohibitively expensive. Track document hashes or modification timestamps and only re-embed changed documents. Use a content-addressable storage pattern: hash the document content, check if the hash exists in the index, and skip if unchanged. For deletions, maintain a mapping from document IDs to vector IDs so you can remove stale vectors without scanning the entire index.

See the [Migration & Deduplication]({{< ref "/principles/migration-dedup" >}}) principles for related guidance on idempotent operations and checkpointing that applies to incremental indexing.

**Anti-pattern — Full Re-index on Every Change:** Rebuilding the entire vector index when a single document changes. For a corpus of 100K documents, this means re-embedding all 100K documents (hours of compute) when only one changed. Incremental indexing reduces update cost from O(N) to O(1) per change.

## Monitoring & Drift Detection

Track relevance metrics and query performance over time to detect embedding drift. Schedule automated re-indexing when drift is detected.

Monitor retrieval quality continuously: track average relevance scores, click-through rates on search results, and query-to-no-result ratios over time. A gradual decline in these metrics indicates drift—your corpus has changed but your index hasn't kept up, or the types of queries have shifted away from what your embedding model handles well. Set up automated alerts when metrics drop below baseline and trigger re-indexing or model evaluation.

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for broader guidance on SLIs, alerting, and dashboards that applies to retrieval system monitoring.

**Anti-pattern — Set and Forget:** Building a retrieval system, shipping it, and never monitoring retrieval quality. Over months, document additions, deletions, and updates cause the index to drift. New query patterns emerge that the original model handles poorly. Without monitoring, quality degrades silently until users complain—by which time trust is already eroded.

## Decision Framework

Choose your retrieval strategy based on the structure of the data and the type of queries being performed:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Exact Keyword Match** | Lexical Search (BM25) | Best for names, IDs, and specific technical terminology. |
| **Semantic Meaning** | Vector Search (RAG) | Understands intent and concepts rather than just matching characters. |
| **Complex Relations** | Graph Search | navigates connections between entities (e.g., social networks). |
| **Real-time Updates** | LSM-based Stores | Optimized for high write volumes and point lookups for fresh data. |

**Decision Heuristic:** "Choose **Hybrid Search** (Lexical + Vector) when accuracy is more important than pure semantic novelty."
