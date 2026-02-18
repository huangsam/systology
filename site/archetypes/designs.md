---
title: "Short title"
description: "Short description"
summary: "One-line summary used on index pages"
tags: []
categories: ["designs"]
draft: true
---

## 1. Problem Statement & Constraints

Write a concise problem statement describing the core business or technical problem you're solving.

### Functional Requirements

- State what the system must do (e.g., accept requests, aggregate data, query results).

### Non-Functional Requirements

- **Scale:** Requests per second (avg/peak), data volume, growth trajectory.
- **Latency:** P50, P99 end-to-end latencies or throughput SLAs.
- **Consistency:** Strong consistency, eventual consistency, or specific guarantees (e.g., exactly-once).
- **Availability:** Uptime target (e.g., 99.99%), fault tolerance, regional failover.
- **Workload Profile:**
  - Read:Write ratio (e.g., 90:10)
  - QPS avg/peak (e.g., 2k/200k)
  - Average payload size
  - Key skew (uniform, moderate, high)
  - Data retention period
- **Other constraints:** Budget, data residency, compliance, tech stack preferences.

## 2. High-Level Architecture

Include a diagram and brief component responsibilities.

{{< mermaid >}}
graph LR
  Client --> API[API Layer]
  API --> Worker[Worker/Workers]
  Worker --> Store[(Data store)]
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

Describe key components, data model, and interfaces.

## 4. Operational Excellence

List SLIs/SLOs, monitoring/alerting strategy, and any operational considerations (e.g., canary releases, rollbacks, etc.).
