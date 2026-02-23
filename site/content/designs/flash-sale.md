---
title: "Flash Sale / Ticketmaster"
description: "High-concurrency inventory management for massive traffic spikes."
summary: "Design for handling extreme bursts of traffic where limited inventory must be distributed fairly and consistently under heavy load."
tags: ["concurrency", "database", "distributed-systems"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design a ticketing or flash sale system capable of handling millions of users simultaneously trying to purchase a limited set of items (e.g., concert tickets). The system must prevent over-selling, ensure fair access (e.g., virtual waiting rooms), and maintain stable performance during extreme traffic bursts.

### Functional Requirements

- Browse inventory and product details.
- Reserve items with time-limited holds.
- Complete purchases with payment processing.
- Manage a virtual waiting room for fair queue management.

### Non-Functional Requirements

- **Scale:** Handle 1M concurrent users; limited inventory (e.g., 100k tickets).
- **Availability:** 99.99% uptime for sale event duration.
- **Consistency:** Linearizable consistency for inventory counts; no double-selling.
- **Latency:** Inventory check and reservation < 500ms under peak load.
- **Workload Profile:**
    - Read:Write ratio: ~80:20
    - Peak throughput: 1M requests/sec
    - Retention: 30 days post-event

## High-Level Architecture

{{< mermaid >}}
graph TD
    Users --> Edge
    Edge --> WaitRoom[Wait Room]
    WaitRoom --> GW[Gateway]
    GW --> Reserve
    Reserve --> Redis[(Redis)]
    Reserve --> Orders[(Orders)]
    GW --> Payment
    Payment --> Orders
{{< /mermaid >}}

## Data Design

### Inventory Key-Space (Redis)
| Key Pattern | Value Type | Description | TTL |
| :--- | :--- | :--- | :--- |
| `inv:<sku_id>` | Integer | Atomic counter for available items. | Event duration |
| `hold:<sku_id>:<user_id>`| String | Reservation lock / owner ID. | 10 minutes |
| `idemp:<key>` | String | Idempotency key for deduplication. | 15 minutes |

### Order Schema (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **orders** | `id` | UUID (PK) | Unique order identifier. |
| | `user_id` | UUID (FK) | Buyer identifier. |
| | `sku_id` | String | Purchased item ID. |
| | `status` | Enum | `pending`, `confirmed`, `expired`. |
| | `version` | Integer | For optimistic concurrency control. |

## Deep Dive & Trade-offs

### Deep Dive

- **Virtual waiting room:** Admits users in batches via token-bucket once traffic thresholds are exceeded. Simple static pages poll admission endpoints to smooth the thundering herd.

- **Atomic inventory:** Managed in Redis using Lua scripts. `DECR` operations succeed only if the counter remains ≥ 0, providing safe, high-concurrency without row-level locks.

- **Two-phase purchase:** Phase 1 reserves inventory with a TTL (e.g., 10m). Phase 2 confirms on payment. A background reaper releases expired holds back to the pool.

- **Edge load shedding:** CDN/Edge enforces IP rate limits. API gateways shed traffic (503 Retry-After) based on backend concurrency, protecting the reservation core.

- **Sharded Order DB:** Horizontally sharded by `order_id` with optimistic concurrency control. Distributes the massive write-burst across multiple database nodes.

- **Idempotent requests:** Client-generated keys deduplicated in a short-lived Redis store. Prevents double-charges or double-reservations from network retries.

- **Bot mitigation:** CAPTCHA at the waiting room boundary plus device fingerprinting and behavioral analysis blocks automated scalper bots.

### Trade-offs

- **Redis vs. DB Locks:** Redis is faster for hot counters but riskier on state loss; DB locks are durable but create massive contention bottlenecks under peak load.

- **Waiting Room vs. Rate Limiting:** Waiting rooms provide a fair experience but add latency; pure rate limiting is simpler but results in random, frustrating rejections.

- **Reservation TTL Length:** Short TTLs recycle inventory faster but risk timeouts; long TTLs are user-friendly but can keep inventory "hostage" if users abandon.

## Operational Excellence

### SLIs / SLOs
- SLO: 99.9% of admitted users can complete a reservation within 500 ms.
- SLO: 0% over-sell rate (linearizable inventory accuracy).
- SLIs: reservation_latency_p99, inventory_accuracy (Redis vs. Order DB reconciliation), waiting_room_admission_rate, payment_success_rate, abandoned_reservation_rate.

### Monitoring & Alerts (examples)

Alerts:

- `redis_inventory_key_missing` for any active SKU
    - Severity: P0 (inventory state lost; halt sale and restore from Order DB).
- `reservation_latency_p99 > 1s` for 2m
    - Severity: P1 (backend saturation; trigger additional load shedding or scale pods).
- `abandoned_reservation_rate > 30%` (5m window)
    - Severity: P2 (investigate payment flow issues or adjust reservation TTL).

### Testing & Reliability
- Run full-scale load tests simulating 2× expected peak (2 million concurrent users) in a staging environment before each sale event.
- Chaos-test Redis failover: kill the primary and verify Sentinel / Cluster promotes a replica within the reservation TTL window without inventory loss.
- End-to-end test the reservation TTL reaper to ensure expired holds are correctly released back to inventory.

### Backups & Data Retention
- Snapshot Redis inventory state immediately before and after each sale event for forensic reconciliation.
- Retain all order and payment records in the Order DB indefinitely for compliance and dispute resolution.
- Archive waiting-room and rate-limiting logs for 30 days to support post-event capacity analysis.
