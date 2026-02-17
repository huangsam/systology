---
title: "ETL Pipeline for ML Feature Engineering"
description: "Data extraction, transformation, and loading."
summary: "Robust ETL pipeline for deterministic, reproducible ML feature generation from diverse sources, with idempotence and scale in mind."
tags: ["ml","data-pipelines","monitoring","etl"]
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Build a robust ETL pipeline that extracts raw data from diverse sources, transforms it into machine learning features through deterministic and reproducible processes, and loads the features into a store for model training. The system must scale to large datasets, ensure idempotent operations for reliability, and run efficiently on modest hardware while maintaining strict reproducibility standards.

- **Functional Requirements:** Extract raw data (e.g., images, logs), transform into features, load into feature store for ML models.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** Process 1TB/day, with reproducible runs.
    - **Availability:** 99.5% for batch jobs.
    - **Consistency:** Deterministic feature generation.
    - **Latency Targets:** Batch completion < 2 hours.

## 2. High-Level Architecture

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

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Source connectors:** build modular, pluggable connectors for each data source (databases via CDC, blob stores, streaming topics, REST APIs). Each connector handles authentication, pagination, and checkpoint tracking so that extraction is resumable and idempotent.
- **Transform DAG and orchestration:** model transformations as a directed acyclic graph (e.g., Airflow DAG or dbt-style dependency graph). Each node is a pure function: `(input partitions, config) → output partition`. Run the DAG on a schedule or trigger it via new-data events. Use an orchestrator (Airflow, Dagster, Prefect) for dependency resolution, retries, and backfill.
- **Idempotent loads:** write output partitions atomically using a `partition_key + run_id` scheme. If a run is re-executed, it overwrites the same partition, producing identical results. This guarantees that reruns don't create duplicate features and that the feature store converges to the correct state.
- **Reproducibility:** pin all transform code, library versions, and config in a versioned artifact (container image or locked requirements file). Tag each output partition with the code version and input data snapshot hash so that any feature set can be reproduced exactly.
- **Schema evolution:** define feature schemas in a registry (e.g., Avro, Protobuf, or a feature-store schema). Use backward-compatible evolution rules: new columns with defaults are safe; column removals or type changes require a migration step and downstream notification.
- **Backfill strategy:** support historical backfill by accepting a date range parameter. Partition data by date so that backfills process only affected partitions without reprocessing the entire dataset. Run backfills at lower priority to avoid starving production pipelines.
- **Data quality and validation:** embed data-quality checks (Great Expectations, dbt tests) into the DAG as validation nodes: null-rate checks, range checks, row-count drift detection. Fail the pipeline early on quality violations before bad features reach the store.

### Trade-offs

- Batch vs. micro-batch vs. streaming: batch (hourly/daily) is simplest and sufficient for most ML training loops; streaming gives fresher features but adds complexity (exactly-once, state management); micro-batch (e.g., Spark Structured Streaming) is a middle ground.
- Centralised orchestrator vs. event-driven: an orchestrator provides a single pane of glass for scheduling and lineage but becomes a single point of failure; event-driven execution is more resilient but harder to reason about dependency ordering.
- Schema registry: enforces contracts and catches breaking changes early but adds a dependency and requires team discipline to register schemas before writing producers.

## 4. Operational Excellence

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
