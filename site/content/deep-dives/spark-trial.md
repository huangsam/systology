---
title: "Spark Trial"
description: "Batch processing with ETL workflows."
summary: "End-to-end ETL example using Apache Spark for parquet datasets; focuses on schema handling, partitioning, and reproducible aggregation."
tags: ["data-pipelines", "etl", "monitoring"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/spark-trial"
draft: false
---

## Context — Problem — Solution

**Context:** `spark-trial` demonstrates end-to-end ETL for NYC Yellow Taxi trip data using Apache Spark with Scala and SBT, performing schema alignment, validation, and statistical aggregations across multiple years.

**Problem:** Processing large, multi-year parquet datasets requires robust schema handling, partition-aware IO, and reproducible aggregation logic for analytics.

**Solution (high-level):** Use Spark DataFrame best practices: schema-on-read, partition pruning, parquet predicate pushdown, and deterministic aggregation pipelines with tests and CI-friendly samples.

## The Local Implementation

- **Current Logic:** A Scala/SBT project that downloads parquet-formatted trip data from public sources, loads into Spark, normalizes schemas across years, runs validations, and computes aggregated yearly and quarterly metrics with configurable year ranges and quarterly sampling (Jan/Apr/Jul/Oct).
- **Bottleneck:** Large IO volume and schema drift across years; local runs are limited by available memory and CPU.

## Scaling Strategy

- **Vertical vs. Horizontal:** Move to cluster mode with sufficient executors for parallelism; optimize partitioning strategy and caching for repeated transforms.
- **State Management:** Use checkpointing and write intermediate artifacts to durable storage (S3/HDFS) to avoid recomputation.

## Comparison to Industry Standards

- **My Project:** Practical ETL example focused on reproducible analytics for public datasets.
- **Industry:** Production ETL adds orchestration (Airflow/Argo), data cataloging, monitoring, and schema evolution tooling.
- **Gap Analysis:** To reach production readiness, integrate with workflow orchestration for scheduling and error recovery, add data lineage and schema versioning systems, implement comprehensive monitoring (job metrics, data quality checks), and automate handling of schema evolution and drift.

## Experiments & Metrics

- **Job runtime:** end-to-end processing time per year and per quarter.
- **Resource efficiency:** executor memory/CPU utilization and optimal partition counts.
- **Data quality validation:** row count, null rate, and schema conformance checks per ingestion batch; flag regressions against baselines.
- **Partition strategy comparison:** measure read/write throughput and shuffle volume across different partition key choices (time-based vs. hash-based).

## Risks & Mitigations

- **Schema drift:** implement schema merging strategies and robust validation with automatic alerting on unexpected column changes.
- **Data skew:** monitor partition sizes and repartition when a small number of keys dominate; use salted keys or custom partitioners for known-skewed columns.
- **Resource exhaustion on large datasets:** set memory guardrails per executor, use adaptive query execution (AQE) to auto-tune shuffle partitions, and profile spill-to-disk behavior.
