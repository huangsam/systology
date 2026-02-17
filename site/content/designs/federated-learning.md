---
title: "Privacy-Preserving Federated Learning Platform"
description: "Distributed learning without data sharing."
summary: "Platform design for federated learning that trains across devices without sharing raw data, with secure aggregation and privacy safeguards."
tags: ["privacy","ml","distributed-systems"]
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Build a platform for federated learning that trains models across distributed devices without sharing raw data, incorporating privacy-preserving techniques. The system must scale to millions of devices, ensure secure aggregation of updates, and maintain model accuracy while adhering to privacy constraints and handling communication latencies.

- **Functional Requirements:** Train models across devices without data sharing.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 1M devices.
    - **Availability:** 99.5%.
    - **Consistency:** Secure aggregation.
    - **Latency Targets:** Round < 1 hour.

## 2. High-Level Architecture

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

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Federated averaging (FedAvg) protocol:** the coordinator broadcasts the current global model to a sampled subset of devices. Each device trains locally on its private data for several epochs, then sends a model update (gradient or weight delta) back. The aggregator averages the updates, weighted by each device's sample count, to produce a new global model. Repeat for hundreds of rounds until convergence.
- **Secure aggregation:** use cryptographic secure aggregation (e.g., Bonawitz et al. protocol) so that the server only sees the sum of client updates, never individual updates. This guarantees that even a compromised server cannot reconstruct any single device's data. Support dropout tolerance so that rounds succeed even when some clients go offline mid-round.
- **Differential privacy (DP):** apply local or central DP to bound the influence of any single device. Clip per-device gradients to a fixed L2 norm, then add calibrated Gaussian noise. Track a cumulative privacy budget (ε, δ) and halt training or switch to a public dataset when the budget is exhausted.
- **Client selection and scheduling:** sample clients proportionally to data volume, but stratify by device type and timezone to ensure representativeness and avoid mobile‑bias. Enforce minimum battery level and Wi-Fi connectivity before participation. Schedule rounds during off-peak hours to reduce user impact.
- **Communication efficiency:** compress updates using quantisation (e.g., 8-bit or ternary gradients), sparsification (send only top-k gradient elements), or learned compression codecs. This reduces per-round bandwidth from megabytes to kilobytes for large models, making federated learning feasible on mobile networks.
- **Heterogeneity and non-IID data:** device datasets are typically non-IID and imbalanced. Use techniques like FedProx (proximal regularisation) or scaffold (control variates) to stabilise convergence. Run periodic evaluations on a held-out server-side validation set to detect divergence.
- **Model versioning and rollout:** store each global checkpoint with a round number and evaluation metrics. Roll out the updated model to production gradually (canary → percentage ramp → full fleet) and monitor accuracy and fairness metrics before promoting.

### Tradeoffs

- Secure aggregation vs performance: cryptographic protocols add 2–5× overhead per round and increase coordinator complexity; without them, a compromised server can reconstruct individual updates, creating a privacy risk.
- Differential privacy vs model accuracy: stronger privacy guarantees (lower ε) inject more noise and reduce model accuracy; teams must choose a privacy-accuracy operating point based on regulatory requirements and data sensitivity.
- Client sampling breadth vs round speed: sampling more clients per round improves update quality but increases round latency and bandwidth; small samples are faster but noisier.

## 4. Operational Excellence

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
