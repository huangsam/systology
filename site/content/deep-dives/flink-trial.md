---
title: "Flink Trial"
description: "Stream processing with state and fault tolerance."
summary: "Streaming analytics demo for simulated IoT events — emphasizes time semantics, state backends, checkpointing, and fault tolerance."
tags: ["analytics", "data-pipelines", "monitoring", "streaming"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/flink-trial"
draft: false
---

## Context — Problem — Solution

**Context:** `flink-trial` is a streaming analytics demo that processes simulated IoT device events using Apache Flink's native Java API. It demonstrates tumbling window aggregation, side output patterns for error routing, and checkpoint-based fault tolerance—features that go beyond Beam's portable abstraction layer.

**Problem:** Real-time streaming requires reliable windowing semantics (processing-time vs. event-time), proper error routing without blocking the main pipeline, state management for windowed aggregations, and fault tolerance that recovers from failures without data loss. These concerns interact in subtle ways—a wrong windowing choice silently produces incorrect aggregates that are difficult to detect after the fact.

**Solution (high-level):** Use Flink-native APIs for processing-time windowed aggregation as a starting point, with side output patterns to route malformed events to error sinks, and a clear migration path toward event-time processing with watermarks, RocksDB state backend, and checkpoint-based fault tolerance for production scenarios.

## The Local Implementation

- **Current Logic:** A simulated event generator produces IoT sensor readings (temperature, humidity, pressure) with embedded timestamps and occasional malformed events. The pipeline applies a `ProcessFunction` that validates events and routes invalid ones to a side output tagged `OutputTag<String>("errors")`. Valid events are keyed by device ID and fed into a 5-second tumbling window that computes min/max/avg per sensor per window. Results are emitted to both a console sink and a CSV file sink. Error events go to a separate error log sink.
- **Flink-native features:** the pipeline leverages Flink-specific APIs beyond Beam's portable surface: `ProcessFunction` with side outputs (no direct Beam equivalent), `ValueState` and `MapState` for per-key stateful processing, `RocksDBStateBackend` for large state that exceeds heap, and Flink's built-in backpressure mechanism via credit-based flow control between operators.
- **Time semantics:** currently uses processing-time windows for simplicity. Events carry an `event_timestamp` field that enables migration to event-time processing with `WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofSeconds(5))`, which tolerates up to 5 seconds of out-of-order delivery before closing windows.
- **Bottleneck:** Processing-time windows are simple but don't correctly handle reprocessed events or late arrivals—aggregates can differ between runs of the same data. Local demo parallelism (1–2 task slots) doesn't reflect cluster-scale behavior where network shuffle between operators introduces real latency and backpressure dynamics.

## Scaling Strategy

- **Vertical vs. Horizontal:** Run on a Flink cluster (standalone or YARN/Kubernetes) for production. Scale parallelism per operator independently—the source and window operators often need different parallelism settings. Use Flink's reactive scaling (Kubernetes) to adjust TaskManagers based on backpressure signals.
- **State Management:** Enable checkpoints with `env.enableCheckpointing(60_000)` (60s interval) using the `RocksDBStateBackend` for state that exceeds available heap. Configure state TTL (`StateTtlConfig.newBuilder(Time.hours(1))`) on windowed state to prevent unbounded growth from stale device keys. For exactly-once semantics with external sinks, use Flink's two-phase commit protocol with transactional sinks (Kafka, JDBC).

## Comparison to Industry Standards

- **My Project:** Demonstration-grade streaming with common Flink patterns (side outputs, windowed counts, keyed state). Focused on illustrating Flink's native capabilities and operational model.
- **Industry:** Production streaming includes event-time watermarks with late-data side outputs, complex event processing (CEP library), exactly-once end-to-end guarantees, comprehensive job health dashboards (Flink Web UI + Prometheus), and dynamic resource scaling with Kubernetes.
- **Gap Analysis:** For production deployment: implement event-time windowing with watermarks and configurable allowed lateness, add late-data side outputs for events that arrive after window closure, build comprehensive dashboards (checkpoint duration, backpressure, watermark lag, records-per-second per operator), integrate with a metrics stack (Prometheus + Grafana via Flink's metrics reporters), and automate savepoint management for job upgrades.

## Experiments & Metrics

- **Latency:** per-event processing latency (ingestion to window emission) under different parallelism settings (1, 2, 4, 8 task slots). Measure at the operator level using Flink's latency tracking markers.
- **Throughput:** events/second sustainable at each parallelism level before backpressure triggers. Identify the bottleneck operator (usually the window function or the sink).
- **Processing-time vs. event-time comparison:** run the same event stream through both windowing modes and compare aggregate correctness when events arrive out of order. Quantify the error rate of processing-time windows under realistic disorder.
- **Fault recovery:** time to recover after simulated TaskManager failures with checkpointing enabled. Measure checkpoint size, checkpoint duration, and end-to-end recovery time (failure → full throughput restored).
- **State size growth:** monitor RocksDB state size over time with and without TTL to quantify unbounded state risk.

## Risks & Mitigations

- **Incorrect time semantics:** processing-time windows produce non-deterministic results for reprocessed data. Document the migration path to event-time with watermarks and provide both configurations in the example code for comparison.
- **State blowup:** use RocksDB backend and explicit TTL on all stateful operators. Monitor state size via Flink's `State Size` metric and alert when it exceeds expected bounds.
- **Checkpoint failures:** large state or slow sinks can cause checkpoint timeouts. Configure `checkpointing.timeout` and `tolerable-checkpoint-failures` to prevent job restarts from transient checkpoint issues. Use incremental checkpointing with RocksDB to reduce checkpoint size.
- **Backpressure cascading:** if a slow sink causes backpressure, it propagates upstream and can stall the entire pipeline. Use async IO for sink operations and configure separate parallelism for sink operators.
