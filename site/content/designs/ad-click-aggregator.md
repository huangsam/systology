---
title: "Ad Click Aggregator"
description: "Real-time big data processing for ad events."
summary: "Design for aggregating ad clicks at massive scale, focusing on deduplication, exactly-once processing, and low-latency reporting."
tags: ["analytics", "streaming"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design a system to aggregate millions of ad click events in real-time to provide up-to-the-minute reporting for advertisers. The system must handle high-volume streams, filter out fraudulent or duplicate clicks, and ensure that click counts are accurate for billing purposes.

### Functional Requirements

- Aggregate clicks by ad ID and time window (e.g., 1 minute).
- Detect and filter duplicate clicks.
- Provide an API for real-time query results.

### Non-Functional Requirements

- **Scale:** 10 billion click events per day (peak 200k events/sec).
- **Latency:** End-to-end data delay (event time to ingestion in report) < 1 minute.
- **Consistency:** Exactly-once semantics for billing; hyper-accurate counts (probabilistic structures acceptable for pre-aggregation).
- **Availability:** Robustness against regional outages or stream spikes.
- **Workload Profile:**
    - Read:Write ratio: ~100:1
    - Peak throughput: 200k events/sec
    - Retention: 90 days hot, 1y archive

## High-Level Architecture

{{< mermaid >}}
graph LR
    SDK --> Ingest
    Ingest --> Kafka
    Kafka --> Dedup
    Dedup --> Agg
    Agg --> OLAP[(OLAP)]
    OLAP --> Query
    Kafka --> Fraud
    Fraud -.->|flag| Dedup
{{< /mermaid >}}

The architecture ingests events via a stateless HTTP/gRPC API behind a global load balancer, appending them to Kafka. A two-stage deduplication process (Bloom filter followed by Redis check) filters duplicates before streaming engines (like Flink or Spark) perform 1-minute event-time tumbling window aggregations. Final counts are upserted into an OLAP store (ClickHouse/Druid) for real-time querying. In parallel, a fraud detection sidecar scores events and feeds flags back to the deduplication stage to correct counts.

## Data Design

The data layer is split between high-throughput temporary streams and long-term analytical storage. Kafka manages the ingest pipelines using topic partitioning to guarantee order per ad. The reporting backend utilizes a columnar OLAP database tailored for real-time aggregations and sub-second roll-ups by campaign.

### Message Stream (Kafka Topics)
| Topic | Partition Key | Description | Retention |
| :--- | :--- | :--- | :--- |
| `raw_clicks` | `click_id` | Original event stream from SDK. | 7 days |
| `ad_events` | `ad_id` | Deduplicated events for aggregation. | 24 hours |
| `fraud_verdicts` | `ad_id` | ML flags for retroactive subtraction. | 24 hours |

### Reporting Schema (OLAP - ClickHouse)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **clicks_agg** | `ad_id` | UInt32 (PK) | Unique advertisement ID. |
| | `window_ts` | DateTime (PK)| 1-min window start timestamp. |
| | `click_count`| AggregateSet| Rolling count for the window. |
| | `revenue` | Decimal | Sum of bid price for clicked ads. |

## Deep Dive & Trade-offs

### Deep Dive

- **Exactly-once semantics:** Kafka transactional producers + stream engine checkpointing. Atomic read-process-write cycles and idempotent OLAP upserts keyed by `(ad_id, window)` ensure end-to-end consistency.

- **Backpressure & flow control:** Token-bucket rate limits per advertiser at ingestion. Consumer lag thresholds trigger autoscaling of stream task slots to maintain 1-minute freshness SLO.

- **Data reconciliation:** Nightly batch job re-reads raw events to validate real-time aggregates. Generates adjustment records if discrepancies exceed tolerance, ensuring billing integrity.

### Trade-offs

- **Bloom filter + Redis vs. Pure Redis:** Two-stage is memory-efficient but allows rare duplicates; Pure Redis is exact but expensive in memory and I/O at 200k events/sec.

- **Tumbling vs. Sliding Windows:** Tumbling is simpler and cheaper; Sliding provides smoother curves at the cost of higher CPU and state overhead.

- **Real-time vs. Batch Fraud Scoring:** Real-time catches fraud early but adds latency/infra; Batch is simpler but results in temporary report inflation until correction runs.

## Operational Excellence

### SLIs / SLOs

- SLO: 99% of click events are reflected in query results within 1 minute of event time.
- SLO: 99.9% of query API requests return in < 500 ms.
- SLIs: kafka_consumer_lag, aggregation_window_latency_p95, query_latency_p99, dedup_false_positive_rate, fraud_flag_rate.

### Monitoring & Alerts

- `kafka_consumer_lag > 60s`: Scale stream tasks or check spikes (P1).
- `bloom_filter_saturation > 90%`: Resize or rotate filter (P2).
- `reconciliation_discrepancy > 0.1%`: Check real-time vs batch drift (P2).

### Reliability & Resiliency

- **Verification**: Replay historical Kafka topics to validate aggregation and late-event handling.
- **Chaos**: Kill task managers mid-checkpoint to verify exactly-once recovery.
- **Load**: Test ingestion at 2x peak traffic to validate backpressure and scaling.

### Retention & Backups

- **Kafka**: 7-day retention for replay and reconciliation.
- **OLAP**: 90-day hot tier; 1y archive in cold object storage.
- **Models**: Versioned fraud model artifacts and features for auditability.
