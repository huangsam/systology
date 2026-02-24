---
title: "Payment System"
description: "Handling global transactions with high reliability and consistency."
summary: "Design of a scalable payment gateway integration and internal ledger system ensuring idempotency, strict consistency, and failure recovery."
tags: ["database", "distributed-systems"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design a robust payment system that processes customer transactions via third-party gateways (e.g., Stripe, PayPal) while maintaining a high-fidelity internal ledger. The system must handle millions of transactions daily, ensuring that no customer is double-charged and every payment is accurately reconciled.

### Functional Requirements

- Process customer payments via multiple payment gateways.
- Handle refunds, disputes, and state transitions.
- Maintain a double-entry ledger for all transactions.
- Provide idempotency and deduplication for all operations.

### Non-Functional Requirements

- **Scale:** 1M transactions/day; peak 100 TPS.
- **Availability:** 99.99% for critical payment paths.
- **Consistency:** Strict ACID compliance for ledger; external consistency via idempotency keys; eventual for analytics.
- **Latency:** P99 < 2 seconds for payment processing.
- **Workload Profile:**
    - Read:Write ratio: ~30:70
    - Peak throughput: 100 TPS
    - Retention: 7-year ledger; 30 days hot metrics

## High-Level Architecture

{{< mermaid >}}
graph TD
    Client --> API
    API --> PSM[State Machine]
    PSM --> GW[Gateway]
    GW --> Stripe
    GW --> PayPal
    PSM --> Ledger[(Ledger)]
    PSM --> Bus[Events]
    Bus --> Hooks[Webhooks]
    Bus --> Recon
    Recon --> Ledger
{{< /mermaid >}}

An API receives client requests, driving a Payment State Machine that orchestrates the transaction lifecycle. The State Machine calls external Gateways to authorize and capture funds, while synchronously writing double-entry records to a durable Ledger. All state transitions publish to an Event Bus, triggering downstream webhooks and offline Reconciliation.

## Data Design

An Idempotency Store (Redis/Postgres) caches request signatures to prevent double-charging. The core Internal Ledger uses a relational database with append-only tables for immutable debit and credit entries, ensuring strict financial balance.

### Idempotency Store (Redis/Postgres)
| Key Pattern | Value | TTL | Purpose |
| :--- | :--- | :--- | :--- |
| `idem:<key>` | JSON Response | 24 Hours | Prevent double-charges from retries. |
| `lock:<user>` | Boolean | 30 Seconds | Distributed lock during active process. |

### Internal Ledger (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **entries** | `id` | UUID (PK) | Unique entry identifier. |
| | `account_id` | String (Idx) | e.g., `user_123`, `gateway_stripe`. |
| | `amount` | BigInt | Smallest unit (e.g. cents). |
| | `direction` | Enum | `debit`, `credit`. |
| | `tx_id` | UUID (FK) | Reference to parent transaction. |

## Deep Dive & Trade-offs

### Deep Dive

- **Payment state machine:** Strict transitions (`CREATED → AUTHORIZED → CAPTURED`) reject invalid moves. Every change persists atomically with full audit metadata.

- **Double-entry ledger:** Offsetting append-only debit/credit entries sum to zero. Corrections require new compensating entries, preserving the immutable audit trail.

- **Gateway abstraction:** A unified interface (`authorize`, `capture`) decouples business logic from provider APIs, easing routing and migrations.

- **Reconciliation jobs:** Hourly jobs validate gateway settlement reports against the ledger. Nightly deep passes re-derive balances from raw entries to catch subtle discrepancies.

- **PCI-DSS isolation:** Edge SDKs tokenize card data. The backend handles only opaque tokens in a secure vault, entirely bypassing PCI scope.

- **Event-driven webhooks:** Kafka/SNS dispatches state change events to downstream services with at-least-once delivery and HMAC signatures.

- **Currency & FX:** Integer math on smallest units (cents) avoids floating-point errors. Multi-currency tracks FX rates captured at exact authorization time.

### Trade-offs

- **Sync vs. Async Gateway Calls:** Sync is simpler for clients but blocks during latency; Async (Webhooks) decouples latency but requires polling/WebSocket infra and client complexity.

- **Append-only vs. Mutable Ledger:** Append-only provides a tamper-evident audit trail but increases verbosity; Mutable is simpler for low-scale but risks integrity and auditing gaps.

- **Single vs. Multi-gateway:** Single is operationally simple but risks lock-in/SPOF; Multi-gateway improves resilience but adds routing, reconciliation, and integration complexity.

## Operational Excellence

### SLIs / SLOs

- SLO: 99.99% of payment API requests return a response (success or well-defined error) within 2 seconds.
- SLO: 0 ledger imbalances (debits and credits sum to zero at all times).
- SLIs: payment_success_rate, gateway_latency_p99, ledger_balance_check, reconciliation_discrepancy_count, idempotency_cache_hit_rate.

### Reliability & Resiliency

- **Integrations**: End-to-end flows against gateway sandboxes in CI.
- **Chaos**: Inject gateway timeouts to verify state machine and idempotency.
- **Audit**: Monthly balance re-derivation from raw entries vs. aggregates.
