---
title: "Real-Time Analytics Pipeline for User Behavior"
description: "Event stream processing and metrics"
summary: "Scalable real-time pipeline to ingest and process high-volume user event streams for immediate analytics and dashboards; handles late arrivals and fault tolerance."
tags: ["data-pipelines","monitoring","analytics","queues"]
categories: ["designs"]
---

# 1. Problem Statement & Constraints

Design a scalable system to ingest and process high-volume user event streams from a web application in real-time, enabling immediate analytics and dashboards for metrics like engagement. The pipeline must handle variable loads, ensure data accuracy despite late arrivals, and support fault-tolerant operations to maintain continuous availability.

- **Functional Requirements:** Ingest user event streams (e.g., clicks, views) from a web app, process in real-time, and provide analytics dashboards with aggregations like user engagement metrics.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** Handle 10k-100k events/sec, with 80:20 read:write ratio.
    - **Availability:** 99.9% uptime.
    - **Consistency:** Eventual consistency for aggregations.
    - **Latency Targets:** P99 < 500ms for event processing.

## 2. High-Level Architecture

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

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Event collection and ingestion:** deploy a stateless collector fleet behind a load balancer that accepts events over HTTPS (or gRPC). Validate, enrich (timestamp, geo-IP, session ID), and publish each event to a partitioned Kafka topic. Partition by user ID or session ID to preserve ordering within a user's session.
- **Stream processing engine:** use Apache Flink (or Kafka Streams for simpler cases) for stateful stream processing. Implement tumbling, sliding, and session windows to compute aggregations (page views per minute, unique users per hour, session duration). Flink's exactly-once checkpointing ensures aggregation accuracy even during failures.
- **Windowing and watermarks:** define event-time watermarks to track processing progress and handle out-of-order events. Use allowed-lateness thresholds (e.g., 5 minutes) to accept late arrivals and update previously emitted aggregations. Events arriving after the lateness window are routed to a dead-letter topic for batch reconciliation.
- **OLAP sink and query layer:** write computed aggregations to a columnar OLAP store (ClickHouse, Apache Druid, or BigQuery) optimised for fast analytical queries. Partition tables by time (hourly/daily) for efficient range scans. Expose a query API that dashboards poll or that pushes updates via WebSocket for near-real-time displays.
- **Raw event archival:** mirror the raw Kafka topic to a data lake (S3/GCS in Parquet format) via a Kafka Connect sink for historical analysis, machine learning, and regulatory compliance. This decouples the real-time path from batch workloads.
- **Backpressure and load shedding:** implement backpressure from the stream processor to the collector (via Kafka consumer lag). If lag exceeds a threshold, shed non-critical events (e.g., impression pings) or degrade dashboard refresh rate rather than dropping high-value events (purchases, errors).
- **Schema management:** enforce an Avro or Protobuf schema registry for event payloads. Producers must register schemas before publishing; the stream processor validates incoming events against the registry, rejecting malformed messages to protect downstream consumers.

### Tradeoffs

- Flink vs Kafka Streams: Flink provides richer windowing, savepoints, and exactly-once guarantees across sinks, but requires a dedicated cluster; Kafka Streams runs as a library inside application pods, simplifying deployment but limiting state-management capabilities.
- Event-time vs processing-time: event-time windowing produces accurate aggregations but requires watermark management and handling late data; processing-time is simpler but can produce inconsistent results under lag or reprocessing.
- OLAP store choice: ClickHouse offers excellent single-node performance and simpler ops; Druid excels at high-concurrency sub-second queries but is more complex to operate; managed services (BigQuery) eliminate ops burden but limit tuning control and may increase cost.

## 4. Operational Excellence

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
- Load-test at 3× peak event rate to validate autoscaling behaviour and identify bottlenecks in the collector, Kafka, and OLAP layers.

### Backups & Data Retention
- Raw events in the data lake retained for 1 year (regulatory and ML retraining).
- OLAP aggregation tables retained for 90 days at minute granularity; rolled up to hourly granularity for 1 year.
- Kafka topic retention set to 7 days for replay; longer retention via the data lake archive.
