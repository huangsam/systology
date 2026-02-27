---
title: "Model Serving & Inference"
description: "Reliable, low-latency ML inference in production."
summary: "Principles for production ML inference: immutable model registries, micro-batching, canary rollouts, fallback degradation, and GPU management."
tags: ["ml", "monitoring"]
categories: ["principles"]
draft: false
---

## Immutable Model Registry

Treat model versions as immutable artifacts—never overwrite a version in place. Store binaries, runtime environments, and a metadata manifest together so any deployed version can be reproduced or rolled back instantly.

A model registry is a content-addressable store where each entry maps a version identifier to a frozen tuple: `(weights_uri, runtime_container_tag, preprocessing_config, training_run_id)`. The `is_live` flag is the only mutable field—everything else is sealed at publish time. When you need to revert a bad rollout, the previous version already exists and is fully self-contained; there's nothing to rebuild. Without immutability, the "working version" can change underneath you even without a new deployment.

**Anti-pattern — Overwriting `latest`:** Pushing new weights to the same `model_latest.pt` path in object storage. Any service that cached the old file now silently uses stale weights, and there's no way to go back if the new version is broken. Use content-addressed versioning (`model_v42_sha256abc.pt`) and never overwrite past versions.

## Micro-batching for GPU Throughput

Aggregate incoming inference requests over a short time window (5–10 ms) before dispatching a single batched kernel call. This amortizes GPU launch overhead across many requests and dramatically improves throughput without meaningfully impacting tail latency.

GPU kernel launches have fixed overhead (~50–200 μs) regardless of batch size. A single request processed alone wastes most of that overhead budget. Batching 32 requests together on the same kernel launch increases throughput by 20–30× while adding only the batching window to latency. Tune the window duration and max batch size per model: latency-sensitive models need shorter windows; throughput-oriented models can tolerate larger ones.

**Anti-pattern — Request-per-Kernel:** Dispatching one GPU kernel per incoming request. At 1,000 RPS, you spend more time on kernel launches than actual computation. Micro-batching is the single highest-leverage optimization for GPU inference throughput.

## Canary Rollouts with Metrics-Driven Promotion

Route a small fraction of live traffic (5–10%) to a new model version before promoting it fully. Automated promotion decisions should compare latency and accuracy metrics between the canary and stable pools over a validation window.

Canaries work best when you define promotion criteria upfront: "promote if P99 latency is within 10% of baseline and accuracy delta on shadow labels is less than 0.5% for 4 hours." Automated rollback triggers—fires if error rate or latency exceeds thresholds—prevent bad canaries from causing extended incidents. Treat the canary decision as a pipeline stage, not a manual review.

{{< mermaid >}}
graph TD
    Client --> Gateway
    Gateway --> Router[Router\nCanary Split]
    Router -->|5-10% canary| Canary[Canary Pool\nNew Version]
    Router -->|90-95% stable| Stable[Stable Pool\nCurrent Version]
    Canary --> Gate{Metrics Gate}
    Gate -->|pass| Promote[Promote to 100%]
    Gate -->|fail| Rollback[Rollback]
    Stable -.->|on error| Fallback[Fallback Model]
    Canary -.->|on error| Fallback
{{< /mermaid >}}

See the [ML Experiments]({{< ref "/principles/ml-experiments" >}}) principles for guidance on reproducible model evaluation and artifact versioning that precedes a canary launch.

**Anti-pattern — Big-bang Cutover:** Switching 100% of traffic to a new model version instantaneously. If the new version has a regression, every user is affected immediately. A 5% canary limits blast radius and gives you real-world signal before full commitment.

## Fallback & Graceful Degradation

Always have a fallback model that activates automatically on latency spikes or primary failures. A distilled, smaller version of the primary model provides degraded-but-useful inference while preserving SLA compliance.

