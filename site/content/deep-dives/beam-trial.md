---
title: "Beam Trial"
description: "Apache Beam for unified batch/streaming pipelines."
summary: "Minimal Apache Beam Hello World in Java/Gradle demonstrating pipeline construction, transforms, and DirectRunner execution for learning Beam's core model."
tags: ["data-pipelines", "extensibility", "streaming"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/beam-trial"
draft: false
---

## Context & Motivation

**Context:** `beam-trial` is a minimal Apache Beam learning project in Java/Gradle that demonstrates fundamental pipeline construction with the DirectRunner. The project provides a single entry point that creates an in-memory `PCollection`, applies transforms, and writes sharded text output.

**Motivation:** Beam is an alternative to Flink, and I wanted to understand its core programming model and abstractions. The project serves as a simple starting point to learn how to construct pipelines, apply transforms, and execute with the DirectRunner before exploring more complex features like windowing, stateful processing, and runner portability.

## The Local Implementation

- **Current Logic:** A Gradle project with a single `Main` class. The pipeline creates an in-memory `PCollection` from a small set of words, applies `MapElements` transforms with a prefixing function, and writes sharded text output via `TextIO.write()`. The DirectRunner executes the pipeline locally in a single JVM.
- **Beam model concepts:** even this minimal example illustrates key Beam abstractions—`PCollection` as a logical dataset (bounded or unbounded), `PTransform` as a composable operation, and `Coder` for serialization. Understanding these abstractions is essential because they determine how runners execute the graph.
- **Bottleneck:** DirectRunner executes transforms sequentially in a single JVM, which masks parallelism and fusion behavior. IO sharding on DirectRunner produces a single shard regardless of configuration, hiding the multi-shard behavior visible on distributed runners. The project is intentionally minimal—extending it to demonstrate GroupByKey, windowing, and multi-runner support is the natural next step.

## Scaling Strategy

- **Vertical vs. Horizontal:** DirectRunner is single-JVM and useful only for testing and learning. To scale, the pipeline can be run on FlinkRunner (distributes work across TaskManagers) or Dataflow (autoscales workers based on backlog). Switching runners requires adding the appropriate runner dependency to `build.gradle` and passing `--runner=` CLI flags.
- **Runner portability trade-offs:** Beam's portable API guarantees semantic equivalence across runners, but performance characteristics diverge. Flink applies operator chaining (fusion) aggressively, reducing serialization overhead. Dataflow optimizes shuffle via its proprietary Shuffle Service. Direct comparisons require identical input data and transform graphs to isolate runner effects.
- **State Management:** For production, use durable sinks (GCS, S3, HDFS) and runner-provided checkpointing for fault tolerance. Flink's checkpointing snapshots operator state to RocksDB or FS backends; Dataflow handles this transparently.

## Comparison to Industry Standards

- **My Project:** A teaching-first, minimal Beam example that establishes the core pipeline model. Emphasis on simplicity and a clean starting point for further exploration.
- **Industry:** Production Beam pipelines rely on robust runners with monitoring (Dataflow Metrics, Flink Web UI), durable sources/sinks, exactly-once semantics, and orchestration (Airflow, Argo) for scheduling and retry.
- **Gap Analysis:** To move from this learning example to production: add additional transforms (GroupByKey, windowed aggregations, side inputs), integrate durable sources/sinks with schema enforcement (Avro/Parquet), implement pipeline-level monitoring and alerting, integrate orchestration for scheduling and failure recovery, and tune runner-specific configurations for the target workload.

## Risks & Mitigations

- **Local-only assumptions:** the project currently only demonstrates DirectRunner. Include docs on runner portability and the dependency/config changes required when switching runners. Add Gradle configurations per runner for easy switching.
- **Minimal scope limiting learning:** the single-pipeline structure doesn't yet cover GroupByKey, windowing, or side inputs—features critical for real-world Beam usage. Extend incrementally with documented learning paths.
- **Dependency conflicts:** Beam's transitive dependencies (gRPC, Protobuf, Guava) frequently conflict with runner libraries. Pin versions and document known-good dependency sets per runner.
