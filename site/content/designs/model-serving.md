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

A Gateway forwards client requests to a Router that splits traffic between a small Canary pool and a large Stable production pool. Both pools dynamically execute versioned models from a Registry on dedicated GPUs. Errors or latency spikes automatically reroute to a lightweight Fallback Model to preserve availability.

## Data Design

An immutable Model Registry stores versioned binaries and runtimes, enabling instant rollbacks. Volatile Inference Logs capture real-time distributions, confidence scores, and hardware metrics to drive automated promotion or fallback decisions.

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

- **Serving Runtime:** High-performance inference servers (Triton/TorchServe) provide unified gRPC/REST APIs across varied GPU backends.

- **Micro-batching:** Aggregating requests within a 5-10ms window amortizes kernel launch overhead, dramatically increasing GPU throughput.

- **Resource Management:** GPUs are assigned based on memory needs, using MPS for sharing small models and isolating latency-critical traffic.

- **Canary Rollouts:** Routing 5-10% of traffic to new versions enables automated, metrics-driven promotion or rollback.

- **Fallback & Degradation:** Distilled fallback models or cached predictions automatically activate during latency spikes or primary failures to strictly meet SLOs.

- **Preprocessing:** Vectorized transforms for feature normalization run inside the serving pipeline, versioned alongside the model to eliminate training-serving skew.

### Trade-offs

- **Batch Size vs. Latency:** Larger batches maximize throughput but increase tail latency (P99); requires per-model tuning to balance cost against responsiveness.

- **GPU Sharing vs. Isolation:** Sharing maximizes cost-efficiency but risks noisy-neighbor effects; Isolation guarantees performance but leaves capacity idle during troughs.

## Operational Excellence

### SLIs / SLOs

- SLO: P99 inference latency < 200 ms for all production models.
- SLO: 99.9% availability of the inference API (including fallback responses).
- SLIs: inference_latency_p99, inference_error_rate, model_load_time, gpu_utilization, batch_fill_ratio, canary_accuracy_delta.

### Reliability & Resiliency

- **Load-Test**: Validate 2x peak QPS for each new version before canary.
- **Shadow**: Run offline baseline comparisons via production traffic mirrors.
- **Chaos**: Kill GPU nodes and verify 30s fallback/reschedule timing.
