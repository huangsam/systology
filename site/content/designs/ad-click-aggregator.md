---
title: "Ad Click Aggregator"
description: "Real-time big data processing for ad events."
summary: "Design for aggregating ad clicks at massive scale, focusing on deduplication, exactly-once processing, and low-latency reporting."
tags: ["analytics", "streaming"]
categories: ["designs"]
draft: true
---

## 1. Problem Statement & Constraints

Design a system to aggregate millions of ad click events in real-time to provide up-to-the-minute reporting for advertisers. The system must handle high-volume streams, filter out fraudulent or duplicate clicks, and ensure that click counts are accurate for billing purposes.

- **Functional Requirements:** Aggregate clicks by ad ID and time window (e.g., 1 minute), detect/filter duplicates, provide an API for real-time query results.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 10 billion click events per day (peak 200k events/sec).
    - **Latency:** End-to-end data delay (event time to ingestion in report) < 1 minute.
    - **Accuracy:** Exactly-once semantics for billing; hyper-accurate counts (probabilistic structures acceptable for pre-aggregation).
    - **Fault Tolerance:** Robustness against regional outages or stream spikes.

## 2. High-Level Architecture

{{< mermaid >}}
graph LR
  SDK[Client SDK] --> Ingest[Ingestion API]
  Ingest --> Kafka[Kafka Topics]
  Kafka --> Dedup[Dedup Filter]
  Dedup --> Agg[Stream Aggregator]
  Agg --> OLAP[(OLAP Store)]
  OLAP --> QueryAPI[Query API]
  Kafka --> Fraud[Fraud Detector]
  Fraud -.->|flag| Dedup
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Ingestion layer:** stateless HTTP/gRPC endpoints behind a global load balancer. Each event carries an SDK-generated click ID (UUID), ad ID, campaign ID, timestamp, and anonymised user fingerprint. Servers validate schema and append to partitioned Kafka topics keyed by `ad_id` to preserve per-ad ordering.
- **Click deduplication:** two-stage dedup. Stage 1: a probabilistic Bloom filter (false-positive rate ~0.1 %) provides a fast first pass in the stream processor. Stage 2: for any event that passes the Bloom filter, perform a definitive check against a Redis set of recent click IDs (TTL = 2× the aggregation window). This keeps memory bounded while preserving billing-grade accuracy.
- **Windowed aggregation:** use a stream processing engine (Flink / Spark Structured Streaming) with event-time tumbling windows (1-minute default). Late-arriving events are handled with allowed lateness (e.g., 30 s) and side outputs for extremely late data. Aggregated counts per `(ad_id, window)` are emitted to the OLAP store.
- **Exactly-once semantics:** enable Kafka transactional producers and the stream engine's checkpointing (Flink checkpoints / Spark write-ahead logs). End-to-end exactly-once from ingestion to OLAP is achieved by atomic Kafka read-process-write cycles plus idempotent OLAP upserts keyed on `(ad_id, window_start)`.
- **OLAP query store:** ClickHouse or Apache Druid serves as the real-time query backend. Data is partitioned by time and indexed on `ad_id` and `campaign_id`. The Query API exposes roll-ups by campaign, advertiser, and time granularity, with sub-second response times for dashboard queries.
- **Fraud detection sidecar:** a parallel Kafka consumer runs ML scoring models (click-through-rate anomalies, IP clustering, device fingerprint velocity) and publishes fraud verdicts back to a compacted topic. The dedup stage consumes these verdicts to retroactively subtract flagged clicks from aggregate windows via correction events.
- **Backpressure and flow control:** ingestion servers apply per-advertiser rate limits (token bucket). If Kafka consumer lag exceeds a threshold, the stream processor triggers autoscaling of task slots before lag impacts the 1-minute freshness SLO.
- **Data reconciliation:** a nightly batch job re-reads raw events from Kafka's long-retention topic (7 days), re-runs dedup and aggregation, and compares results against real-time aggregates. Discrepancies above a configurable tolerance generate reconciliation adjustment records for billing.

### Trade-offs

- Bloom filter + Redis dedup: fast and memory-efficient, but the Bloom filter can allow a small number of duplicates through; a pure Redis approach is exact but requires significantly more memory and network I/O at 200 k events/sec.
- Event-time tumbling windows vs. sliding windows: tumbling windows are simpler and cheaper to maintain state for, but provide coarser temporal resolution; sliding windows give smoother reporting curves at the cost of higher state and CPU overhead.
- Real-time ML fraud detection vs. batch scoring: real-time catches fraud before it enters aggregates but adds processing latency and model-serving infrastructure; batch scoring is simpler but means fraudulent clicks inflate reports until the next correction run.

## 4. Operational Excellence

### SLIs / SLOs
- SLO: 99% of click events are reflected in query results within 1 minute of event time.
- SLO: 99.9% of query API requests return in < 500 ms.
- SLIs: kafka_consumer_lag, aggregation_window_latency_p95, query_latency_p99, dedup_false_positive_rate, fraud_flag_rate.

### Monitoring & Alerts (examples)

Alerts:

- `kafka_consumer_lag > 60s` for 5m
    - Severity: P1 (scale stream processor tasks or investigate upstream spike).
- `dedup_bloom_filter_saturation > 90%`
    - Severity: P2 (rotate or resize filter to maintain target false-positive rate).
- `reconciliation_discrepancy > 0.1%`
    - Severity: P2 (investigate drift between real-time and batch aggregates).

### Testing & Reliability
- Replay historical Kafka topics through the pipeline in a staging environment to validate aggregation accuracy and late-event handling.
- Chaos-test by killing stream processor task managers mid-checkpoint to verify exactly-once recovery semantics.
- Load-test the ingestion layer at 2× peak (400 k events/sec) to validate backpressure and autoscaling behaviour.

### Backups & Data Retention
- Retain raw click events in Kafka with 7-day retention for replay and reconciliation.
- Store aggregated data in the OLAP store with a 90-day hot tier and archive older partitions to cold object storage for compliance.
- Back up fraud model artefacts and feature stores separately with versioning for auditability.
