---
title: "Privacy-Preserving Federated Learning Platform"
description: "Distributed learning without data sharing."
summary: "Platform design for federated learning that trains across devices without sharing raw data, with secure aggregation and privacy safeguards."
tags: ["algorithms", "distributed-systems", "ml", "privacy"]
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

A Coordinator broadcasts global model parameters to a Device Selector that samples client devices. Devices train locally on private data and send encrypted weight updates to a Secure Aggregator. Cryptographic aggregation preserves privacy before writing averaged parameters back to the Global Store for the next round.

## Data Design

The Global Model Store acts as a versioned object registry for network weights, architectures, and privacy spend logs. A separate relational database tracks per-round telemetry (participation, dropouts, validation accuracy).

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

{{< pseudocode id="fedavg-algorithm" title="Federated Averaging (FedAvg)" >}}
```python
def federated_averaging(global_model, client_devices, current_round, num_rounds):
    """
    Simplified FedAvg Training Loop (Server-side & Client-side)
    """
    for round_num in range(current_round, num_rounds):

        # 1. Server: Select a random subset of available clients for this round
        participating_clients = select_clients(client_devices, fraction=0.1)

        client_updates = []
        total_data_points = 0

        # 2. Server broadcasts the current global model weights to selected clients
        global_weights = global_model.get_weights()

        # 3. Clients: Train locally (in parallel)
        for client in participating_clients:
            # Client downloads global weights and initializes a local model
            local_model = initialize_model(global_weights)

            # Client trains on their private, local dataset exclusively
            client_data_count = client.dataset.size()
            local_model.train(client.dataset, epochs=5, batch_size=32)

            # Client sends updated weights back (securely/encrypted in reality)
            client_updates.append({
                'weights': local_model.get_weights(),
                'sample_count': client_data_count
            })
            total_data_points += client_data_count

        # 4. Server: Securely aggregate updates (weighted average)
        new_global_weights = []

        # For each layer/parameter in the model:
        for p_idx in range(len(global_weights)):
            layer_sum = 0

            # Sum the weighted parameters from all clients
            for update in client_updates:
                weight_factor = update['sample_count'] / total_data_points
                layer_sum += update['weights'][p_idx] * weight_factor

            new_global_weights.append(layer_sum)

        # 5. Server updates the global model for the next round
        global_model.set_weights(new_global_weights)

    return global_model
```
{{< /pseudocode >}}

### Deep Dive

- **Secure aggregation:** Cryptographic protocols ensure the server only sees the aggregate sum, protecting individual updates while tolerating device dropouts.

- **Differential Privacy (DP):** Clipping gradients and adding noise bounds individual influence. A cumulative (ε, δ) budget halts training upon exhaustion.

- **Client scheduling:** Stratified sampling targets devices on Wi-Fi with sufficient battery to minimize user impact while ensuring representation.

- **Communication efficiency:** Quantization (8-bit) and sparsification (Top-K gradients) drastically reduce bandwidth for mobile network feasibility.

- **Non-IID handling:** Techniques like FedProx stabilize convergence across heterogeneous client datasets, caught early by server-side validation.

- **Model rollouts:** Checkpoints deploy via canary stages, promoting only after monitoring accuracy and fairness across device cohorts.

### Trade-offs

- **Secure Agg vs. Performance:** Cryptography adds significant overhead and complexity but is essential to prevent a compromised server from reconstructing private user data.

- **DP vs. Accuracy:** Stronger privacy injects more noise, reducing accuracy. Teams must balance regulatory compliance against model performance requirements.

- **Sample Breadth vs. Round Speed:** Larger cohorts improve gradient quality but increase round latency and bandwidth; smaller samples are faster but noisier.

## Operational Excellence

### SLIs / SLOs
- SLO: 95% of FL rounds complete within 1 hour.
- SLO: Model accuracy on the server-side validation set improves or remains stable across rounds (no regression > 1%).
- SLIs: round_duration_p95, client_participation_rate, model_accuracy_delta, privacy_budget_consumed, dropped_client_rate.

### Reliability & Resiliency

- **Simulation**: Verify convergence with non-IID data in synthetic rounds.
- **Adversarial**: Test poisoning defenses via rogue client injection.
- **Load**: Test aggregation at 10x client concurrency for memory/throughput.
