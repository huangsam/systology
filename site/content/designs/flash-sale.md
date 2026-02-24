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

The CDN/Edge layer queues bursting traffic into a Virtual Waiting Room. Admitted users pass through an API Gateway to a Reservation service that atomically claims inventory in Redis and writes a temporary hold to the sharded Orders DB. Checkout via the Payment service converts holds into confirmed orders.

## Data Design

Redis provides a high-speed volatile cache for atomic inventory counters and short-lived idempotency keys. The SQL Orders database provides durable transactional truth, utilizing optimistic concurrency control to handle write bursts safely.

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

- **Virtual waiting room:** Token-bucket batch admission smooths the thundering herd, redirecting excess traffic to static polling pages.

- **Atomic inventory:** Redis Lua scripts safely `DECR` counters only if ≥ 0, achieving high concurrency without SQL row-level locks.

- **Two-phase purchase:** Phase 1 reserves inventory with a TTL; Phase 2 confirms on payment. A background reaper recycles expired holds.

- **Edge load shedding:** Edge IP rate limits and API gateway backend-concurrency shedding (503 Retry-After) protect the core.

- **Sharded Order DB:** Horizontal sharding by `order_id` combined with optimistic concurrency control distributes the massive write-burst.

- **Idempotent requests:** Short-lived Redis deduplication of client-generated keys prevents double-charges from network retries.

- **Bot mitigation:** Waiting-room CAPTCHAs, device fingerprinting, and behavioral analysis block automated scalpers.

### Trade-offs

- **Redis vs. DB Locks:** Redis is faster for hot counters but riskier on state loss; DB locks are durable but create massive contention bottlenecks under peak load.

- **Waiting Room vs. Rate Limiting:** Waiting rooms provide a fair experience but add latency; pure rate limiting is simpler but results in random, frustrating rejections.

- **Reservation TTL Length:** Short TTLs recycle inventory faster but risk timeouts; long TTLs are user-friendly but can keep inventory "hostage" if users abandon.

## Operational Excellence

### SLIs / SLOs

- SLO: 99.9% of admitted users can complete a reservation within 500 ms.
- SLO: 0% over-sell rate (linearizable inventory accuracy).
- SLIs: reservation_latency_p99, inventory_accuracy (Redis vs. Order DB reconciliation), waiting_room_admission_rate, payment_success_rate, abandoned_reservation_rate.

### Monitoring & Alerts

- `redis_inventory_missing`: P0 (state lost; halt sale and restore from DB).
- `reservation_latency > 1s`: P1 (backend saturation; trigger load shedding).
- `abandoned_reservations > 30%`: P2 (check payment flow or adjust TTL).

### Reliability & Resiliency

- **Load**: Test at 2x peak (2M users) in staging before each event.
- **Chaos**: Kill Redis primary and verify Sentinel failover without data loss.
- **Reaper**: End-to-end test TTL reaper to ensure hold recycling.

### Retention & Backups

- **Forensics**: Snapshot Redis state immediately before/after sale events.
- **Orders**: All records in SQL DB retained indefinitely for compliance.
- **Logs**: Archive waiting-room and rate-limit logs for 30-day capacity analysis.
