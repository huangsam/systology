---
title: "Ragchain"
description: "Retrieval-augmented generation with search and ML."
summary: "Local RAG stack (Chroma + Ollama) for private, reproducible retrieval and LLM usage; focuses on hybrid retrieval, index versioning, and evaluation."
tags: ["ml", "privacy", "retrieval"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/ragchain"
draft: false
---

## Context — Problem — Solution

**Context:** `ragchain` is a local-first RAG (Retrieval-Augmented Generation) stack built on Chroma for vector storage and Ollama for local LLM inference. Everything runs on-device—embeddings, vector search, BM25 retrieval, and LLM generation—ensuring that user documents and queries never leave local infrastructure.

**Motivation:** I have a deep interest in asking insightful questions about programming languages from time to time. One of the websites I keep coming back to is TIOBE, which has all the numbers but not as much about the language or the underlying concepts itself. When I want to try out a new language on that list, I want a chatbot that can answer questions about the language, its history, and its ecosystem based on the TIOBE content.

## The Local Implementation

- **Current Logic:** Documents are ingested via a CLI (`ragchain ingest`) that chunks text with configurable size and overlap (default 2500 chars / 500 overlap), generates embeddings via Ollama's local embedding model (qwen3-embedding), and stores vectors in Chroma with document metadata. A parallel BM25 index (rank_bm25) is built over the same chunks for lexical retrieval. Queries are served via `ragchain ask`, which uses LangGraph to orchestrate intent-based adaptive retrieval—classifying queries as FACT, CONCEPT, or COMPARISON and adjusting BM25/vector weights accordingly—then combines results using RRF (score = Σ 1/(k + rank) across retrievers) and feeds the top-k chunks as context to Ollama for generation.
- **Hybrid retrieval details:** BM25 excels at exact keyword matches (error codes, proper nouns, specific terms) while semantic search handles paraphrases and conceptual queries. The intent router classifies queries and assigns retrieval weights: FACT queries use 0.8 BM25 / 0.2 Chroma (keyword-heavy for enumerations), CONCEPT queries use 0.4 BM25 / 0.6 Chroma (balanced), and COMPARISON queries use 0.3 BM25 / 0.7 Chroma (semantic-heavy). A document relevance grader validates retrieved results, and automatic query rewriting retries retrieval on failure (max 1 retry).
- **Self-correcting pipeline:** the LangGraph orchestrator implements a conditional retry loop—if the grader deems retrieved documents irrelevant, the query rewriter enhances the query and re-retrieves. This self-correcting behavior significantly improves answer quality for ambiguous or poorly-phrased queries.
- **Privacy architecture:** no data leaves the device. Ollama runs models locally (currently qwen3 for generation, qwen3-embedding for embeddings), Chroma stores vectors on local disk or via a local Docker container, and the BM25 index is an in-memory structure rebuilt from local documents.
- **Bottleneck:** Embedding generation is the ingestion bottleneck—Ollama on CPU can be slow per chunk, making large re-indexing runs time-consuming. Memory footprint grows with corpus size (Chroma vectors + BM25 term frequencies). The default corpus covers 50 programming languages plus 10 conceptual bridge pages, and extending to larger domains requires attention to chunk sizing and retrieval parameter tuning.

## Scaling Strategy

- **Vertical vs. Horizontal:** For larger corpora, shard indices by domain or document collection and serve queries to a coordinating aggregator that merges RRF-fused results across shards. Use incremental indexing (content-hash-based diff detection) to avoid full re-embedding when only a few documents change—this reduces update cost from O(N) to O(changed).
- **State Management:** Version vector indices with manifests, snapshot ingestion cursors (last-processed document hash), and store provenance metadata for all indexed documents. Use Docker Compose + Makefiles for reproducible local stacks. Maintain a mapping from document IDs to vector IDs for efficient deletion of stale vectors.

## Comparison to Industry Standards

- **My Project:** Local-only RAG with explicit reproducibility and privacy guarantees. No cloud dependencies. Hybrid retrieval with systematic evaluation. Suitable for personal knowledge bases and privacy-sensitive domains.
- **Industry:** Cloud RAG offerings (Pinecone + OpenAI, Weaviate Cloud, Amazon Kendra) provide managed scaling, automatic sharding, and access to powerful embedding/generation models, but trade off privacy, repeatability, and cost transparency. They also abstract away retrieval tuning, making quality debugging opaque.
- **Gap Analysis:** To reach production-grade scale and latency: implement persistent sharding with cross-shard query routing, add ANN (HNSW) search for indices beyond 1M vectors (Chroma uses exact search by default), integrate monitoring for retrieval quality drift (track average relevance scores over time), and build a reranker layer (cross-encoder on top-50 results) to recover precision lost by approximate search.

## Risks & Mitigations

- **Stale embeddings:** incremental re-embedding on document change detection (content hash comparison). Schedule periodic full re-index validation that compares incremental vs. clean-build index quality to detect accumulated drift.
- **Resource exhaustion:** provide configurable limits on corpus size and in-memory BM25 index size. Guide users to shard or prune indices when memory exceeds thresholds. Document minimum hardware requirements per corpus size.
- **Embedding model drift:** pin embedding model versions in the index manifest. When upgrading models, re-embed the entire corpus atomically and compare retrieval quality before and after using the evaluation suite.
- **LLM hallucination:** log the retrieved context alongside generated answers for auditability. Surface retrieval confidence scores to the user so low-confidence answers are flagged rather than presented as authoritative.
