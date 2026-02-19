---
title: "AI/ML Workshop"
description: "AI/ML workshops on model training and evaluation."
summary: "Practical, reproducible ML examples (PyTorch/Hugging Face/NumPy) with MPS-aware benchmarks and experiment hygiene for local hardware."
tags: ["ml", "privacy"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/ai-ml-workshop"
draft: false
---

## Context & Motivation

**Context:** A hands-on collection focused on core ML workflows: PyTorch model development, Hugging Face model/dataset tooling, NumPy implementations for fundamentals, and scikit-learn experiments for classical algorithms. RAG/agents and media preprocessing are covered in auxiliary repos (`ragchain`, `vidicant`, `xcode-trial`).

**Motivation:** It was difficult finding one place to learn and experiment with the full ML workflow—from data loading to model training, evaluation, and optimization—especially with a local-first approach that emphasizes reproducibility and hardware-aware benchmarking (MPS vs. CPU). Many resources are either too high-level (abstracting away training details) or too fragmented (focusing on one aspect like Hugging Face without the full pipeline). Additionally, ensuring experiments are reproducible and comparable across hardware adds complexity.

## The Local Implementation

- **Current Logic:** A CLI-driven workshop centers on PyTorch examples (training, transfer learning, MPS optimization), Hugging Face integrations (datasets, tokenizers, model hubs), NumPy-from-scratch exercises for fundamentals, and scikit-learn algorithm demos. Notebooks, scripts, and `uv` tasks orchestrate experiments. RAG/agent demos and media feature extraction are maintained in `ragchain`, `mailprune`, `vidicant`, and `xcode-trial` respectively.
- **Bottleneck:** Variation in hardware (MPS vs. CPU), inconsistent dependency pinning, and resource limits for transformer-scale experiments create noisy comparisons; large-model fine-tuning may be infeasible without PEFT techniques or smaller models.

## Comparison to Industry Standards

- **My Project:** Local-first, educational experiments with an emphasis on explainability and small-scale reproducibility.
- **Industry:** Production ML stacks use strict MLOps, artifact registries, and scalable training infra (Kubernetes, distributed TPU/GPU).
- **Gap Analysis:** To move from workshop to production rigour requires CI-driven reproducible runs, artifact signing, and standardized evaluation suites for RAG and agent behaviors.

## Risks & Mitigations

- **Non-reproducible environments:** pin deps, provide `uv` lockfile and minimal docker/devcontainer for CI.
- **Large model resource constraints:** document fallbacks (smaller models, LoRA), and automate profiling to detect OOM early.
