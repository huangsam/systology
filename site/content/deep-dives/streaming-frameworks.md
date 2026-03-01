---
title: "Streaming Frameworks"
description: "Comparative analysis of Beam and Flink streaming frameworks."
summary: "A deep architectural comparison of streaming pipelines: evaluating Apache Beam's portable unified model (Java/DirectRunner) against Apache Flink's native API for stateful processing and fault tolerance."
tags: ["data-pipelines", "monitoring", "streaming"]
categories: ["deep-dives"]
links:
  github:
    - "https://github.com/huangsam/beam-trial"
    - "https://github.com/huangsam/flink-trial"
draft: false
date: "2026-02-16T10:22:20-08:00"
---

## Context & Motivation

**Context:** Both `beam-trial` and `flink-trial` explore real-time stream processing from different angles — Beam via a portable abstraction layer, Flink via its native Java API. Each targets the same fundamental problem: constructing reliable, stateful pipelines that process unbounded data correctly.

**Motivation:** Streaming systems require careful choices around time semantics, state management, fault tolerance, and runner portability. No single framework is universally correct — the right choice depends on whether you need runner portability, native latency/throughput control, or operational simplicity. Exploring both frameworks side-by-side surfaces where the abstraction helps and where it costs you.

## Approach 1: beam-trial

- **Overview:** A minimal Apache Beam pipeline in Java/Gradle using the DirectRunner. Creates an in-memory `PCollection`, applies `MapElements` transforms with a prefixing function, and writes sharded text output via `TextIO.write()`. The DirectRunner executes the pipeline locally in a single JVM, illustrating Beam's core abstractions: `PCollection` as a logical dataset (bounded or unbounded), `PTransform` as a composable operation, and `Coder` for serialization.
- **What worked:** The portable programming model is clean — pipelines are expressed against Beam's API, not a specific runner. This separation of concerns makes it possible to swap runners (DirectRunner → Dataflow → Flink) without rewriting pipeline logic, which is a genuine advantage for multi-cloud or multi-environment deployments.
- **Bottlenecks & Limitations:** DirectRunner executes transforms sequentially in a single JVM, masking real parallelism and operator fusion behavior. IO sharding produces a single shard regardless of configuration. Beam's portable surface also omits Flink-native capabilities (side outputs via `ProcessFunction`, `ValueState`/`MapState`, `RocksDBStateBackend`) — features that matter significantly in production streaming workloads.
- **Production gaps:** Add transforms beyond `MapElements` (GroupByKey, windowed aggregations, side inputs); integrate durable sources/sinks with schema enforcement (Avro/Parquet); implement pipeline-level monitoring and alerting; add orchestration (Airflow, Argo) for scheduling and failure recovery; and tune runner-specific configurations for the target workload.

## Approach 2: flink-trial

- **Overview:** A streaming analytics demo using Flink's native Java API processing simulated IoT sensor events (temperature, humidity, pressure). A `ProcessFunction` validates events and routes invalid ones to a side output (`OutputTag<String>("errors")`). Valid events are keyed by device ID and aggregated in 5-second tumbling windows (min/max/avg per sensor). Results go to a console sink and CSV file sink; errors go to a separate error log. Uses `RocksDBStateBackend` for large state and Flink's credit-based flow control for backpressure.
- **What worked:** Flink's native API exposes capabilities with no Beam equivalent — side outputs for error routing without blocking the main pipeline, per-key `ValueState`/`MapState` for stateful aggregation, incremental checkpointing with RocksDB, and built-in backpressure propagation. The event timestamp field enables a clear migration path from processing-time to event-time windowing with `WatermarkStrategy.forBoundedOutOfOrderness()`.
- **Bottlenecks & Limitations:** Processing-time windows produce non-deterministic results when reprocessing the same data — aggregates differ across runs. Local demo parallelism (1–2 task slots) doesn't surface real backpressure or network shuffle latency. The Flink Web UI and Prometheus integration require additional setup that isn't reflected in the trial.
- **Production gaps:** Implement event-time windowing with watermarks and configurable allowed lateness; add late-data side outputs for events arriving after window closure; build comprehensive dashboards (checkpoint duration, backpressure, watermark lag, records-per-second per operator); integrate a metrics stack (Prometheus + Grafana via Flink's metrics reporters); and automate savepoint management for job upgrades.

## Comparative Analysis

Beam's abstraction layer is its strength and its ceiling. For teams that need runner portability — running the same pipeline on Dataflow in prod and Flink on-prem — Beam's model is the right investment. But the abstraction hides runner-specific behavior (fusion, state backends, backpressure), which makes performance tuning opaque and limits access to Flink's most powerful features.

Flink's native API gives full access to the execution model: you choose state backends, control operator parallelism, configure watermarks and allowed lateness, and observe backpressure directly. The tradeoff is vendor lock-in — a Flink pipeline isn't portable to Dataflow without a rewrite.

For a greenfield streaming system where operational control and latency matter, Flink native is the pragmatic choice. For a multi-runner or hybrid-cloud pipeline where portability is a hard constraint, Beam earns its complexity.

## Risks & Mitigations

- **Incorrect time semantics (shared):** processing-time windows produce non-deterministic results on reprocessed data. Document and implement the migration path to event-time with watermarks; provide both configurations in example code for direct comparison.
- **Runner portability assumptions (Beam):** testing only on DirectRunner masks distributed behavior. Add Gradle configurations per runner and include docs on dependency/config changes required when switching runners.
- **Dependency conflicts (Beam):** Beam's transitive dependencies (gRPC, Protobuf, Guava) frequently conflict with runner libraries. Pin versions and document known-good dependency sets per runner.
- **State blowup (Flink):** use RocksDB backend with explicit TTL on all stateful operators. Monitor state size via Flink's `State Size` metric and alert when it exceeds expected bounds.
- **Checkpoint failures (Flink):** large state or slow sinks cause checkpoint timeouts. Configure `checkpointing.timeout` and `tolerable-checkpoint-failures`. Use incremental checkpointing with RocksDB to reduce checkpoint size.
- **Backpressure cascading (Flink):** a slow sink propagates backpressure upstream and can stall the entire pipeline. Use async IO for sink operations and configure separate parallelism for sink operators.
