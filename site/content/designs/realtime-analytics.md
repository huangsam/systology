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

## Data Design

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

- **Event ingestion:** Stateless collector fleet behind LB accepts HTTPS/gRPC. Events enriched (Geo-IP, session ID) and published to Kafka. Partitioning by `session_id` ensures intra-session ordering.

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

### Monitoring & Alerts (examples)

Alerts:

- `consumer_lag_seconds > 30` for 5m
    - Severity: P1 (stream processor falling behind; scale consumers or investigate processing bottleneck).
- `event_drop_rate > 0.1%` (5m)
    - Severity: P2 (events being shed or rejected; check schema validation and collector health).
- `dlq_event_count increases > 100/min`
    - Severity: P2 (excessive late arrivals or malformed events; investigate producer timestamps).

### Testing & Reliability
- Replay historical Kafka topics through a staging pipeline to validate windowing and aggregation logic before promoting changes.
- Chaos-test: kill Flink task managers and verify that exactly-once checkpointing restores state without data loss or duplication.
- Load-test at 3× peak event rate to validate autoscaling behavior and identify bottlenecks in the collector, Kafka, and OLAP layers.

### Backups & Data Retention
- Raw events in the data lake retained for 1 year (regulatory and ML retraining).
- OLAP aggregation tables retained for 90 days at minute granularity; rolled up to hourly granularity for 1 year.
- Kafka topic retention set to 7 days for replay; longer retention via the data lake archive.
