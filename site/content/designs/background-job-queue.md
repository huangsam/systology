---
title: "Background Job Queue for Big Tasks"
description: "Async job for videos and data processing."
summary: "Asynchronous job queue design for resource-heavy tasks (video encoding, data processing) with retries, idempotency, DLQ handling, and autoscaling."
tags: ["concurrency", "distributed-systems", "monitoring", "networking", "queues"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Create an asynchronous job queue system to handle resource-intensive tasks like video encoding or data processing, ensuring reliable execution with retries and idempotency. The system must scale to manage thousands of jobs concurrently, provide visibility into job status, and maintain high availability without impacting the main application performance.

### Functional Requirements

- Queue tasks (e.g., video encoding, data processing).
- Process tasks asynchronously with retry logic.
- Provide visibility into job status and failure handling.

### Non-Functional Requirements

- **Scale:** 10k jobs/hour; concurrent task processing capacity.
- **Availability:** 99.9% job completion reliability.
- **Consistency:** Idempotent operations; no duplicate processing.
- **Latency:** Job start time < 5 minutes after queue.
- **Workload Profile:**
    - Read:Write ratio: ~50:50
    - Peak throughput: 10 jobs/sec
    - Retention: 30 days

## High-Level Architecture

{{< mermaid >}}
graph LR
    Client --> API
    API --> Queue
    Queue --> Worker
    Worker --> Storage
    Worker --> DB
    DB --> Dashboard
{{< /mermaid >}}

Clients submit jobs to an API layer, which places messages onto a durable queue. A pool of pull-based workers picks up the jobs, performing the heavy execution and writing large payloads to object storage. Worker status and job metadata are pushed to a relational database, which powers an operational dashboard for visibility into job progress and failures.

## Data Design

The data storage splits transient job states from long-term payload storage. The primary job queue uses high-throughput message brokers or streams, while the job status store relies on a relational database to track idempotency and execution state. Large payloads are stored in an external blob store, referenced only by URI in the messages.

### Job Message Format (Redis Streams / SQS)
| Field | Type | Description |
| :--- | :--- | :--- |
| `job_id` | UUID | Unique identifier for the job instance. |
| `task_type` | String | e.g., `transcode_v1`, `batch_report_v2`. |
| `payload_ref`| URI | S3 path to the large payload (if applicable). |
| `retries` | Int | Current attempt count. |

### Job Status Store (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **jobs** | `id` | UUID (PK) | Unique job ID. |
| | `status` | Enum | `pending`, `running`, `success`, `failed`. |
| | `result_url`| String | Link to output artifact. |
| | `error_log` | Text | Last error message for DLQ inspection. |
| | `owner_id` | UUID (Idx)| Identifying the worker currently leasing. |

## Deep Dive & Trade-offs

### Deep Dive

- **Queue backend:** Partitioned/durable queues (Redis Streams, Kafka, SQS). Redis is ideal for low-latency; Kafka/SQS for massive scale and native replayability.

- **Worker model:** Pull-based workers with visibility timeouts and heartbeats. Per-worker resource limits (CPU/memory) and local concurrency controls ensure stability.

- **Idempotency:** Every job uses a dedup key/token. Statuses (`PENDING → RUNNING → SUCCESS/FAIL`) are persisted in a Job DB to prevent double-processing.

- **Retries & DLQ:** Exponential backoff with jitter (e.g., 5 attempts) before routing to a Dead-Letter Queue (DLQ) for manual inspection or scripted recovery.

- **Priority & QoS:** Separate queues for latency-sensitive vs. batch jobs. Token-bucket rate limiting prevents overwhelming downstream internal or external services.

- **Autoscaling:** Workers scale based on queue depth and CPU utilization. Independent scaling per job type ensures high-throughput tasks don't starve small, fast jobs.

- **Isolation:** Untrusted or long-running tasks execute in isolated containers/sandboxes with strict network and resource quotas to protect the host system.

### Trade-offs

- **Redis Streams vs. Kafka/SQS:** Redis is faster/simpler; Kafka/SQS scales better for multi-day retention and multi-consumer reprocessing.

- **Inline vs. External Payloads:** Inline is simpler but adds bloat; External (S3) is robust for large files but increases architectural complexity.

## Operational Excellence

### SLIs / SLOs

- SLO: 99% of jobs start processing within 5 minutes of enqueue.
- SLO: 99.9% of jobs succeed (or move to DLQ) within configured retry policy.
- SLIs: queue_depth, job_start_latency_p95, job_completion_latency_p99, job_success_rate (1m/5m windows).

### Monitoring & Alerts

- `queue_depth > 500`: Scale workers or investigate producer flood (P1).
- `job_failure_rate > 3%`: Check recent code or dependency health (P2).
- `DLQ_growth > threshold`: Inspect failing payloads via dashboard (P2).

### Reliability & Resiliency

- **Load/Chaos**: Test worker crashes, storage latency, and network partitions.
- **Idempotency**: Verify retry semantics and duplicate prevention via integration tests.
- **Canary**: Roll out job handler changes to 5% traffic before full promotion.

### Retention & Backups

- **Metadata**: Replicated DB with 30–90 day TTL for historical debugging.
- **Logs**: Archive completed job logs and artifacts with lifecycle rules.
