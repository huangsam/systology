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

## Deep Dive & Trade-offs

### Deep Dive

- **Virtual waiting room:** when traffic exceeds a configured threshold (e.g., 50 k concurrent connections), incoming users are placed in a FIFO queue served by a lightweight waiting-room service. Users receive a position token and are admitted in batches using a token-bucket algorithm, smoothing the thundering-herd effect. The waiting room page is fully static, served from the CDN, and polls the admission endpoint on a jittered interval.
- **Inventory reservation with Redis:** inventory for each SKU is stored as a Redis key (`inv:<sku_id>`). Reservation uses an atomic Lua script that `DECR`s the counter only if the result is ≥ 0, returning success or sold-out in a single round-trip. This avoids race conditions without distributed locks and supports ~100 k atomic operations/sec per shard.
- **Two-phase purchase flow:** Phase 1 (Reserve): deduct inventory and create a reservation record with a TTL (e.g., 10 minutes). Phase 2 (Confirm): upon successful payment, mark the reservation as confirmed in the Order DB. If the payment fails or the TTL expires, a background reaper releases the reserved inventory back to Redis, preventing ghost holds.
- **Connection shedding at the edge:** the CDN / edge layer enforces per-IP rate limits and connection caps. Under extreme load, the API gateway applies adaptive load shedding (HTTP 503 with `Retry-After`) using a PID controller that targets a fixed request concurrency per backend pod. This protects the reservation service from overload.
- **Database sharding for orders:** the Order DB is horizontally sharded by `order_id` (hash-based) to distribute write load. Each shard uses optimistic concurrency control (version column) to handle the rare case of concurrent updates to the same order during payment confirmation.
- **Idempotent operations:** every reservation and payment request carries a client-generated idempotency key. The API deduplicates by checking a short-lived idempotency store (Redis, 15-minute TTL) before processing, preventing double-charges from retries or network glitches.
- **Pre-warming and capacity planning:** before a scheduled sale event, pre-scale all services to expected peak capacity, warm Redis with inventory keys, and pre-populate CDN caches for product pages. Capacity is estimated from historical data and pre-sale registration counts.
- **Fairness and bot mitigation:** integrate CAPTCHA challenges at the waiting-room admission boundary and use device fingerprinting plus behavioural analysis to detect and throttle automated purchasing bots.

### Trade-offs

- Redis atomic `DECR` vs. database row-level locks: Redis is orders-of-magnitude faster for hot inventory counters but introduces a single point of failure and requires careful persistence configuration; database locks are more durable but create contention bottlenecks under flash-sale concurrency.
- Virtual waiting room vs. direct admission with rate limiting: the waiting room provides a fairer user experience and predictable backend load, but adds user-perceived latency and engineering complexity; pure rate limiting is simpler but leads to random request rejection under load.
- Short reservation TTL vs. long TTL: shorter TTLs (5 min) recycle unsold inventory faster, improving sell-through rate, but risk timing out legitimate slow payers; longer TTLs (15 min) are user-friendlier but can hold inventory hostage if many users abandon.

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
