---
title: "Data Processing Architectures"
description: "Comparative analysis of batch and streaming frameworks."
summary: "A deep architectural comparison of data processing pipelines: evaluating Apache Spark's batch ETL model against Apache Beam's portable unified model and Apache Flink's native API for stateful processing."
tags: [data-pipelines, fault-tolerance, parallelization, streaming, systems-programming]
categories: ["deep-dives"]
links:
  github:
    - "https://github.com/huangsam/spark-trial"
    - "https://github.com/huangsam/beam-trial"
    - "https://github.com/huangsam/flink-trial"
draft: false
date: "2026-02-16T10:22:20-08:00"
---

## Context & Motivation

**Context:** Modern data systems require a mix of batch and streaming capabilities. These trials explore three distinct approaches: `spark-trial` for batch ETL, `beam-trial` for portable unified processing, and `flink-trial` for native high-performance streaming.

**Motivation:** Choosing the right framework involves balancing latency, throughput, time semantics, and runner portability. A batch-first approach (Spark) is often the most reliable for rebuilding historical data, while streaming (Flink/Beam) is required for real-time insights. Exploring all three surfaces the practical tradeoffs between these paradigms.

{{< mermaid >}}
graph TD
    subgraph Unified ["Unified Layer"]
        B[Beam API]
    end

    B -- "Translates to" --> S
    B -- "Translates to" --> F
    B -- "Translates to" --> D

    subgraph Batch ["Batch Execution"]
        S[Spark] --> S_Opt[Catalyst Optimizer]
        S_Opt --> S_Exec[Tungsten Execution]
    end

    subgraph Stream ["Streaming Execution"]
        F[Flink] --> F_State[RocksDB State]
        F_State --> F_Sem[Event-time / Watermarks]
    end

    subgraph Managed ["Cloud Execution"]
        D[Cloud Dataflow]
    end
{{< /mermaid >}}

## Approach 1: spark-trial (Batch ETL)

- **Overview:** A Scala/SBT project performing end-to-end ETL on NYC Yellow Taxi trip data. It demonstrates schema alignment across multiple years of parquet data, statistical aggregations (yearly/quarterly), and rigorous validation.
- **What worked:** Spark's SQL optimizer and strong schema handling made it straightforward to normalize drifting data formats across years. The Dataset API provided compile-time type safety for complex aggregations.
- **Bottlenecks & Limitations:** Large IO volumes during historical rebuilds can exhaust local resources. Schema drift across years required explicit mapping logic rather than relying on auto-detection.
- **Production gaps:** Integrate with orchestration (Airflow/Argo) for scheduling; add data lineage and versioning; implement comprehensive data quality monitoring.

## Approach 2: beam-trial (Portable Unified Model)

- **Overview:** A minimal Apache Beam pipeline in Java/Gradle using the DirectRunner. Creates an in-memory `PCollection` and applies composable `PTransform` operations. Illustrates Beam's core abstractions: logical datasets, composable operations, and runner-agnostic logic.
- **What worked:** The portable programming model is clean—pipelines are expressed once and can theoretically run on Dataflow, Flink, or Spark without logic changes. This is a significant operational advantage for multi-cloud environments.
- **Bottlenecks & Limitations:** The DirectRunner masks distributed behavior and parallelism. Beam's APIs for stateful processing are less flexible and ergonomic than Flink's native equivalents, and some runner-specific optimizations remain outside the portable surface.
- **Production gaps:** Add windowed aggregations and side inputs; integrate with durable sinks (Avro/Parquet); implement pipeline-level alerting and monitoring.

## Approach 3: flink-trial (Native Stateful Streaming)

- **Overview:** A streaming analytics demo using Flink's native Java API processing simulated IoT sensor events. Uses a `ProcessFunction` for validation and side-output routing, with 5-second tumbling windows for per-device metrics. Uses `RocksDBStateBackend` for fault-tolerant state.
- **What worked:** Flink's native API exposes low-level capabilities like side outputs for error routing and per-key `ValueState`. Its built-in backpressure propagation and credit-based flow control ensure stability under load.
- **Bottlenecks & Limitations:** Processing-time windows can produce non-deterministic results when reprocessing. Local parallelism is limited and won't surface real network shuffle latency or backpressure until scaled to a cluster.
- **Production gaps:** Implement event-time windowing with watermarks; add metrics reporters for Prometheus/Grafana; automate savepoint management for upgrades.

## Comparative Analysis

| Feature | Spark (Batch) | Beam (Portable) | Flink (Native) |
| :--- | :--- | :--- | :--- |
| **Primary Use** | Historical Rebuilds / ETL | Multi-cloud / Unified | Low-latency Streaming |
| **API Focus** | Schema & SQL (Dataset) | Portability (PTransform) | Stateful Control (ProcessFunction) |
| **Fault Tolerance**| RDD Lineage / Checkpoints | Runner-dependent | Incremental Checkpoints (RocksDB) |
| **Time Semantics** | N/A (Batch) | Event-time (Portable) | Event-time (Native) |
| **Typical Latency**| Minutes to Hours | Seconds to Minutes | Sub-second |
| **Op Complexity** | Moderate | High (Indirection) | High (State Mgmt) |

Spark's strength is its robust batch ecosystem and SQL optimization, making it the baseline for accurate, rebuiltable historical data. Beam offers the highest abstraction, trading off some native performance for the ability to swap runners as infrastructure evolves. Flink provides the most granular control over state and time, making it the pragmatic choice for high-stakes streaming systems where latency and operator-level tuning matter most.

## Risks & Mitigations

- **Schema drift (Spark):** implement schema merging and robust validation with alerting.
- **Runner portability (Beam):** testing only on DirectRunner masks distributed behavior; validate on target runners in CI.
- **State blowup (Flink):** use RocksDB with explicit TTL and monitor state size via metrics.
- **Non-deterministic re-runs (Streaming):** migrate from processing-time to event-time with watermarks for reproducible results.
