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

## Deep Dive & Trade-offs

### Deep Dive

- **Priority routing:** incoming notification requests are classified into priority tiers (high / normal / low) based on the notification type (e.g., security alerts = high, order updates = normal, marketing = low). Each tier maps to a separate message queue with independent consumer groups, ensuring that a flood of marketing messages never delays a critical security alert.
- **Channel adapters:** each delivery channel (Push / SMS / Email) is encapsulated in a pluggable adapter behind a common `Deliver(message)` interface. Adapters handle provider-specific concerns: APNs/FCM token management for push, Twilio/SNS API contracts for SMS, SES/SendGrid connection pooling for email. Adding a new channel (e.g., Slack, WhatsApp) requires only implementing the adapter interface.
- **Template engine with i18n:** notifications reference versioned templates stored in a Template Service. Templates use a lightweight markup (Mustache / Handlebars) with variable interpolation. Localisation is handled by keying templates on `(template_id, locale)` pairs; a fallback chain (`user_locale → region_default → en`) ensures every user receives a rendered message.
- **User preference store:** a dedicated Preferences DB stores per-user opt-in/opt-out flags, quiet hours, and channel preferences. The dispatcher consults preferences before sending and silently drops or defers messages that violate the user's settings. Preferences are cached in Redis with a short TTL to avoid a DB lookup on every dispatch.
- **Rate limiting:** two layers of rate limiting. Platform-level: global token-bucket rate limits per channel to stay within provider quotas (e.g., 100 SMS/sec via Twilio). User-level: per-user sliding-window limits (e.g., max 5 push notifications per hour) to prevent notification fatigue and reduce uninstall rates.
- **Delivery tracking and receipts:** every outbound message is assigned a unique `delivery_id` and tracked through states (`QUEUED → DISPATCHED → DELIVERED → READ | BOUNCED | FAILED`). Channel adapters asynchronously consume provider webhooks (delivery receipts, bounce notifications) and update the Delivery Tracker DB, enabling real-time delivery dashboards and retry decisions.
- **Fanout for broadcast notifications:** for large-audience broadcasts (e.g., app-wide announcements), the API accepts a segment definition rather than individual recipient lists. A Fanout Worker resolves the segment against the user store in batches, enqueuing individual messages into the appropriate priority queue. This avoids exploding the request payload and allows progress tracking.
- **Retry and dead-letter handling:** failed deliveries are retried with exponential backoff (capped at 3 attempts for SMS/push, 5 for email). Permanently failed messages (hard bounces, invalid tokens) are routed to a DLQ for inspection and trigger automatic preference updates (e.g., mark push token as stale).

### Trade-offs

- Per-priority queues vs. single queue with priority field: separate queues provide strong isolation and independent scaling, but increase operational overhead (more queues to monitor and tune); a single priority queue is simpler but risks head-of-line blocking if the consumer cannot process fast enough.
- Push-based delivery vs. pull-based (inbox model): push is lower latency for real-time engagement but requires managing device tokens and handling offline users; an inbox/pull model is more reliable for guaranteed delivery but adds read latency and a polling or WebSocket infrastructure.
- Inline template rendering vs. pre-rendered messages: inline rendering allows last-minute personalisation and A/B testing, but adds latency in the dispatch path; pre-rendering at enqueue time is faster but locks in content and makes template corrections harder after enqueue.

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
