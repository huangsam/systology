---
title: "Scalable Model Serving Infrastructure"
description: "Real-time ML inference at scale"
summary: "Infrastructure for real-time ML inference with model versioning, autoscaling, and resource-aware fallbacks."
tags: ["ml","monitoring"]
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Design an infrastructure to serve machine learning models for real-time inference, supporting high throughput and low latency while providing resource-aware fallbacks. The system must ensure deterministic results, handle model versioning, and scale horizontally to accommodate varying loads without compromising availability or performance.

- **Functional Requirements:** Serve ML models for inference.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 10k inferences/sec.
    - **Availability:** 99.9%.
    - **Consistency:** Deterministic results.
    - **Latency Targets:** P99 < 200ms.

## 2. High-Level Architecture

{{< mermaid >}}
graph LR
  Client[API Client] --> Gateway[API Gateway]
  Gateway --> Router[Model Router]
  Router --> ServerA[Model Server A - v2 canary]
  Router --> ServerB[Model Server B - v1 stable]
  ServerA --> GPU[(GPU Pool)]
  ServerB --> GPU
  Registry[(Model Registry)] --> ServerA
  Registry --> ServerB
  Router -.->|fallback| Fallback[Lightweight Fallback Model]
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

### Deep Dive

- **Model registry and versioning:** store every trained model as an immutable, versioned artifact (ONNX, TorchScript, SavedModel) in an object store with metadata (training run, dataset hash, metrics). The registry tracks which version is live, canary, and shadow, enabling instant rollback to any previous version.
- **Serving runtime:** use a high-performance inference server (Triton, TorchServe, TF Serving) that loads models on startup and serves predictions via gRPC/REST. Support multiple model formats and hardware backends (CPU, GPU, TPU) with a unified API.
- **Request batching:** aggregate incoming requests into micro-batches (e.g., 8–32 inputs) with a short wait window (5–10 ms). Batching amortises GPU kernel launch overhead and increases throughput by 3–10× with only marginal latency increase. Use adaptive batch sizing based on current load.
- **GPU scheduling and resource management:** assign models to GPU instances based on memory requirements and latency SLOs. Use model-level resource quotas and support GPU sharing (MPS or time-slicing) for smaller models. Place latency-sensitive models on dedicated GPUs; batch/offline models can share.
- **Canary and blue-green rollouts:** deploy new model versions as canary (5–10% traffic), compare accuracy and latency metrics against the stable version in real-time, and auto-promote or rollback. Use feature flags or header-based routing so that specific users or test traffic can be sent to the canary explicitly.
- **Fallback and degradation:** maintain a lightweight fallback model (e.g., logistic regression, cached predictions, or a smaller distilled model) that activates when the primary model is unhealthy or latency exceeds the SLO. The fallback trades accuracy for availability and ensures the API never returns errors to end users.
- **Pre- and post-processing:** run feature extraction, normalisation, and output formatting in the serving pipeline as vectorised transforms. Keep preprocessing deterministic and version it alongside the model to avoid training-serving skew.

### Tradeoffs

- Batching vs latency: larger batches improve throughput and GPU utilisation but increase tail latency for requests that arrive at the start of a batch window; systems must tune batch size and wait time per SLO tier.
- GPU sharing vs isolation: sharing GPUs across models maximises utilisation but introduces noisy-neighbour effects; dedicated GPUs guarantee latency but leave capacity idle during low traffic.
- Rich serving framework vs custom server: frameworks like Triton provide out-of-the-box batching, multi-model, and multi-backend support but add abstraction layers; custom servers offer maximum control but require significant engineering investment.

## 4. Operational Excellence

### SLIs / SLOs
- SLO: P99 inference latency < 200 ms for all production models.
- SLO: 99.9% availability of the inference API (including fallback responses).
- SLIs: inference_latency_p99, inference_error_rate, model_load_time, gpu_utilisation, batch_fill_ratio, canary_accuracy_delta.

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
