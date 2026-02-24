---
title: "Notification System"
description: "Scalable multi-channel notification engine for real-time engagement."
summary: "Design of a high-throughput notification service supporting push, email, and SMS with prioritization, rate limiting, and delivery tracking."
tags: ["distributed-systems", "queues"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Build a central notification system that allows various internal services to send messages across multiple channels (Push, SMS, Email). The system must handle massive spikes (e.g., flash sales, breaking news) while ensuring critical alerts are prioritized over marketing messages.

### Functional Requirements

- Send notifications across multiple channels (push, SMS, email).
- Support templating, localization, and user preferences.
- Provide delivery tracking and receipt handling.
- Enforce priority-based queue management.

### Non-Functional Requirements

- **Scale:** Peak volume 100k notifications/minute; handle 10–100× spikes.
- **Availability:** 99.9% uptime; graceful degradation during provider outages.
- **Consistency:** At-least-once delivery; deduplication for idempotency.
- **Latency:** Delivery to external providers within 5 seconds (high-priority).
- **Workload Profile:**
    - Read:Write ratio: ~20:80
    - Peak throughput: 100k notifications/min
    - Retention: 30 days delivery logs; 90 days metrics

## High-Level Architecture

{{< mermaid >}}
graph TD
    Services --> API
    API --> Router
    Router --> HQ[High Q]
    Router --> NQ[Normal Q]
    Router --> LQ[Low Q]
    HQ --> Dispatch
    NQ --> Dispatch
    LQ --> Dispatch
    Dispatch --> Push
    Dispatch --> SMS
    Dispatch --> Email
    Dispatch --> Tracker[(Tracker)]
{{< /mermaid >}}

Internal services send notification requests to a central API. A Router inspects payloads and routes them into tiered queues (High, Normal, Low) to prevent bulk campaigns from blocking critical alerts. Pluggable Dispatch workers format and deliver messages via external providers, logging statuses to a Tracker database.

## Data Design

Redis Streams or Kafka buffer high-throughput transient payloads and routing metadata. A relational Delivery Tracker durably records receipt statuses and error codes from external providers for operational monitoring.

### Notification Queue (Redis Streams / Kafka)
| Field | Type | Description |
| :--- | :--- | :--- |
| `notif_id` | UUID | Correlates dispatch with receipt. |
| `priority` | Enum | `HIGH`, `NORMAL`, `BULK`. |
| `payload` | JSON/Proto | Rendered content or template variables. |
| `channel_pref`| List | `[push, email]` order of retry. |

### Delivery Tracker (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **notifications** | `id` | UUID (PK)| Master ID for tracking. |
| **receipts** | `notif_id` | UUID (FK)| Links to external provider status. |
| | `status` | Enum | `sent`, `delivered`, `opened`, `bounced`.|
| | `err_code` | String | Provider-specific failure reason. |

## Deep Dive & Trade-offs

### Deep Dive

- **Channel adapters:** Pluggable adapters behind a standard `Deliver()` interface encapsulate complex token management and connection pooling per provider.

- **Template engine & i18n:** Versioned templates use Mustache/Handlebars interpolation, resolving localization via a priority chain (`user_locale → region_default → en`).

- **User preferences:** Redis-cached opt-ins, quiet hours, and channel overrides instruct Dispatchers to dynamically drop or defer messages.

- **Double-layer rate limiting:** Global token-buckets enforce provider quotas, while user-level sliding windows block spam and prevent app uninstalls.

- **Delivery tracking:** Adapters ingest provider webhooks to transition outbound message lifecycles (`QUEUED → DISPATCHED → DELIVERED → READ`) for real-time dashboards.

- **Broadcast fanout:** Workers batch-resolve user segments and enqueue individual messages, avoiding massive payloads and enabling targeted retries for large campaigns.

- **Retries & DLQ:** Failed deliveries retry with exponential backoff. Permanent failures hit a Dead Letter Queue and trigger stale-token cleanups.

### Trade-offs

- **Per-priority vs. Single Priority Queue:** Separate queues offer better isolation and scaling but higher operational overhead; a single queue is simpler but risks head-of-line blocking.

- **Push vs. Pull (Inbox) Model:** Push is lower latency but requires complex token/offline management; Pull is more reliable but adds read latency and polling infra.

- **Inline vs. Pre-rendering:** Inline allows last-minute A/B testing and personalization but adds dispatch latency; Pre-rendering is faster at dispatch but less flexible.

## Operational Excellence

### SLIs / SLOs

- SLO: 99% of high-priority notifications delivered to the external provider within 5 seconds of API receipt.
- SLO: 99.9% overall delivery success rate (excluding user opt-outs and invalid tokens).
- SLIs: dispatch_latency_p95_by_priority, delivery_success_rate, bounce_rate, queue_depth_by_priority, rate_limit_rejection_rate.

### Monitoring & Alerts

- `high_priority_queue_depth > 100`: Scale consumers or check providers (P1).
- `bounce_rate > 5%`: Check for stale tokens or provider filtering (P2).
- `rate_limit_rejections > 10%`: Request quota increase or redistribute (P2).

### Reliability & Resiliency

- **Integrations**: Validate each channel against provider sandboxes.
- **Chaos**: Fail one channel to verify no cross-channel impact.
- **Scale**: Load-test fanout worker with 10M-user broadcast batching.

### Retention & Backups

- **Tracking**: Logs kept 90 days; archive to cold storage for 1 year.
- **Templates**: Git-backed or versioned DB store for audit and rollback.
- **Preferences**: SQL backup for primary data; Redis cache is ephemeral.
