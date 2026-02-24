---
title: "ETL Pipeline for ML Features"
description: "Data extraction, transformation, and loading."
summary: "Robust ETL pipeline for deterministic, reproducible ML feature generation from diverse sources, with idempotence and scale in mind."
tags: ["data-pipelines", "etl", "ml", "monitoring"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Build a robust ETL pipeline that extracts raw data from diverse sources, transforms it into machine learning features through deterministic and reproducible processes, and loads the features into a store for model training. The system must scale to large datasets, ensure idempotent operations for reliability, and run efficiently on modest hardware while maintaining strict reproducibility standards.

### Functional Requirements

- Extract raw data from diverse sources (databases, APIs, blob stores).
- Transform data into deterministic ML features.
- Load features into a feature store for model training.

### Non-Functional Requirements

- **Scale:** Process 1 TB/day of raw input; reproducible pipeline runs.
- **Availability:** 99.5% for batch jobs; graceful handling of source unavailability.
- **Consistency:** Deterministic, bit-for-bit reproducible feature generation.
- **Latency:** Batch job completion < 2 hours; daily schedule.
- **Workload Profile:**
    - Read:Write ratio: ~90:10
    - Throughput: 1 TB/day
    - Retention: 1y hot feature store; archive older features

## High-Level Architecture

{{< mermaid >}}
graph LR
    Raw[Raw Sources] --> Ingest
    Ingest --> Lake
    Lake --> Transform[DAG]
    Transform --> FeatureStore[Store]
    FeatureStore --> Training
    Scheduler[Orchestrator] --> Ingest
    Scheduler --> Transform
    Transform -.->|lineage| Catalog
{{< /mermaid >}}

An Orchestrator triggers data ingestion from raw sources into a multi-tier Data Lake. Transformation DAGs pull data, process ML features, and publish vectors to a Feature Store for model training. Lineage Catalogs record transformation metadata and data dependencies.

## Data Design

A medallion Data Lake (Bronze, Silver, Gold), heavily partitioned by date and group, accelerates batch reads. A low-latency Feature Store (KV database) serves specific user or product tensors quickly to the training pipeline.

### Data Lake Partitioning (S3/HDFS/Warehouse)
| Layer | Partition Key | Format | Retention |
| :--- | :--- | :--- | :--- |
| **Bronze** | `source_id/YYYY-MM-DD` | Parquet | 1 year |
| **Silver** | `feature_group/v_1` | Iceberg | 5 years |
| **Gold** | `model_version/run_id` | Parquet | Indefinite |

### Feature Store Layout (KV/NoSQL)
| Key Pattern | Value Type | Purpose | Latency |
| :--- | :--- | :--- | :--- |
| `u:feat:<user_id>` | Hash/Vector | Real-time user embedding. | < 5ms |
| `p:feat:<prod_id>` | Tensor/List | Product interaction stats. | < 10ms |
| `meta:<group_v>` | JSON | Feature metadata / drift thresholds. | < 50ms |

## Deep Dive & Trade-offs

### Deep Dive

- **Source connectors:** Pluggable connectors (CDC, blob stores, APIs) handle auth, pagination, and checkpointing for resumable, idempotent extraction.

- **Transform DAG:** Orchestrators (Airflow/Dagster) manage pure function `(input, config) → output` dependencies, retries, and backfills reproducible runs.

- **Idempotent loads:** Partition overwrites using a `partition_key + run_id` scheme ensure reruns converge to the same state without duplication.

- **Reproducibility:** Versioned containers pin code, and data hashes on output partitions allow bit-for-bit reconstruction.

- **Schema evolution:** Backward-compatible rules in a registry (Avro/Protobuf) prevent new columns from breaking downstream training.

- **Backfill strategy:** Date-partitioning limits scans to specific windows, naturally supporting backfills while prioritizing production pipelines.

- **Data quality:** Embedded validation nodes (Great Expectations) fail pipelines early on null-rate or drift violations.

### Trade-offs

- **Batch vs. Streaming:** Batch is simpler and sufficient for most ML loops; Streaming offers lower latency but increases architectural complexity (state, exactly-once).

- **Centralized vs. Event-driven Orchestration:** Centralized provides better lineage and visibility but is a single point of failure; Event-driven is resilient but harder to debug.

## Operational Excellence

### SLIs / SLOs

- SLO: 99% of daily batch pipelines complete within the 2-hour SLA window.
- SLO: Feature freshness < 4 hours (time from raw ingestion to feature-store availability).
- SLIs: pipeline_duration_p95, feature_freshness_lag, data_quality_pass_rate, row_count_delta_percent.

### Monitoring & Alerts

- `pipeline_duration > 2h`: Investigate bottleneck tasks (P1).
- `quality_pass_rate < 99%`: Quarantine affected data partitions (P2).
- `row_count_delta > 20%`: Verify upstream source health (P2).

### Reliability & Resiliency

- **Snapshots**: Daily staging runs compared against frozen golden snapshots.
- **Connectors**: Integration-test mocks for pagination and retry behavior.
- **Backfills**: Quarterly drills to ensure reproducible bit-identical historical data.

### Retention & Backups

- **Landing**: Raw data retained 1y in cold storage for replay/audit.
- **Feature Store**: 90-day active partitions; 1y archived for reproducibility.
- **Lineage**: Metadata and lineage stored indefinitely for compliance.
