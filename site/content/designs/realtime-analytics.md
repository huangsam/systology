---
title: "Real-Time Analytics Pipeline"
description: "Event stream processing and metrics."
summary: "Scalable real-time pipeline to ingest and process high-volume user event streams for immediate analytics and dashboards; handles late arrivals and fault tolerance."
tags: ["analytics", "data-pipelines", "monitoring", "queues"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design a scalable system to ingest and process high-volume user event streams from a web application in real-time, enabling immediate analytics and dashboards for metrics like engagement. The pipeline must handle variable loads, ensure data accuracy despite late arrivals, and support fault-tolerant operations to maintain continuous availability.

### Functional Requirements

- Ingest user event streams (clicks, views, conversions) from web/mobile apps.
- Process events in real-time with stateful aggregations.
- Provide analytics dashboards and API for metric queries.
- Archive raw events for batch reprocessing.

### Non-Functional Requirements

- **Scale:** Handle 10k–100k events/sec; peak-hour bursts.
- **Availability:** 99.9% uptime; resilient to temporary source unavailability.
- **Consistency:** Eventual consistency for aggregations; at-least-once event processing.
- **Latency:** P99 < 500ms for event-to-dashboard visibility.
- **Workload Profile:**
    - Read:Write ratio: ~20:80
    - Peak throughput: 100k events/sec
    - Retention: 30 days hot; 1y archive

## High-Level Architecture

{{< mermaid >}}
graph LR
    App --> Collector
    Collector --> Kafka
    Kafka --> StreamProc[Processor]
    StreamProc --> OLAP
    OLAP --> Dashboard
    StreamProc -.->|late| DLQ
    Kafka -.->|archive| Lake
{{< /mermaid >}}

Apps emit events to a stateless Collector fleet that enriches payloads and publishes to Kafka. A Stream Processor (Flink) consumes the stream, computes stateful aggregations using event-time watermarks, and sinks results into an OLAP database for real-time Dashboards. Late events exceeding allowed windows route to a DLQ, while all raw events archive continuously to a Data Lake.

## Data Design

Kafka buffers high-throughput raw streams and intermediate aggregates. A columnar OLAP datastore (ClickHouse/Druid) uses heavy partitioning for millisecond analytics querying, while the Data Lake provides cheap, infinite retention for raw Parquet files.

### Event Stream (Kafka Topics)
| Topic | Partition Key | Throughput | Retention |
| :--- | :--- | :--- | :--- |
| `user_events` | `session_id` | 100k msg/s | 7 days |
| `aggregates` | `metric_name` | 1k msg/s | 24 hours |
| `late_events` | `event_id` | < 100 msg/s | 14 days |

### Metrics Store (OLAP - ClickHouse/Druid)
| Table | Granularity | Partitioning | Primary Key |
| :--- | :--- | :--- | :--- |
| **raw_events** | Event-level | `YYYY-MM-DD` | `session_id, timestamp` |
| **minly_aggs** | 1 Minute | `YYYY-MM` | `metric_type, window_start` |
| **hourly_aggs**| 1 Hour | `YYYY` | `metric_type, window_start` |

## Deep Dive & Trade-offs

### Deep Dive

- **Stream processing:** Apache Flink computes stateful aggregations, relying on exactly-once checkpointing for accuracy across varied time windows.

- **Watermarks & lateness:** Event-time watermarks handle out-of-order data. Allowed-lateness settings trigger retroactive updates, dropping older data to a DLQ.

- **OLAP query layer:** Columnar stores optimized for range scans support Query APIs for dashboard polling and real-time WebSocket pushes.

- **Event archival:** Kafka Connect mirrors raw topics to a data lake in Parquet, completely decoupling real-time processing from offline ML training.

- **Load shedding:** Kafka lag backpressure triggers dynamic shedding of non-critical events to protect high-value data freshness.

- **Schema registry:** A centralized registry enforces Avro/Protobuf schemas, validating messages stream-side to prevent corrupted OLAP sinks.

### Trade-offs

- **Flink vs. Kafka Streams:** Flink offers robust exactly-once state management but requires a cluster; Kafka Streams is a lightweight library but lacks comprehensive multi-sink guarantees.

- **Event-time vs. Processing-time:** Event-time is accurate but requires complex watermark management; Processing-time is simpler but inconsistent under lag or replay.

- **OLAP Choice:** ClickHouse is simpler for high-perf single-nodes; Druid scales better for high-concurrency queries; Managed (BigQuery) reduces ops but limits tuning.

## Operational Excellence

### SLIs / SLOs

- SLO: P99 end-to-end event processing latency (collector to OLAP) < 500 ms.
- SLO: Dashboard data freshness < 2 seconds from the latest processed event.
- SLIs: event_processing_latency_p99, consumer_lag_seconds, dashboard_freshness_lag, event_drop_rate, dlq_event_count.

### Reliability & Resiliency

- **Replay**: Re-run historical topics in staging to validate windowing logic.
- **Chaos**: Kill task managers to verify exactly-once checkpoint restoration.
- **Scale**: Load-test at 3x peak to validate collector and OLAP throughput.
