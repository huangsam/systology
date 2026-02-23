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

## Data Design

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

- **Idempotency keys:** Client-generated keys stored in Postgres/Redis (24h TTL). Subsequent requests return stored responses without re-executing, preventing double-charges from network retries.

- **Payment state machine:** Strict transitions (`CREATED → AUTHORIZED → CAPTURED → SETTLED`). Invalid moves are rejected; all state changes are persisted atomically with full audit metadata.

- **Double-entry ledger:** Offsetting debit/credit entries (sum to zero). Append-only model ensures integrity; corrections use compensating entries rather than mutations for auditing.

- **Gateway abstraction:** Unified interface (`authorize`, `capture`, `refund`). Decouples business logic from provider APIs (Stripe, PayPal), enabling routing rules and provider migrations.

- **Reconciliation jobs:** Hourly jobs pull gateway settlement reports to validate against the internal ledger. Nightly deep reconciliations re-derive balances from raw entries to flag discrepancies.

- **PCI-DSS isolation:** Card data tokenized at the edge via SDKs. Backend handles only opaque tokens stored in a secure vault, keeping the main application out of PCI scope.

- **Event-driven webhooks:** State changes emit events to Kafka/SNS. A dispatcher delivers these to downstream services (order, notification) with at-least-once semantics and HMAC signatures.

- **Currency & FX:** Amounts stored as integers in the smallest unit (cents) to avoid floating-point errors. Multi-currency uses FX rates captured at authorization, tracking original and settled values.

### Trade-offs

- **Sync vs. Async Gateway Calls:** Sync is simpler for clients but blocks during latency; Async (Webhooks) decouples latency but requires polling/WebSocket infra and client complexity.

- **Append-only vs. Mutable Ledger:** Append-only provides a tamper-evident audit trail but increases verbosity; Mutable is simpler for low-scale but risks integrity and auditing gaps.

- **Single vs. Multi-gateway:** Single is operationally simple but risks lock-in/SPOF; Multi-gateway improves resilience but adds routing, reconciliation, and integration complexity.

## Operational Excellence

### SLIs / SLOs
- SLO: 99.99% of payment API requests return a response (success or well-defined error) within 2 seconds.
- SLO: 0 ledger imbalances (debits and credits sum to zero at all times).
- SLIs: payment_success_rate, gateway_latency_p99, ledger_balance_check, reconciliation_discrepancy_count, idempotency_cache_hit_rate.

### Monitoring & Alerts (examples)

Alerts:

- `payment_success_rate < 95%` (5m)
    - Severity: P1 (gateway degradation or integration bug; check gateway status page and recent deploys).
- `ledger_imbalance != 0`
    - Severity: P0 (data integrity violation; halt writes, investigate immediately).
- `reconciliation_discrepancy_count > 0` after hourly job
    - Severity: P2 (flag for finance team review; investigate settlement report gaps).

### Testing & Reliability
- Run end-to-end payment flows against gateway sandbox/test environments in CI to catch integration regressions.
- Chaos-test gateway timeouts: inject artificial latency and verify the state machine correctly marks payments as `FAILED` and the idempotency layer handles retries.
- Audit the ledger monthly by re-deriving all balances from raw entries and comparing against cached aggregates.

### Backups & Data Retention
- Replicate the ledger and payment databases across availability zones with synchronous replication (RPO = 0).
- Retain all payment and ledger records for 7 years minimum to meet financial regulatory requirements.
- Store PCI-scoped token vault backups in an encrypted, access-audited cold store with separate key management.
