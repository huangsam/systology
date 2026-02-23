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

## Data Design

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

- **Source connectors:** Pluggable connectors for CDC, blob stores, and APIs. Handles auth, pagination, and checkpointing to ensure extraction is resumable and idempotent.

- **Transform DAG:** Pure functions `(input, config) → output`. Orchestration (Airflow/Dagster) manages dependency resolution, retries, and backfills for reproducible runs.

- **Idempotent loads:** Overwrites output partitions using a `partition_key + run_id` scheme. Ensures reruns converge to the same state without creating duplicate features in the store.

- **Reproducibility:** Versioned artifacts (containers) pin all code and dependencies. Output partitions tagged with code versions and data hashes allow bit-for-bit reconstruction.

- **Schema evolution:** Enforced via a registry (Avro/Protobuf). Backward-compatible rules ensure new columns with defaults don't break downstream training.

- **Backfill strategy:** Supports date-range parameters and prioritizes production pipelines. Date-partitioning allows re-processing specific windows without needing a full scan.

- **Data quality:** Embedded validation nodes (Great Expectations) perform null-rate and drift checks. Pipelines fail early to prevent bad data from reaching models.

### Trade-offs

- **Batch vs. Streaming:** Batch is simpler and sufficient for most ML loops; Streaming offers lower latency but increases architectural complexity (state, exactly-once).

- **Centralized vs. Event-driven Orchestration:** Centralized provides better lineage and visibility but is a single point of failure; Event-driven is resilient but harder to debug.

## Operational Excellence

### SLIs / SLOs
- SLO: 99% of daily batch pipelines complete within the 2-hour SLA window.
- SLO: Feature freshness < 4 hours (time from raw ingestion to feature-store availability).
- SLIs: pipeline_duration_p95, feature_freshness_lag, data_quality_pass_rate, row_count_delta_percent.

### Monitoring & Alerts (examples)

Alerts:

- `pipeline_duration > 2h`
    - Severity: P1 (SLA at risk; investigate bottleneck tasks).
- `data_quality_pass_rate < 99%` (per run)
    - Severity: P2 (bad data entering feature store; quarantine affected partitions).
- `row_count_delta > 20%` vs. previous run
    - Severity: P2 (unexpected data volume change; verify source health).

### Testing & Reliability
- Run the full DAG on a staging dataset daily; compare output features against a frozen golden snapshot.
- Integration-test each connector with a mock source to verify pagination, retry, and checkpoint behavior.
- Perform quarterly backfill drills to validate that historical re-processing produces bit-identical features.

### Backups & Data Retention
- Raw data (landing zone) retained for 1 year in cold storage for replay and auditing.
- Feature store partitions retained for 90 days (active) + 1 year (archived) for reproducibility.
- Pipeline metadata and lineage stored in the catalog with no expiry for compliance and debugging.