Design the fallback to be stateless and fast: a distilled or quantized model loaded permanently in memory, not fetched on demand when things are already broken. Define activation triggers: "if P99 latency exceeds 300 ms for 30 consecutive seconds, reroute to fallback." Cached predictions are another valid fallback for workloads with low input cardinality. The goal is: the user gets a result, even if it's less accurate.

**Anti-pattern — No Fallback Path:** Returning errors to users when the primary model is slow or unavailable. For most inference workloads, a degraded response is vastly preferable to an error. Design the "what if the GPU pool is saturated?" path before you need it.

## GPU Resource Management

Choose between GPU sharing and isolation based on latency requirements. Share GPUs across small models to maximize utilization; isolate GPUs for latency-critical paths or large models to eliminate noisy-neighbor effects.

Use NVIDIA MPS (Multi-Process Service) to share a single GPU across multiple small models with low per-request memory needs—this keeps GPU utilization high. For models with strict P99 SLOs, dedicate a GPU to avoid contention from co-located workloads. Assign GPUs based on model memory footprint at registration time, not at request time, to eliminate scheduling jitter.

**Anti-pattern — One-size-fits-all Sharing:** Co-locating a batch-heavy model and a latency-critical model on the same GPU. The batch job saturates GPU memory and compute, causing the latency-sensitive model to miss its SLO. Segment by latency profile at the infrastructure level.

## Eliminate Training-Serving Skew

Version preprocessing transforms alongside model weights and run them inside the serving pipeline. Skew between training-time and serving-time feature computation is the most common cause of silent accuracy degradation.

Training-serving skew occurs when the feature vector seen at inference differs from the one the model was trained on—even if the difference is subtle (different normalization constants, different tokenizer version, missing feature imputation). The fix: treat the preprocessing pipeline as part of the model artifact. Bundle it into the model package and test it with the same inputs used during training evaluation.

See the [Data Pipelines]({{< ref "/principles/data-pipelines" >}}) principles for guidance on schema evolution and idempotent feature generation that feeds into the serving pipeline.

**Anti-pattern — Separate Preprocessing Repos:** Maintaining training preprocessing in a ML research repo and serving preprocessing in an application repo with no enforced sync. Over time they diverge. The model performs great on offline benchmarks and inexplicably worse in production. Colocate and version them together.

## Observability for Inference

Log input feature distributions, output confidence scores, and hardware metrics alongside standard latency/error metrics. Distribution drift in inputs is an early warning signal for accuracy degradation before it shows up in labels.

Emit: `inference_latency_p99`, `batch_fill_ratio`, `gpu_utilization`, `model_version`, and sampled `(input_hash, output_distribution)` for each serving replica. Monitor `canary_accuracy_delta` during rollouts. Alert on GPU memory pressure before it causes OOM evictions. For high-cardinality input spaces, sample at 1–5% to manage storage costs.

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for SLO construction and alerting patterns that apply directly to inference services.

## Decision Framework

Choose your model serving configuration based on the primary constraint for your workload:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Lowest P99 Latency** | Dedicated GPU + no sharing | Eliminates noisy-neighbor contention; predictable tail latency. |
| **Maximum Throughput** | Micro-batching + shared GPU (MPS) | Amortizes kernel launch cost; maximizes GPU utilization. |
| **Safe Rollout** | Canary (5–10%) + metrics gate | Limits blast radius; automated promotion prevents human error. |
| **Graceful Degradation** | Distilled fallback model (always warm) | Preserves SLA compliance during primary failure; loaded in memory, not fetched on demand. |
| **Cost Efficiency** | Multi-model GPU sharing (MPS) | Keeps utilization high for many small models; acceptable when latency SLAs are loose. |
| **Accuracy Safety Net** | Shadow traffic + offline eval before canary | Catches regressions on real inputs before any user sees the new model. |

**Decision Heuristic:** "Choose **dedicated GPU isolation** for latency-critical paths and **micro-batching with shared GPUs** for throughput-oriented workloads. Never sacrifice the fallback path—design it before you need it."
