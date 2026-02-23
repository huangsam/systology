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

## Data Design

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

- **Priority routing:** High/Normal/Low tiers mapped to independent queues and consumer groups. Prevents lower-priority spikes (e.g., marketing) from blocking critical alerts (e.g., security).

- **Channel adapters:** Pluggable adapters (Push, SMS, Email) behind a `Deliver()` interface. Encapsulates provider-specific logic like token management (FCM/APNs) or connection pooling (SES/SendGrid).

- **Template engine & i18n:** Versioned templates with Mustache/Handlebars interpolation. Localisation keyed by `(template_id, locale)` with a fallback chain (`user_locale → region_default → en`).

- **User preferences:** Dedicated DB/Cache for opt-in flags, quiet hours, and channel overrides. Dispatchers consult Redis-cached preferences to drop/defer messages.

- **Double-layer rate limiting:** Global token-buckets enforce provider quotas (e.g., 100 SMS/sec); user-level sliding windows prevent spam and reduce app uninstalls.

- **Delivery tracking:** Outbound messages tracked through lifecycle states (`QUEUED → DISPATCHED → DELIVERED → READ`). Adapters consume provider webhooks to update statuses for real-time dashboards.

- **Broadcast fanout:** For app-wide alerts, workers resolve user segments in batches and enqueue individual messages. Avoids massive payloads and enables progress tracking for large campaigns.

- **Retries & DLQ:** Failed deliveries use exponential backoff (3–5 attempts). Permanent failures route to a Dead Letter Queue and trigger stale-token updates in user profiles.

### Trade-offs

- **Per-priority vs. Single Priority Queue:** Separate queues offer better isolation and scaling but higher operational overhead; a single queue is simpler but risks head-of-line blocking.

- **Push vs. Pull (Inbox) Model:** Push is lower latency but requires complex token/offline management; Pull is more reliable but adds read latency and polling infra.

- **Inline vs. Pre-rendering:** Inline allows last-minute A/B testing and personalization but adds dispatch latency; Pre-rendering is faster at dispatch but less flexible.

## Operational Excellence

### SLIs / SLOs
- SLO: 99% of high-priority notifications delivered to the external provider within 5 seconds of API receipt.
- SLO: 99.9% overall delivery success rate (excluding user opt-outs and invalid tokens).
- SLIs: dispatch_latency_p95_by_priority, delivery_success_rate, bounce_rate, queue_depth_by_priority, rate_limit_rejection_rate.

### Monitoring & Alerts (examples)

Alerts:

- `high_priority_queue_depth > 100` for 2m
    - Severity: P1 (high-priority dispatch is falling behind; scale consumers or investigate provider issues).
- `bounce_rate > 5%` for any channel (10m)
    - Severity: P2 (check for stale tokens, bad email lists, or provider-side filtering).
- `rate_limit_rejections > 10%` of traffic (5m)
    - Severity: P2 (approaching provider quota ceiling; request limit increase or redistribute traffic).

### Testing & Reliability
- Integration-test each channel adapter against provider sandbox environments to validate rendering, delivery, and receipt handling.
- Chaos-test by failing one channel adapter (e.g., SMS) and verifying that only that channel's messages are affected, with no cross-channel impact.
- Load-test the fanout worker with a 10-million-user broadcast to verify batching, queue throughput, and memory footprint.

### Backups & Data Retention
- Retain delivery tracking records for 90 days for debugging and analytics; archive to cold storage for compliance (1 year).
- Store notification templates with version history in a Git-backed store or versioned DB for audit and rollback.
- Back up user preference data with the main user DB; keep Redis cache ephemeral with warm-up on restart.
