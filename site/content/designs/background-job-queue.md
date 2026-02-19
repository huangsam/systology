---
title: "Background Job Queue for Big Tasks"
description: "Async job for videos and data processing."
summary: "Asynchronous job queue design for resource-heavy tasks (video encoding, data processing) with retries, idempotency, DLQ handling, and autoscaling."
tags: ["concurrency", "distributed-systems", "monitoring", "networking", "queues"]
categories: ["designs"]
draft: false
---

## 1. Problem Statement & Constraints

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
    - Read:Write ratio: ~50:50 (status checks + new enqueues)
    - QPS: avg 3 / peak 10 jobs/sec
    - Avg payload: 2–10 KB per job
    - Key skew: moderate (certain job types more frequent)
    - Retention: 30 days job history

## 2. High-Level Architecture

{{< mermaid >}}
graph LR
    Client --> API
    API --> Queue
    Queue --> Worker
    Worker --> Storage
    Worker --> DB
    DB --> Dashboard
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Queue backend:** prefer durable, partitioned queues (Redis Streams / Kafka / SQS); use Redis Streams for low-latency + simple ops, SQS/Kafka for larger scale and replayability.
- **Payload strategy:** keep messages small (IDs + metadata). Store large media in object storage and reference by URL to avoid queue bloat.
- **Worker model:** pull-based workers with leases/visibility timeouts and periodic heartbeats. Use worker-side concurrency controls and per-worker resource limits (CPU/memory/cgroup).
- **Idempotency:** every job must have a dedup key / idempotency token and be safe to run multiple times. Persist job status (`PENDING` → `RUNNING` → `SUCCEEDED` | `FAILED`) in a Job DB to avoid double work.
- **Retries & poison messages:** exponential backoff with jitter, capped retries (e.g., 5 attempts), then move to a Dead-Letter Queue (DLQ) for manual inspection or automated recovery.
- **Prioritization & QoS:** implement separate queues (or priority fields) for latency-sensitive vs. batch jobs; apply token-bucket rate limiting when calling external services.
- **Scaling strategy:** autoscale workers on queue depth and worker CPU utilization; partition work by job type to scale independently.
- **Transactions & consistency:** use at-least-once semantics internally and rely on idempotent handlers; do not attempt expensive exactly-once semantics across distributed systems.
- **Security & isolation:** run untrusted/long-running jobs in isolated sandboxes (containers) with strict resource quotas and network egress controls.

### Trade-offs

- Redis Streams: low-latency + simple, but requires careful persistence/ops for large retention. Kafka/SQS: better for guaranteed delivery and reprocessing at scale but adds operational complexity.
- Inline payloads: simpler but increases queue size and risk of message loss; object store references increase system complexity but are more robust for large files.

## 4. Operational Excellence

### SLIs / SLOs
- SLO: 99% of jobs start processing within 5 minutes of enqueue.
- SLO: 99.9% of jobs succeed (or move to DLQ) within configured retry policy.
- SLIs: queue_depth, job_start_latency_p95, job_completion_latency_p99, job_success_rate (1m/5m windows).

### Monitoring & Alerts (examples)

Alerts:

- `queue_depth > 500` for 5m
    - Severity: P1 (scale workers / investigate producer flood).
- `job_failure_rate > 3%` (5m)
    - Severity: P2 (investigate recent code or dependency failures).
- `DLQ_size increases > threshold`
    - Severity: P2 (inspect failing payloads).

### Testing & Reliability
- Run regular capacity and chaos tests (worker crashes, storage latency, network partitions).
- Add unit/integration tests for idempotency and retry semantics.
- Canary job handler changes with a small percentage of traffic before full rollout.

### Backups & Data Retention
- Keep job metadata in a replicated DB with TTL for historical debugging (30–90 days).
- Archive completed job logs and store large artifacts in object storage with lifecycle rules to control cost.
