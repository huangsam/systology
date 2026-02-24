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

Web and mobile apps emit events to a stateless Collector fleet, which enriches the payloads before publishing them to Kafka. A Stream Processor (like Flink) consumes from Kafka, computing stateful aggregations based on event-time watermarks, and sinking the results into an OLAP database that powers real-time Dashboards. Late-arriving events that fall outside the allowed windows are routed to a Dead Letter Queue (DLQ), while all raw events are continuously archived to a Data Lake for historical analysis.

## Data Design

The data storage strategy balances high-throughput buffering, ultra-fast analytics, and cheap long-term retention. Kafka topics act as the resilient buffer for raw event streams and intermediate aggregates. The OLAP datastore (like ClickHouse or Druid) uses heavily partitioned, columnar tables to support millisecond querying over broad time ranges, while the Data Lake provides infinite retention of the raw Parquet files.

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

- **Stream processing:** Apache Flink performs stateful aggregations (metrics per min/hour). Flink’s exactly-once checkpointing ensures accuracy across tumbling, sliding, and session windows.

- **Watermarks & lateness:** Event-time watermarks handle out-of-order data. Allowed-lateness thresholds accept late events and trigger aggregate updates; data exceeding the window routes to a DLQ.

- **OLAP query layer:** Aggregates written to columnar stores (ClickHouse/Druid) optimized for range scans. A Query API supports dashboard polling or WebSocket pushes for real-time visibility.

- **Event archival:** Raw Kafka topics mirrored to a data lake (S3/GCS) in Parquet via Kafka Connect. Decouples real-time processing from historical analysis and ML training.

- **Load shedding:** Backpressure from stream processor (via Kafka lag) triggers shedding of non-critical events (e.g., pings) to protect high-value data and maintain freshness.

- **Schema registry:** Enforces Avro/Protobuf schemas. Producers register schemas before publishing; processor validates messages to prevent corrupted sinks.

### Trade-offs

- **Flink vs. Kafka Streams:** Flink offers robust exactly-once state management but requires a cluster; Kafka Streams is a lightweight library but lacks comprehensive multi-sink guarantees.

- **Event-time vs. Processing-time:** Event-time is accurate but requires complex watermark management; Processing-time is simpler but inconsistent under lag or replay.

- **OLAP Choice:** ClickHouse is simpler for high-perf single-nodes; Druid scales better for high-concurrency queries; Managed (BigQuery) reduces ops but limits tuning.

## Operational Excellence

### SLIs / SLOs

- SLO: P99 end-to-end event processing latency (collector to OLAP) < 500 ms.
- SLO: Dashboard data freshness < 2 seconds from the latest processed event.
- SLIs: event_processing_latency_p99, consumer_lag_seconds, dashboard_freshness_lag, event_drop_rate, dlq_event_count.

### Monitoring & Alerts

- `consumer_lag > 30s`: Scale consumers or check processing bottlenecks (P1).
- `event_drop_rate > 0.1%`: Check schema validation or collector health (P2).
- `dlq_growth > 100/min`: Investigate late arrivals or malformed events (P2).

### Reliability & Resiliency

- **Replay**: Re-run historical topics in staging to validate windowing logic.
- **Chaos**: Kill task managers to verify exactly-once checkpoint restoration.
- **Scale**: Load-test at 3x peak to validate collector and OLAP throughput.

### Retention & Backups

- **Lake**: Raw events in S3/GCS retained 1 year for audit and ML.
- **OLAP**: 90-day minute-level aggs; 1 year hourly roll-ups.
- **Kafka**: 7-day retention for replay; mirrored to data lake archive.
