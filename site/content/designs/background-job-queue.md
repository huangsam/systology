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

Clients submit jobs via an API to a durable queue. Pull-based workers execute tasks, writing payloads to object storage. Worker status and job metadata are synced to a relational database, powering a real-time operational dashboard.

## Data Design

Message brokers buffer the high-throughput primary job queue. A relational database tracks idempotency and execution status. Large payloads reside in an external blob store, referenced via URI to keep messages small.

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

- **Queue backend:** Redis Streams offers low-latency; Kafka/SQS scale massively with native replayability.

- **Worker model:** Pull-based workers use visibility timeouts and heartbeats, with local resource limits to ensure stability.

- **Idempotency:** Unique deduction keys and persistent database statuses prevent duplicate processing.

- **Retries & DLQ:** Jobs retry using exponential backoff with jitter before routing to a Dead-Letter Queue (DLQ).

- **Priority & QoS:** Dedicated queues isolate latency-sensitive from batch jobs. Token-bucket rate limits protect downstream services.

- **Autoscaling:** Workers scale independently per job type based on queue depth and CPU utilization.

- **Isolation:** Untrusted jobs execute in sandboxed containers with strict resource quotas.

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
