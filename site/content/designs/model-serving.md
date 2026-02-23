---
title: "Scalable Model Serving Inference"
description: "Real-time ML inference at scale."
summary: "Infrastructure for real-time ML inference with model versioning, autoscaling, and resource-aware fallbacks."
tags: ["ml", "monitoring"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design an infrastructure to serve machine learning models for real-time inference, supporting high throughput and low latency while providing resource-aware fallbacks. The system must ensure deterministic results, handle model versioning, and scale horizontally to accommodate varying loads without compromising availability or performance.

### Functional Requirements

- Serve trained ML models for inference requests.
- Support model versioning and canary rollouts.
- Provide fallback models on errors or resource constraints.

### Non-Functional Requirements

- **Scale:** 10k inferences/sec; multi-replica horizontal scaling.
- **Availability:** 99.9% inference availability.
- **Consistency:** Deterministic results for same input across replicas.
- **Latency:** P99 < 200ms end-to-end inference.
- **Workload Profile:**
    - Read:Write ratio: ~99:1
    - Peak throughput: 10k inferences/sec
    - Retention: last 10 model versions + 30-day metrics

## High-Level Architecture

{{< mermaid >}}
graph TD
    Client["Client<br/>(Inference Request)"]
    Gateway["Gateway<br/>(Load Balance)"]
    Router["Router<br/>(Canary Decision)"]
    ServerA["Server A<br/>(Canary ~5-10%)"]
    ServerB["Server B<br/>(Stable ~90-95%)"]
    GPUA["GPU Pool A"]
    GPUB["GPU Pool B"]
    Registry["Model Registry<br/>(Versions)"]
    Fallback["Fallback Model"]
    Client --> Gateway
    Gateway --> Router
    Router -->|canary traffic| ServerA
    Router -->|production traffic| ServerB
    ServerA --> GPUA
    ServerB --> GPUB
    ServerA -.->|load| Registry
    ServerB -.->|load| Registry
    ServerA -.->|on error| Fallback
    ServerB -.->|on error| Fallback
{{< /mermaid >}}

## Data Design

### Model Registry (Object Store + Metadata)
| Registry Field | Type | Description | Immutable |
| :--- | :--- | :--- | :--- |
| `model_uri` | S3 URI | Path to TorchScript/ONNX binary. | Yes |
| `runtime_env` | Container Tag | Python/C++ environment version. | Yes |
| `is_live` | Boolean | Global flag for production routing. | No |
| `fallback_id` | Version ID | Directs to smaller model if latency spikes. | No |

### Inference Logs (Sampled / Streaming)
| Dimension | Description | Retention |
| :--- | :--- | :--- |
| **Input Features** | Vector/Tensor used for prediction. | 14 days |
| **Probability** | Softmax/Confidence score from head. | 14 days |
| **Hardware Metrics**| GPU Mem/Util during the kernel call. | 30 days |

## Deep Dive & Trade-offs

### Deep Dive

- **Model Registry:** Immutable, versioned storage for ONNX/TorchScript artifacts. Metadata tracks training runs and metrics, enabling instant, safe rollbacks.

- **Serving Runtime:** High-performance inference servers (Triton/TorchServe) support gRPC/REST. Unified APIs allow serving multiple formats across CPU, GPU, and TPU backends.

- **Micro-batching:** Aggregates requests (8–32 inputs) within a 5–10ms window. Dramatically increases GPU throughput by amortizing kernel launch overhead.

- **Resource Management:** Assigns models to GPU pools based on memory needs. Uses MPS (sharing) for small models and dedicated instances for latency-critical traffic.

- **Canary Rollouts:** Deploys new versions to 5–10% of traffic. Real-time accuracy/latency comparisons against baseline automate promotion or rollback decisions.

- **Fallback & Degradation:** Activates distilled models or cached predictions when primaries fail or exceed SLOs. Ensures consistent API availability despite backend issues.

- **Preprocessing:** Runs feature normalization and formatting as vectorized transforms in the serving pipeline. Versioned with the model to eliminate training-serving skew.

### Trade-offs

- **Batch Size vs. Latency:** Larger batches maximize throughput but increase tail latency (P99); requires per-model tuning to balance cost against responsiveness.

- **GPU Sharing vs. Isolation:** Sharing maximizes cost-efficiency but risks noisy-neighbor effects; Isolation guarantees performance but leaves capacity idle during troughs.

## Operational Excellence

### SLIs / SLOs
- SLO: P99 inference latency < 200 ms for all production models.
- SLO: 99.9% availability of the inference API (including fallback responses).
- SLIs: inference_latency_p99, inference_error_rate, model_load_time, gpu_utilization, batch_fill_ratio, canary_accuracy_delta.

### Monitoring & Alerts (examples)

Alerts:

- `inference_latency_p99 > 180ms` for 5m
    - Severity: P2 (approaching SLO; investigate GPU contention or model regression).
- `inference_error_rate > 0.5%` (5m)
    - Severity: P1 (model health issue; check logs and consider rollback or fallback activation).
- `canary_accuracy < baseline - 2%` for 15m
    - Severity: P1 (canary model underperforming; auto-rollback to stable version).

### Testing & Reliability
- Load-test each new model version at 2× peak QPS before canary rollout to validate latency and throughput.
- Run shadow-mode evaluation: send production traffic to the new model without serving its results, and compare metrics offline.
- Chaos-test GPU node failures; verify that the orchestrator reschedules model servers and that the fallback activates within 30 seconds.

### Backups & Data Retention
- All model artifacts are immutable in the registry; retain at least the last 10 versions for instant rollback.
- Store inference logs (request/response pairs, sampled) for 14 days for debugging and model improvement.
- Archive model evaluation metrics and A/B test results indefinitely for long-term model quality tracking.
