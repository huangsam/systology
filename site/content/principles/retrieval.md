---
title: "Retrieval & RAG"
description: "Building robust retrieval systems and RAG pipelines."
summary: "Core principles for robust retrieval and RAG: hybrid retrieval, embedding stability, evaluation, and privacy-aware indexing."
tags: ["retrieval"]
categories: ["principles"]
draft: false
---

## 1. Local Vector Store Hygiene

Version vector indices to enable rollbacks and prune stale vectors to control storage costs. Maintain provenance metadata for audit and understand what you're indexing.

## 2. Hybrid Retrieval Strategy

Combine lexical (BM25) and semantic retrieval for robustness—neither alone handles all query types well. Tune fusion weights per query intent class and experiment with expansion and reranking.

## 3. Embedding Stability

Pin embedding model versions to ensure consistent representations and only re-embed when models or schemas change. Unstable embeddings make debugging retrieval mysterious.

## 4. Evaluation & Benchmarks

Automate MAP@k and MRR metrics with synthetic test suites and use LLM-as-judge for qualitative evaluation but validate against human labels. Maintain small dev sets for quick iteration without overfitting.

## 5. Latency vs. Quality Trade-offs

Cache frequent queries and use approximate nearest neighbors for large-scale search, but time the tradeoff. Rerank only the top-k results to balance quality and speed.

## 6. Privacy & Locality

Default to local embeddings and LLMs to minimize data exposure outside your infrastructure. Require explicit opt-in for cloud services with clear data flow documentation.

## 7. Ingestion & Incrementality

Support incremental indexing to avoid rebuilds on every update and ensure ingest operations are idempotent. Use diff detection to identify changed documents efficiently.

## 8. Monitoring & Drift Detection

Track relevance metrics and query performance over time to detect embedding drift. Schedule automated re-indexing when drift is detected.
