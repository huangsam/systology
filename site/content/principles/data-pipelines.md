---
title: "Data Pipelines"
description: "Time semantics, fault tolerance, etc. for batch/streaming."
summary: "Principles for reliable batch and streaming pipelines: time semantics, fault tolerance, partitioning, observability, and reproducibility."
tags: ["data-pipelines", "etl", "streaming"]
categories: ["principles"]
draft: false
---

## Time Semantics

Choose batch processing (Spark) for bounded, rebuiltable datasets and streaming (Flink) for continuous, low-latency updates. For correctness, prefer event-time with watermarks to handle late-arriving data rather than processing-time which varies with system load.

Event-time processing answers the question "when did this actually happen?" rather than "when did the system see it?" This distinction is critical for analytics correctness—a click that happened at 11:59 PM should land in yesterday's report even if it arrives at 12:03 AM. Watermarks define "how long do we wait for stragglers?" and directly control the latency-completeness tradeoff.

**Anti-pattern — Processing-time Everything:** Using processing-time windows because they're simpler. This works until data arrives out of order (network delays, partition lag, mobile offline sync), at which point your aggregates silently become wrong. Use event-time from the start and save yourself a painful migration later.

## Fault Tolerance & State

Use checkpointing with durable state backends (RocksDB, S3) and implement recovery tests—storing state in memory makes failures expensive and limits scalability. Include state TTL cleanup policies for long-running jobs.

Checkpointing serializes your pipeline's state to durable storage at regular intervals. On failure, the pipeline restarts from the last checkpoint rather than reprocessing everything from scratch. The checkpoint interval is a tradeoff: frequent checkpoints reduce data loss but increase overhead; infrequent checkpoints are cheaper but lose more work on failure.

**Anti-pattern — In-Memory-Only State:** Keeping all state in heap memory because it's fast. When the process crashes (and it will), you lose everything and must reprocess from the beginning. For a 6-hour batch job, this means 6 hours of wasted compute. Always persist state to a durable backend, even if it adds latency.

**Anti-pattern — No State TTL:** Letting keyed state grow unboundedly in long-running streaming jobs. If you window by user ID but never expire old users, your state store grows forever until it OOMs. Set explicit TTL policies to evict stale keys.

## Partitioning & Parallelism

Partition data by logical keys to expose parallelism and monitor for skew. Repartition dynamically if certain keys are processing much faster or slower than others, as skew is often the root cause of latency problems.

Good partition keys distribute work evenly and group related records together. Partition by `user_id` if you need per-user aggregation; by `region` if you need geographic grouping. The key choice directly determines your maximum parallelism and whether one worker gets 90% of the load.

