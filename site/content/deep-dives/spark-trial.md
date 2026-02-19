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

**Problem:** I have used Spark SQL and PySpark in the past, but also wanted to complete my understand of the Spark ecosystem by writing a Scala-based Spark application that handles real-world data challenges: schema drift across years, large IO volumes, and the need for reproducible analytics. The project serves as a practical example of Spark's core abstractions (DataFrames, Datasets, RDDs) and optimization techniques (partitioning, caching) while also addressing common pitfalls like schema evolution and data skew.

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

## Risks & Mitigations

- **Schema drift:** implement schema merging strategies and robust validation with automatic alerting on unexpected column changes.
- **Data skew:** monitor partition sizes and repartition when a small number of keys dominate; use salted keys or custom partitioners for known-skewed columns.
- **Resource exhaustion on large datasets:** set memory guardrails per executor, use adaptive query execution (AQE) to auto-tune shuffle partitions, and profile spill-to-disk behavior.
