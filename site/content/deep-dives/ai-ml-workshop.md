---
title: "AI/ML Workshop"
description: "AI/ML workshops on model training and evaluation."
summary: "Practical, reproducible ML examples (PyTorch/Hugging Face/NumPy) with MPS-aware benchmarks and experiment hygiene for local hardware."
tags: ["experiments", "ml", "ml-ops", "privacy", "reproducibility"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/ai-ml-workshop"
draft: false
---

## Context — Problem — Solution

**Context:** A hands-on collection focused on core ML workflows: PyTorch model development, Hugging Face model/dataset tooling, NumPy implementations for fundamentals, and scikit-learn experiments for classical algorithms. RAG/agents and media preprocessing are covered in auxiliary repos (`ragchain`, `mailprune`, `vidicant`, `xcode-trial`).

**Problem:** Reproducible experimentation and fair comparison of models is hindered by environment drift, heterogeneous hardware (MPS vs. CPU), and limited local resources for larger Transformer workflows.

**Solution (high-level):** Emphasize reproducible, local-first experiments: pinned environments, MPS-aware benchmarking, deterministic datasets/seeded runs, and lightweight experiment tracking. Delegate RAG/agent and media-specific operational concerns to their respective projects.

## 1. The Local Implementation

- **Current Logic:** A CLI-driven workshop centers on PyTorch examples (training, transfer learning, MPS optimization), Hugging Face integrations (datasets, tokenizers, model hubs), NumPy-from-scratch exercises for fundamentals, and scikit-learn algorithm demos. Notebooks, scripts, and `uv` tasks orchestrate experiments. RAG/agent demos and media feature extraction are maintained in `ragchain`, `mailprune`, `vidicant`, and `xcode-trial` respectively.
- **Bottleneck:** Variation in hardware (MPS vs. CPU), inconsistent dependency pinning, and resource limits for transformer-scale experiments create noisy comparisons; large-model fine-tuning may be infeasible without PEFT techniques or smaller models.

## 2. Scaling Strategy

- **Vertical vs. Horizontal:** Use vertical tuning (mixed precision, batch-size scaling) to maximize local hardware. For larger datasets, offload to reproducible CI runners or cloud spot instances with the same pinned environment.
- **State Management:** Capture experiments with deterministic seeds, dataset checksums, and an artifact store (local FS or remote). Use a lightweight experiment-tracking dashboard (MLflow/simple TSV) for metrics.

## 3. Comparison to Industry Standards

- **My Project:** Local-first, educational experiments with an emphasis on explainability and small-scale reproducibility.
- **Industry:** Production ML stacks use strict MLOps, artifact registries, and scalable training infra (Kubernetes, distributed TPU/GPU).
- **Gap Analysis:** To move from workshop to production rigour requires CI-driven reproducible runs, artifact signing, and standardized evaluation suites for RAG and agent behaviors.

## 4. Experiments & Metrics

- **MPS speedups:** time/epoch and memory usage comparisons (MPS vs. CPU) across representative models and batch sizes.
- **PEFT efficiency:** parameter reduction, wall-clock fine-tune time, and downstream accuracy when using LoRA/PEFT vs. full fine-tune.
- **Classical ML comparisons:** consistent cross-validation benchmarks for scikit-learn examples (accuracy, AUC, training time) against baseline implementations.
- **NumPy correctness:** unit-tested implementations verifying gradients, PCA, and linear algebra results against known libraries.

## 5. Risks & Mitigations

- **Non-reproducible environments:** pin deps, provide `uv` lockfile and minimal docker/devcontainer for CI.
- **Large model resource constraints:** document fallbacks (smaller models, LoRA), and automate profiling to detect OOM early.

## Related Principles

- [ML Experiments](/principles/ml-experiments): Reproducibility, resource-aware design, deterministic evaluation, and lightweight MLOps.
- [Privacy & Agents](/principles/privacy-agents): Local-first defaults and data handling for sensitive datasets.
