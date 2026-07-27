---
title: "AI/ML Workshop"
description: "ML workflows with a full-stack dashboard: PyTorch, scikit-learn, NumPy, and real-time SSE visualization."
summary: "A hands-on ML workshop that grew from a CLI script runner into a full-stack application: a FastAPI async backend dispatches training jobs to a thread pool, intercepts matplotlib output in-memory, and streams live telemetry to a Next.js dashboard via Server-Sent Events, while still supporting headless CLI experimentation with uv."
tags: [concurrency, machine-learning, privacy]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/ai-ml-workshop"
draft: false
date: "2026-02-16T10:22:20-08:00"
---

## Context & Motivation

**Context:** A hands-on collection focused on core ML workflows: PyTorch model development, Hugging Face model/dataset tooling, NumPy implementations for fundamentals, and scikit-learn experiments for classical algorithms. RAG/agents and media preprocessing are covered in auxiliary repos (`ragchain`, `vidicant`, `xcode-trial`).

**Motivation:** It was difficult finding one place to learn and experiment with the full ML workflow—from data loading to model training, evaluation, and optimization—especially with a local-first approach that emphasizes reproducibility and hardware-aware benchmarking (MPS vs. CPU). Many resources are either too high-level (abstracting away training details) or too fragmented (focusing on one aspect like Hugging Face without the full pipeline). Additionally, ensuring experiments are reproducible and comparable across hardware adds complexity.

## The Local Implementation

- **CLI Workshop Core:** The `workshop` CLI (orchestrated via `uv run workshop`) drives PyTorch examples (training, transfer learning, PEFT/LoRA fine-tuning), Hugging Face integrations (datasets, tokenizers, model hubs), NumPy-from-scratch exercises (backpropagation, Q-learning, attention, transformer block), and scikit-learn algorithm demos. Auxiliary repos (`ragchain`, `mailprune`, `vidicant`, `xcode-trial`) cover RAG, agents, and media pipelines.
- **Full-Stack Dashboard Architecture:** The workshop now ships a real-time web dashboard: a **FastAPI backend** (`uv run workshop server`) dispatches training jobs to a `ThreadPoolExecutor`, streams live progress via **Server-Sent Events (SSE)**, and serves an API that a **Next.js 15 frontend** (`npm run dev --prefix frontend`) consumes to display interactive hyperparameter controls, live metrics charts (Recharts), and step timelines—all without a page reload.
- **Pydantic-Driven Config Forms:** Each task exposes its hyperparameters as a Pydantic model. The frontend fetches the JSON schema (`GET /tasks/{module}/{task}/schema`) and auto-generates sliders and numeric inputs in `ConfigForm.tsx`, keeping backend and frontend in sync without duplicated type definitions.
- **Matplotlib Monkey-Patching:** To capture plots from background training threads without writing to disk, `plt.savefig` is intercepted at startup. The patch checks thread-local storage for the active `job_id`, captures figure bytes in-memory via `io.BytesIO`, and stores them in a per-job registry—then exposes them at `/plots/{job_id}/{filename}`. A dynamic whitelist (built at startup from registered task plot names) guards against path-traversal attacks.
- **Cooperative Cancellation & Thread-Local Console Capture:** Background threads poll a cancellation flag via `HTTPProgressHook`, so users can abort a misconfigured run gracefully. Standard output and `tqdm` progress bars are captured per-job using a `ThreadLocalStream` wrapper over `sys.stdout`/`sys.stderr`, preventing concurrent training runs from mixing their console output.
- **Bottleneck:** Variation in hardware (MPS vs. CPU) and resource limits for transformer-scale experiments still create noisy comparisons. Large-model fine-tuning may be infeasible without PEFT techniques or smaller model checkpoints.

## Comparison to Industry Standards

- **My Project:** A local-first educational platform with a full-stack dashboard for interactive, real-time ML experimentation. The async FastAPI + SSE design deliberately mimics the telemetry patterns used in production job schedulers at reduced scale.
- **Industry:** Production ML stacks use MLflow/Weights & Biases for experiment tracking, Kubernetes for distributed training infra, and managed artifact registries. Jupyter remains the standard for ad-hoc exploration.
- **vs. Jupyter Notebooks:** The dashboard's async `ThreadPoolExecutor` dispatch keeps the event loop free for concurrent requests, unlike Jupyter's blocking-per-cell kernel model. SSE-streamed live metrics replace Jupyter's post-hoc static chart rendering. Cooperative cancellation (flag polling) avoids the hard kernel-interrupt that loses in-memory state. The tradeoff: Jupyter's per-cell exploration and variable inspection are more flexible for pure research.
- **Gap Analysis:** Closing the gap with production MLOps requires CI-driven reproducible runs, artifact signing, distributed training hooks, and standardized evaluation suites for RAG and agent behaviors.

## Risks & Mitigations

- **Non-reproducible environments:** Pin deps with a `uv.lock` file; provide a minimal devcontainer for CI. Frontend lockfile (`package-lock.json`) is committed for deterministic node installs.
- **Large model resource constraints:** Document fallbacks (smaller models, LoRA/PEFT), and automate profiling to detect OOM early. MPS/CPU parity issues are noted in docs.
- **Thread safety in the backend:** Monkey-patching `plt.savefig` and `sys.stdout` with thread-local storage risks subtle bugs if libraries buffer output or matplotlib's global state is mutated. **Mitigation:** each job gets isolated thread-local context before dispatch; integration tests spin up concurrent job runs to catch cross-job output leakage.
- **SSE connection lifecycle:** Long-lived SSE connections can silently stall if the client disconnects mid-run without the server noticing. **Mitigation:** the backend's generator yields heartbeat events and detects `asyncio.CancelledError` on disconnect to terminate the associated background thread cleanly.
