---
title: "Data Pipelines"
description: "Time semantics, fault tolerance, etc. for batch/streaming."
summary: "Principles for reliable batch and streaming pipelines: time semantics, fault tolerance, partitioning, observability, and reproducibility."
tags: ["data-pipelines", "etl", "streaming"]
categories: ["principles"]
draft: false
---

## 1. Time Semantics

Choose batch processing (Spark) for bounded, rebuiltable datasets and streaming (Flink) for continuous, low-latency updates. For correctness, prefer event-time with watermarks to handle late-arriving data rather than processing-time which varies with system load.

## 2. Fault Tolerance & State

Use checkpointing with durable state backends (RocksDB, S3) and implement recovery tests—storing state in memory makes failures expensive and limits scalability. Include state TTL cleanup policies for long-running jobs.

## 3. Partitioning & Parallelism

Partition data by logical keys to expose parallelism and monitor for skew. Repartition dynamically if certain keys are processing much faster or slower than others, as skew is often the root cause of latency problems.

## 4. IO & Schema

Prefer columnar formats (Parquet/ORC) for analytics and use transactional, durable sinks for streaming. Evolve schemas explicitly with versions and migrations rather than loose compatibility.

## 5. Idempotence & Exactly-once Semantics

Design sinks to be idempotent under retries and rely on transactional semantics at boundaries. End-to-end exactly-once is hard; build idempotence instead so retries don't cause duplicate side effects.

## 6. Backpressure & Flow Control

Use backpressure-friendly sources and runners to prevent downstream overload. If a consumer starts falling behind, the system should slow the source rather than buffering unbounded data.

## 7. Observability & Metrics

Emit structured metrics for throughput, lag, and backlog. Distributed tracing helps debug complex pipelines where data flows through many stages and services.

## 8. Runner Portability vs. Runtime Features

Use Apache Beam for cross-runner portability when deployment flexibility matters, but leverage native APIs (Flink, Spark) when you need advanced optimizations. Portability is valuable until performance becomes critical.

## 9. Testing & Reproducibility

Provide deterministic test datasets and record seed values and runtime configs to make failures reproducible. Automated end-to-end tests that validate output schema and row counts catch silent correctness bugs.

## 10. Cost & Resource Efficiency

Optimize partition counts to avoid excessive task creation and minimize intermediate materializations. Profile IO hotspots and serialize formats for read/write-heavy workloads; estimate cloud egress and storage costs upfront.

## 11. Development Ergonomics

Keep example pipelines minimal with clear steps for switching runners and extract shared helpers to reduce duplication. Good templates and documentation multiply the productivity of new pipeline developers.

## 12. Security & Data Privacy

Mask or encrypt sensitive fields in transit and at rest, limit data retention with automatic cleanup of intermediate artifacts, and document access controls. Privacy is harder to retrofit than to bake in from the start.
