---
title: "Payment System"
description: "Handling global transactions with high reliability and consistency."
summary: "Design of a scalable payment gateway integration and internal ledger system ensuring idempotency, strict consistency, and failure recovery."
tags: ["database", "distributed-systems"]
categories: ["designs"]
draft: false
---

## 1. Problem Statement & Constraints

Design a robust payment system that processes customer transactions via third-party gateways (e.g., Stripe, PayPal) while maintaining a high-fidelity internal ledger. The system must handle millions of transactions daily, ensuring that no customer is double-charged and every payment is accurately reconciled.

- **Functional Requirements:** Process payments, handle refunds, maintain a transaction ledger, and provide idempotency for all operations.
- **Non-Functional Requirements (NFRs):**
    - **Consistency:** Strict ACID compliance for ledger updates; external consistency using idempotency keys.
    - **Availability:** 99.99% for critical payment paths.
    - **Scale:** 1 million transactions per day (peak 100 TPS).
    - **Reliability:** At-least-once delivery for downstream notifications with deduplication.

## 2. High-Level Architecture

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

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Idempotency-key based deduplication:** every payment request includes a client-generated idempotency key. The API stores the key and its response in an idempotency store (Postgres row or Redis, 24-hour TTL) before processing. Subsequent requests with the same key return the stored response without re-executing the payment, preventing double-charges from retries, network timeouts, or client bugs.
- **Payment state machine:** each payment transitions through well-defined states: `CREATED → AUTHORIZED → CAPTURED → SETTLED` (happy path), with branches to `FAILED`, `REFUND_PENDING → REFUNDED`, and `DISPUTED`. Transitions are enforced in application code with a state-machine library; invalid transitions (e.g., `SETTLED → AUTHORIZED`) are rejected. All state changes are persisted atomically with their timestamp and actor for a full audit trail.
- **Double-entry ledger:** every financial operation produces two ledger entries (debit + credit) that sum to zero, ensuring the books always balance. For example, a capture creates `debit: customer_receivable, credit: merchant_payable`. The ledger is append-only; corrections are made via compensating entries, never by mutating existing rows. This model supports reconciliation, auditing, and multi-currency accounting.
- **Gateway abstraction layer:** a `PaymentGateway` interface encapsulates provider-specific API calls (`authorize`, `capture`, `refund`, `void`). Concrete implementations (Stripe, PayPal, Adyen) handle serialisation, authentication, and error mapping. The abstraction enables routing rules (e.g., route cards to Stripe, wallets to PayPal), A/B testing of providers, and seamless provider migration without touching business logic.
- **Reconciliation jobs:** a scheduled batch job (hourly) pulls settlement reports from each gateway's API and compares them against the internal ledger. Discrepancies (missing settlements, amount mismatches) are flagged for manual review. A nightly deep reconciliation re-derives expected balances from raw ledger entries and validates against gateway statements.
- **PCI-DSS isolation:** cardholder data (PAN, CVV) never touches the main application. Card details are tokenised at the edge using the gateway's client-side SDK (Stripe.js, hosted fields). The backend only handles opaque tokens, keeping it out of PCI scope. Tokens are stored in a dedicated, access-controlled vault service with field-level encryption.
- **Webhook delivery for downstream consumers:** payment state changes emit events to an internal event bus (Kafka / SNS). A Webhook Dispatcher consumes these events and delivers them to registered endpoints (order service, notification service, analytics) with at-least-once semantics, exponential retry, and HMAC signature verification for authenticity.
- **Currency handling and FX:** amounts are stored as integers in the smallest currency unit (cents, pence) to avoid floating-point errors. Multi-currency support uses a snapshot FX rate captured at authorisation time, stored alongside the payment record. Settlement currency conversion is handled by the gateway; the ledger records both original and settled amounts.

### Trade-offs

- Synchronous gateway calls vs. async with callbacks: synchronous is simpler and gives the client an immediate result, but ties up a thread during provider latency spikes; async with webhooks decouples latency but requires the client to poll or listen for completion, adding complexity.
- Append-only ledger vs. mutable transaction table: append-only provides a tamper-evident audit trail and simplifies reconciliation, but makes corrections more verbose (compensating entries); a mutable table is simpler for small-scale systems but risks silent data loss and complicates auditing.
- Single vs. multi-gateway: a single gateway is operationally simpler, but creates vendor lock-in and a single point of failure; multi-gateway improves resilience and negotiation leverage but adds routing logic, reconciliation complexity, and multiple provider integrations to maintain.

## 4. Operational Excellence

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