**Anti-pattern — Hot Key Blindness:** Partitioning by a key with a Zipfian distribution (e.g., a viral tweet's ID, a celebrity user) and wondering why one task takes 100x longer than others. Monitor partition sizes in your pipeline's metrics and add salting or pre-aggregation for known hot keys.

See the [Ad Click Aggregator]({{< ref "/designs/ad-click-aggregator" >}}) design for a production example of event-time windowed aggregation with partition-aware scaling.

## IO & Schema

Prefer columnar formats (Parquet/ORC) for analytics and use transactional, durable sinks for streaming. Evolve schemas explicitly with versions and migrations rather than loose compatibility.

Columnar formats dramatically reduce IO for analytical queries that touch a subset of columns—reading 3 columns from a 50-column table is 15x less IO with Parquet than row-oriented CSV. For streaming sinks, use append-only, idempotent writes to avoid partial state on failure.

**Anti-pattern — CSV in Production:** Using CSV as an interchange format for pipelines. CSVs lack schema enforcement, type safety, compression, and column pruning. A malformed row (unescaped comma in a text field) silently corrupts downstream processing. Use Parquet or Avro with explicit schemas.

**Anti-pattern — Schema-on-Read Everywhere:** Deferring all schema validation to the consumer ("we'll figure out the types later"). This pushes errors downstream where they're harder to debug and creates implicit contracts that break silently when producers change.

## Idempotence & Exactly-once Semantics

Design sinks to be idempotent under retries and rely on transactional semantics at boundaries. End-to-end exactly-once is hard; build idempotence instead so retries don't cause duplicate side effects.

The practical approach: use upserts keyed on `(partition, offset)` or `(window_key, window_start)` rather than blind inserts. If a task retries and writes the same record again, the upsert overwrites identically rather than creating a duplicate. This gives you exactly-once *effect* without the complexity of distributed transactions.

See the [Realtime Analytics]({{< ref "/designs/realtime-analytics" >}}) design for a deeper treatment of exactly-once semantics in streaming architectures.

**Anti-pattern — Append-only Without Dedup:** Writing to a sink that only supports appends (e.g., a log file, a Kafka topic) without tracking what's already been written. On retry, you get duplicates that silently inflate your metrics. Always pair appends with a dedup mechanism at the consumer.

## Backpressure & Flow Control

Use backpressure-friendly sources and runners to prevent downstream overload. If a consumer starts falling behind, the system should slow the source rather than buffering unbounded data.

Backpressure is gravity for data pipelines—ignore it and things pile up. Flink handles this natively through its credit-based flow control. Spark Structured Streaming uses micro-batch sizing. Kafka consumers can pause partitions when the processing queue is full. The key insight: slowing the source is always safer than buffering unbounded data in memory.

**Anti-pattern — Unbounded Buffers:** Using an in-memory queue between pipeline stages without a size limit. When the downstream stage slows down, the queue grows until OOM. Always set buffer limits and propagate backpressure upstream.

## Observability & Metrics

Emit structured metrics for throughput, lag, and backlog. Distributed tracing helps debug complex pipelines where data flows through many stages and services.

At minimum, track: records-per-second (throughput), consumer lag (how far behind real-time), checkpoint duration, and error rates by stage. For streaming pipelines, watermark progression tells you whether event-time processing is keeping up. Dashboards should show these at both pipeline and per-stage granularity.

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for a comprehensive treatment of SLOs, alerting, and dashboard design.

## Runner Portability vs. Runtime Features

Use Apache Beam for cross-runner portability when deployment flexibility matters, but leverage native APIs (Flink, Spark) when you need advanced optimizations. Portability is valuable until performance becomes critical.

Beam's unified model lets you write once and deploy on Flink, Spark, Dataflow, or Samza. But each runner has unique strengths: Flink's savepoints and exactly-once, Spark's SQL optimizer, Dataflow's autoscaling. When you need those features, the Beam abstraction becomes a constraint rather than a benefit.

See [Beam Trial]({{< ref "/deep-dives/beam-trial" >}}) for hands-on runner comparison and [Flink Trial]({{< ref "/deep-dives/flink-trial" >}}) for native Flink features that go beyond Beam's portable surface.

**Anti-pattern — Abstraction Lock-in:** Choosing Beam for portability but then using runner-specific transforms everywhere, getting neither portability nor native performance. Commit to one approach: portable Beam *or* native runner APIs. The middle ground is the worst of both worlds.

## Testing & Reproducibility

Provide deterministic test datasets and record seed values and runtime configs to make failures reproducible. Automated end-to-end tests that validate output schema and row counts catch silent correctness bugs.

Structure pipeline tests in three tiers: (1) unit tests for individual transforms with in-memory collections, (2) integration tests that run mini-pipelines against local runners with fixture data, and (3) end-to-end regression tests that compare output against golden datasets. Record the full configuration (runner version, parallelism, configs) alongside test results.

**Anti-pattern — "It Worked on My Laptop":** Testing only with the DirectRunner / local mode and assuming it'll behave identically on a cluster. Runner-specific behaviors (serialization, parallelism, shuffle) surface only at scale. Test on a staging cluster with production-like data volumes before deploying.

## Cost & Resource Efficiency

Optimize partition counts to avoid excessive task creation and minimize intermediate materializations. Profile IO hotspots and serialize formats for read/write-heavy workloads; estimate cloud egress and storage costs upfront.

Each partition creates scheduling overhead—1000 partitions with 1 KB each is far less efficient than 10 partitions with 100 KB each. Similarly, intermediate materializations (writing to disk between stages) are expensive in cloud environments where storage and egress cost money. Use pipeline fusion where possible to keep data in memory between stages.

**Anti-pattern — Partition Explosion:** Setting `spark.sql.shuffle.partitions=10000` "for safety" when your dataset has 1 GB. The scheduling overhead per partition dwarfs the actual processing time. Profile your data size and set partitions proportional to the work.

## Development Ergonomics

Keep example pipelines minimal with clear steps for switching runners and extract shared helpers to reduce duplication. Good templates and documentation multiply the productivity of new pipeline developers.

Provide a `quickstart` template that a new developer can clone, run locally, see output, and modify within 15 minutes. Include runner-switching instructions (e.g., `--runner=FlinkRunner`) and document common gotchas (classpath issues, serialization requirements, dependency conflicts). Extract IO connectors and transform utilities into a shared library so pipeline authors focus on business logic.

## Security & Data Privacy

Mask or encrypt sensitive fields in transit and at rest, limit data retention with automatic cleanup of intermediate artifacts, and document access controls. Privacy is harder to retrofit than to bake in from the start.

Implement field-level encryption or tokenization for PII columns at ingestion time, before the data enters your pipeline. Use role-based access control for pipeline artifacts and intermediate storage. Set lifecycle policies on cloud storage to auto-delete staging data after a configurable retention window.

See the [Privacy & Agents]({{< ref "/principles/privacy-agents" >}}) principles for deeper guidance on data minimization and consent in automated systems.

**Anti-pattern — PII in Logs:** Logging full records (including names, emails, IPs) for debugging convenience. A single log aggregation query can expose millions of users' data. Redact PII at the logging boundary and use synthetic IDs for debugging.

## Decision Framework

Choose your pipeline architecture based on data volume and latency requirements:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Absolute Accuracy** | Batch (Event-time) | Easiest to rebuild and verify from raw source of truth. |
| **Sub-second Insights**| Streaming (Flink) | Processes events as they arrive; handles late data. |
| **High Reproducibility**| Immutable Sinks | Avoids side-effects, making re-runs safe and atomic. |
| **Operational Simplicity**| Cloud-Native Managed | Removes infrastructure toil at the cost of knob-tuning. |

**Decision Heuristic:** "Choose **Idempotent Sinks** over complex transactions. It's cheaper to make retries safe than to make failures impossible."
