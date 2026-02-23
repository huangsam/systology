---
title: "Short title"
description: "Short description"
summary: "One-line summary used on index pages"
tags: []
categories: ["designs"]
draft: true
---

## Problem Statement & Constraints

Write a concise problem statement describing the core business or technical problem you're solving.

### Functional Requirements

- State what the system must do (e.g., accept requests, aggregate data, query results).

### Non-Functional Requirements

- **Scale:** Requests per second (avg/peak), data volume, growth trajectory.
- **Latency:** P50, P99 end-to-end latencies or throughput SLAs.
- **Consistency:** Strong consistency, eventual consistency, or specific guarantees (e.g., exactly-once).
- **Availability:** Uptime target (e.g., 99.99%), fault tolerance, regional failover.
- **Workload Profile:**
  - Read:Write ratio
  - Peak throughput (QPS / TPS)
  - Data retention
- **Other constraints:** Budget, data residency, compliance, tech stack preferences.

## High-Level Architecture

Include a diagram and brief component responsibilities.

{{< mermaid >}}
graph LR
    Client --> API[API Layer]
    API --> Worker[Worker/Workers]
    Worker --> Store[(Data store)]
{{< /mermaid >}}

## Data Design

Describe the data storage layout (SQL schemas, NoSQL key-spaces, or document formats).

| Store | Purpose | Primary Key / Index | TTL / Retention |
| :--- | :--- | :--- | :--- |
| **Component Name** | Description | Field(s) | Policy |

### Sample Schema / Key Format
```sql
-- SQL snippet or JSON example
```

## Deep Dive & Trade-offs

Describe the system design in detail: key components and their responsibilities, data model and schema, internal interfaces/APIs, and major tradeoffs (e.g., consistency vs. latency, durability vs. throughput). Explain why certain choices were made and what alternatives were considered.

## Operational Excellence

Define Service Level Indicators (SLIs) and Service Level Objectives (SLOs) for your system—what does success look like? Outline the monitoring and alerting strategy (key metrics, dashboards, on-call runbooks). Include operational considerations like graceful degradation, canary releases, rollback procedures, and failover strategies.
