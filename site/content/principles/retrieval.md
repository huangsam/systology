---
title: "Retrieval & RAG"
description: "Principles for building robust retrieval systems and retrieval-augmented generation (RAG) pipelines"
summary: "Core principles for robust retrieval and RAG: hybrid retrieval, embedding stability, evaluation, and privacy-aware indexing."
tags: ["retrieval","search"]
categories: ["principles"]
---

1. Local Vector Store Hygiene
    - Version vector indices to track changes and enable rollbacks.
    - Prune stale or irrelevant vectors to control storage and improve performance.
    - Maintain document provenance metadata for audit and debugging.

2. Hybrid Retrieval Strategy
    - Combine lexical (BM25) and semantic (embeddings) for robust retrieval.
    - Tune fusion weights (e.g., Reciprocal Rank Fusion) per query intent class.
    - Experiment with query expansion and reranking for improved accuracy.

3. Embedding Stability
    - Pin embedding models and versions to ensure consistent representations.
    - Re-embed documents only when models or data schemas change.
    - Use model versioning and artifact management for reproducibility.

4. Evaluation & Benchmarks
    - Automate MAP@k and MRR metrics with synthetic test suites.
    - Use LLM-as-judge for qualitative evaluation but validate against human labels.
    - Maintain small, curated dev sets for quick iteration and regression testing.

5. Latency vs Quality Trade-offs
    - Cache results for frequent queries to reduce latency.
    - Use approximate nearest neighbors (ANN) for large-scale vector search.
    - Limit rerank window sizes to balance quality and speed.

6. Privacy & Locality
    - Default to local embeddings and LLMs to minimize data exposure.
    - Require explicit consent for cloud services with clear data flow documentation.
    - Implement data retention policies and automatic cleanup of temporary artifacts.

7. Ingestion & Incrementality
    - Support incremental indexing to avoid full rebuilds on updates.
    - Ensure idempotent ingest operations for fault tolerance.
    - Use lightweight diff detection to identify changed documents efficiently.

8. Monitoring & Drift Detection
    - Track relevance metrics and query performance over time.
    - Detect embedding drift through periodic re-evaluation of baselines.
    - Schedule automated re-indexing when semantic changes are detected.
