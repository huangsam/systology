---
title: "Privacy-Preserving Federated Learning Platform"
description: "Distributed learning without data sharing."
summary: "Platform design for federated learning that trains across devices without sharing raw data, with secure aggregation and privacy safeguards."
tags: ["distributed-systems", "ml", "privacy"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Build a platform for federated learning that trains models across distributed devices without sharing raw data, incorporating privacy-preserving techniques. The system must scale to millions of devices, ensure secure aggregation of updates, and maintain model accuracy while adhering to privacy constraints and handling communication latencies.

### Functional Requirements

- Train models across distributed devices without centralised data collection.
- Aggregate model updates securely and privately.
- Support client device heterogeneity (connectivity, compute).

### Non-Functional Requirements

- **Scale:** 1M+ devices participating per training round.
- **Availability:** 99.5% platform uptime; tolerates device dropout.
- **Consistency:** Secure aggregation; privacy-preserving (differential privacy).
- **Latency:** Training round completion < 1 hour.
- **Workload Profile:**
    - Read:Write ratio: ~1:1
    - Update rate: 10–100 updates/sec per node
    - Retention: 100 training rounds of checkpoints

## High-Level Architecture

{{< mermaid >}}
graph TD
    Coordinator[Coordinator] -->|broadcast model params| Selector[Device Selector]
    Selector --> DeviceA[Device A]
    Selector --> DeviceB[Device B]
    Selector --> DeviceN["Device N (...)"]
    DeviceA -->|encrypted update| Aggregator[Secure Aggregator]
    DeviceB -->|encrypted update| Aggregator
    DeviceN -->|encrypted update| Aggregator
    Aggregator --> GlobalModel[(Global Store)]
    GlobalModel -->|averaged params| Coordinator
{{< /mermaid >}}

## Data Design

### Global Model Store (Object Store / Registry)
| Artifact | Type | Description | Versioning |
| :--- | :--- | :--- | :--- |
| `weights.bin` | Float32 Array | Flat buffer of averaged model parameters. | Per Round |
| `config.json` | JSON | Model architecture and hyperparameters. | Immutable |
| `privacy.log` | Cumulative | Rolling ε (epsilon) and δ (delta) spend. | 100 Rounds |

### Round Metadata (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **rounds** | `round_id` | Int (PK) | Sequential round number. |
| | `client_count`| Int | Number of successfully aggregated clients. |
| | `val_accuracy` | Float | Server-side validation accuracy. |
| | `noise_scale` | Float | DP noise multiplier used in this round. |

## Deep Dive & Trade-offs

### Deep Dive

- **FedAvg protocol:** Coordinator broadcasts parameters to a client subset. Devices train locally and return gradients; server averages updates to produce the next model.

- **Secure aggregation:** Cryptographic protocols ensure the server only sees the aggregate sum, never individual updates. Includes dropout tolerance for connectivity issues.

- **Differential Privacy (DP):** Clips gradients and adds noise to bound individual device influence. Tracks a cumulative (ε, δ) budget to halt training when limits are reached.

- **Client scheduling:** Stratified sampling ensures representation. Participation restricted to devices on Wi-Fi with sufficient battery to minimize user impact.

- **Communication efficiency:** Quantization (8-bit) and sparsification (Top-K gradients) reduce bandwidth. Vital for making ML feasible over mobile networks for large models.

- **Non-IID handling:** Techniques like FedProx stabilize convergence across heterogeneous datasets. Periodic server-side validation detects divergence early.

- **Model rollouts:** Checkpointed models roll out via canary stages. Monitoring accuracy and fairness across device cohorts ensures quality before full promotion.

### Trade-offs

- **Secure Agg vs. Performance:** Cryptography adds significant overhead and complexity but is essential to prevent a compromised server from reconstructing private user data.

- **DP vs. Accuracy:** Stronger privacy injects more noise, reducing accuracy. Teams must balance regulatory compliance against model performance requirements.

- **Sample Breadth vs. Round Speed:** Larger cohorts improve gradient quality but increase round latency and bandwidth; smaller samples are faster but noisier.

## Operational Excellence

### SLIs / SLOs
- SLO: 95% of FL rounds complete within 1 hour.
- SLO: Model accuracy on the server-side validation set improves or remains stable across rounds (no regression > 1%).
- SLIs: round_duration_p95, client_participation_rate, model_accuracy_delta, privacy_budget_consumed, dropped_client_rate.

### Monitoring & Alerts (examples)

Alerts:

- `round_duration_p95 > 50min` for 3 consecutive rounds
    - Severity: P2 (investigate slow clients or network issues).
- `model_accuracy_delta < -2%` round-over-round
    - Severity: P1 (potential poisoning attack or data distribution shift; halt training).
- `privacy_budget_consumed > 80%`
    - Severity: P2 (approaching DP budget limit; plan transition to public data or halt).

### Testing & Reliability
- Simulate FL rounds with synthetic non-IID data and verify convergence within expected rounds.
- Run adversarial tests: inject poisoned updates from rogue clients and confirm that norm-clipping and DP defences detect or neutralise them.
- Load-test the aggregator with 10× the expected client concurrency to validate throughput and memory under peak conditions.

### Backups & Data Retention
- Store global model checkpoints for every round in a versioned object store; retain the last 30 rounds and archive milestone checkpoints indefinitely.
- Client data never leaves the device; no server-side raw data backups exist or are needed.
- Retain round-level metadata (participation counts, accuracy, privacy spend) indefinitely for auditing and compliance.
