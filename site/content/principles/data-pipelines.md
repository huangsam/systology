---
title: "Data Pipelines"
description: "Time semantics, fault tolerance, partitioning, and observability for batch/streaming pipelines."
summary: "Principles for reliable batch and streaming pipelines: time semantics, fault tolerance, partitioning, observability, and reproducibility."
tags: ["data-pipelines","etl","streaming"]
---

1. Time Semantics
    - Batch vs Streaming: choose batch (Spark) for large-scale ETL and analytics; streaming (Flink) for low-latency, continuous processing. Beam provides a programming model that spans both.
    - Event-time vs Processing-time: prefer event-time with watermarks where correctness matters (late data); use processing-time for simple, low-latency demos.

2. Fault Tolerance & State
    - Use checkpointing and durable state backends (RocksDB, filesystem, S3/HDFS) for stateful operators.
    - Ensure tests for recovery and idempotence after failures.
    - Implement state TTL and cleanup policies for long-running jobs.

3. Partitioning & Parallelism
    - Partition/shard data by logical keys to expose parallelism and minimize skew.
    - Tune parallelism levels to balance throughput, latency, and resource usage.
    - Monitor partition distribution and repartition when skew is detected.

4. IO & Schema
    - Prefer partitioned, columnar formats (Parquet/ORC) for analytics workloads.
    - Use durable, transactional sinks for streaming to ensure data consistency.
    - Validate and evolve schemas carefully with explicit migrations and backward compatibility.

5. Idempotence & Exactly-once Semantics
    - Design sinks and downstream effects to be idempotent under retries.
    - Use transactional or deduplicating sinks for exactly-once guarantees.
    - Ensure watermarking and event-time processing for correctness in streaming.

6. Backpressure & Flow Control
    - Use backpressure-friendly sources and runners to handle variable load.
    - Tune buffer sizes and batching to avoid out-of-memory errors.
    - Implement rate-limiting for upstream producers in streaming scenarios.

7. Observability & Metrics
    - Emit structured metrics for throughput, latency, and backlog monitoring.
    - Add alerts for increasing lag, error rates, and state size growth.
    - Use distributed tracing for complex pipeline debugging.

8. Runner Portability (Beam) vs Runtime Features
    - Use Beam for cross-runner portability when deployment flexibility is key.
    - Leverage native Flink/Spark APIs for advanced runtime optimizations.
    - Balance abstraction benefits against performance needs when choosing frameworks.

9. Testing & Reproducibility
    - Provide small, deterministic sample datasets and unit/integration tests for pipelines. Record seed values, environment, and runner configs for reproducible runs.

10. Cost & Resource Efficiency
    - Optimize partition counts, avoid excessive materialization, and profile IO hotspots. For cloud runs, estimate egress and storage costs.

11. Development Ergonomics
    - Keep example pipelines minimal and document runner-switch steps. Extract common helpers (data generators, test harnesses) into a shared folder to reduce duplication across trials.

12. Cross-cutting: Security & Data Privacy
    - Mask or encrypt sensitive fields, limit data retention, and document access controls for intermediate artifacts.
