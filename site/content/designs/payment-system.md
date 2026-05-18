---
title: "Payment System"
description: "Reliable global payment processing system architectures."
summary: "A high-integrity architecture for global payment gateways and internal ledgers, emphasizing rigorous idempotency, eventual consistency, and deterministic recovery."
tags: [consistency, data-flows, databases, idempotency, integrity]
categories: ["designs"]
draft: false
date: "2026-02-17T10:27:08-08:00"
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
| | `account_id` | VARCHAR (IDX) | e.g., `user_123`, `gateway_stripe`. |
| | `amount` | BIGINT | Smallest unit (e.g., cents). |
| | `direction` | ENUM | `debit`, `credit`. |
| | `tx_id` | UUID (FK) | Reference to parent transaction. |

## Deep Dive & Trade-offs

{{< pseudocode id="idempotency-key" title="Idempotent Payment Processing" >}}
```python
import stripe
import psycopg2
from psycopg2.extras import RealDictCursor

def process_payment(idempotency_key: str, payment_method_id: str, amount: int, currency: str, user_id: str) -> str:
    # 1. Start a database transaction
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 2. Try to insert the idempotency key.
            # If it exists, constraint violation occurs, preventing double processing.
            try:
                cur.execute("""
                    INSERT INTO idempotency_keys (key, status)
                    VALUES (%s, 'processing')
                """, (idempotency_key,))
            except psycopg2.IntegrityError:
                # Key exists! Fetch the previous result/status and return it
                cur.execute("SELECT status, response FROM idempotency_keys WHERE key = %s", (idempotency_key,))
                existing_record = cur.fetchone()

                if existing_record['status'] == 'completed':
                    return existing_record['response']
                else:
                    raise Exception("Concurrent request processing")

            # 3. Proceed with external Gateway call using Stripe PaymentIntents.
            try:
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    payment_method_types=["card"],
                    capture_method="automatic",
                    description=f"Payment for user {user_id}",
                    metadata={"idempotency_key": idempotency_key},
                    idempotency_key=idempotency_key,
                )

                confirmed_intent = stripe.PaymentIntent.confirm(
                    payment_intent.id,
                    payment_method=payment_method_id,
                    idempotency_key=f"{idempotency_key}:confirm",
                )

                # 4. Write to internal Double-Entry Ledger
                record_ledger_entries(cur, charge_id=confirmed_intent.id, amount=amount)

                # 5. Update Idempotency record to 'completed'
                cur.execute("""
                    UPDATE idempotency_keys
                    SET status = 'completed', response = %s
                    WHERE key = %s
                """, (confirmed_intent.id, idempotency_key))

                conn.commit()
                return confirmed_intent.id

            except Exception as e:
                conn.rollback()  # Rollback ledger entries
                # EDGE CASE: If the payment intent succeeded but ledger writes failed,
                # persist the provider intent ID for reconciliation rather than retrying blindly.
                cur.execute("UPDATE idempotency_keys SET status = 'failed' WHERE key = %s", (idempotency_key,))
                conn.commit()
                raise e
```
{{< /pseudocode >}}

### Deep Dive

- **Payment state machine:** Strict transitions (`CREATED → AUTHORIZED → CAPTURED`) reject invalid moves. Every change persists atomically with full audit metadata.

- **Double-entry ledger:** Offsetting append-only debit/credit entries sum to zero. Corrections require new compensating entries, preserving the immutable audit trail.

- **Gateway abstraction:** A unified interface (`authorize`, `capture`) decouples business logic from provider APIs, easing routing and migrations.

- **PaymentIntent-first flows:** Stripe PaymentIntents (or equivalent provider stateful transaction objects) replace deprecated charge APIs, enabling safer multi-step authorization, capture, and asynchronous confirmation.

- **Reconciliation jobs:** Hourly jobs validate gateway settlement reports against the ledger. Nightly deep passes re-derive balances from raw entries to catch subtle discrepancies.

- **PCI-DSS isolation:** Edge SDKs tokenize card data. The backend handles only opaque tokens in a secure vault, entirely bypassing PCI scope.

- **Event-driven webhooks:** Kafka/SNS dispatches state change events to downstream services with at-least-once delivery and HMAC signatures.

- **Currency & FX:** Integer math on smallest units (cents) avoids floating-point errors. Multi-currency tracks FX rates captured at exact authorization time.

### Trade-offs

- **Sync vs. Async Gateway Calls:** Synchronous calls simplify client logic but introduce latency-induced blocking; Asynchronous flows (Webhooks) decouple latency but require polling or WebSocket infrastructure.

- **Append-only vs. Mutable Ledger:** Append-only ledgers provide a tamper-evident audit trail at the cost of verbosity; Mutable models are simpler for low-scale operations but risk integrity gaps.

- **Single vs. Multi-gateway:** Single gateways are operationally simple but introduce vendor lock-in; Multi-gateway setups improve resilience but add routing and reconciliation complexity.

## Operational Excellence

### Security Considerations
- Service-to-service traffic should be authenticated with mTLS or service-mesh identity (SPIFFE/SPIRE) instead of trusting network location.
- Secrets and API credentials should be managed in a centralized vault with automated rotation and least-privilege access.

### SLIs / SLOs

- SLO: 99.99% of payment API requests return a response (success or well-defined error) within 2 seconds.
- SLO: 0 ledger imbalances (debits and credits sum to zero at all times).
- SLIs: payment_success_rate, gateway_latency_p99, ledger_balance_check, reconciliation_discrepancy_count, idempotency_cache_hit_rate.

### Failure Mode Response

- If ledger reconciliation detects an imbalance, page on-call immediately and fail new intake until the root cause is isolated.
- If external gateway timeouts or decline storms occur, switch traffic to a secondary provider and enqueue pending payment intents for async backfill.
- On SLO breach, follow the incident runbook, notify stakeholders, and prioritize correctness over speed for financial records.

### Reliability & Resiliency

- **Integrations**: End-to-end flows against gateway sandboxes in CI.
- **Chaos**: Inject gateway timeouts to verify state machine and idempotency.
- **Audit**: Monthly balance re-derivation from raw entries vs. aggregates.
