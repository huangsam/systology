---
title: "Local LLM Inference"
description: "Hardware bottlenecks, KV cache sizing, memory allocation cliffs, and client payload dynamics for local model serving."
summary: "An empirical systems exploration of local LLM inference on unified memory architectures: profiling compute-bound prefill vs. memory-bound decode phases, analyzing KV cache retention during cancellation, measuring the 64K vs. 128K context cliff on Apple Silicon, and comparing client payload strategies."
tags: [caching, machine-learning, optimization, systems-programming]
categories: ["deep-dives"]
draft: false
date: "2026-08-14T08:18:07-07:00"
---

## Context & Motivation

**Context:** Modern AI-assisted software engineering increasingly relies on local-first language model runtimes. Workstation-grade Apple Silicon systems (e.g., M-series Max/Ultra SoCs) allow developers to host 70B+ and 120B+ parameter models directly on local hardware, powering terminal tooling, dotfile automation, shell instrumentation, and interactive agent loops.

**Motivation:** Running local LLMs provides zero-marginal-cost inference, offline capability, and total confidentiality for proprietary codebases. However, local inference operates under strict physical hardware constraints that differ fundamentally from cloud datacenter clusters. Without multi-node GPU clusters, local serving is governed by the physics of single-bus memory bandwidth, Metal GPU wired memory ceilings, and prompt payload overheads. Understanding prefill vs. decode bottlenecks, KV cache eviction behaviors, and empirical memory pressure thresholds is critical for designing responsive, stable local AI workflows.

## The Local Implementation

### The Two Phases of LLM Inference

Every autoregressive Large Language Model request consists of two distinct operational phases with fundamentally different hardware bottlenecks:

| Phase | Bottleneck | Core Operation |
|---|---|---|
| **Prefill** | **Compute** | Parallel batch prompt matrix multiplication to populate KV cache. |
| **Decode** | **Memory** | Sequential autoregressive token generation attending across KV cache. |

{{< mermaid >}}
graph LR
    Prompt[Prompt Input] --> Prefill["Prefill<br>Compute-Bound Ops"]
    Prefill --> Cache[KV Cache in VRAM]
    Cache --> Decode["Decode<br>Bandwidth-Bound Sweep"]
    Decode --> Token[Next Token]
    Token -.->|Feedback Loop| Decode
{{< /mermaid >}}

### Cancellation Dynamics: Prefill vs. Generation

When an inference turn is canceled or interrupted, the lifecycle state of the KV cache determines whether computed activations are preserved for subsequent turns:

#### Canceling During Generation (Text Output)
* **Execution State**: 100% of the input prompt has already been evaluated and stored in the KV cache within VRAM.
* **Effect of Cancel**: Token generation halts immediately, but the prompt prefix activations remain intact in memory.
* **Subsequent Turn**: The server retains the prompt prefix. The next turn achieves an immediate **100% cache hit** and begins generating output instantly without re-evaluating the prompt.

#### Canceling During Prefill (Prompt Ingestion)
* **Execution State**: The model is actively computing KV activations in chunks (e.g., batches of 512 tokens).
* **Effect of Cancel**: The inference runtime halts execution and evicts or rolls back incomplete sequence blocks (`memory_seq_rm`).
* **Subsequent Turn**: Only tokens finalized prior to the cancellation point exist in the cache. The runtime suffers a **cache miss** for the remainder of the context and must evaluate all remaining tokens from scratch.

### Dense vs. MoE Architecture Dynamics on Unified Memory

On single-memory-bus systems (such as Apple Silicon Unified Memory), autoregressive token generation speed is strictly bounded by memory bandwidth:

```text
Generation Speed (tokens/sec) = GPU Memory Bandwidth (GB/s) / Active Model Size in VRAM (GB)
```

* **Dense (120B+)** — `mistral-medium-3.5:128b`, `qwen3.5:122b`
    * *Footprint:* 122B – 128B active parameters (~76.5 – 81 GB VRAM)
    * *Throughput:* ~3.5 – 6.5 tokens/sec (M-Max ~800 GB/s)
    * *Best Fit:* Deep architectural refactoring, zero-hallucination audits, complex logic.
* **Dense / Quantized 70B+** — `deepseek-r1:70b`, `qwen3-coder-next:q4_K_M`
    * *Footprint:* 70B+ parameters (~42 – 51 GB VRAM)
    * *Throughput:* ~25 – 54 tokens/sec
    * *Best Fit:* Balanced sweet spot of high generation speed, reasoning depth, and memory headroom.
* **Optimized MLX / MoE** — `qwen3.6:35b-mlx`, `gemma4:31b-mlx`
    * *Footprint:* Parameter-efficient MLX runtime (~18 – 21 GB VRAM)
    * *Throughput:* ~60 – 90+ tokens/sec
    * *Best Fit:* High-throughput interactive pair programming, fast shell completions, responsive chat.

### macOS Metal GPU Allocation Limits & KV Cache Sizing

Apple Silicon Unified Memory operates under operating system thresholds managed by the Metal graphics driver and XNU kernel:

{{< mermaid >}}
graph TD
    Unified["128 GB Unified Memory"] --> GPU["Metal GPU Wired Zone<br>~96 GB Limit"]
    Unified --> Host["macOS Host Zone<br>~32 GB Headroom"]
    GPU --> Weights["Model Weights<br>~76.5 GB"]
    GPU --> KV["64K KV Cache<br>~19.8 GB"]
    Host --> OS["System & Daemons"]
    Host --> Apps["IDEs & User Apps"]
{{< /mermaid >}}

#### KV Cache Memory Footprint (Q8_0 Quantization):
* **16K Context (`16,384` tokens)**: **~4.9 GB VRAM** (Ideal for 36 GB)
* **32K Context (`32,768` tokens)**: **~9.9 GB VRAM**
* **64K Context (`65,536` tokens)**: **~19.8 GB VRAM** (Ideal for 128 GB)
* **131K Context (`131,072` tokens)**: **~39.7 GB VRAM**

#### The 64K vs. 128K Empirical Cliff:
* **At 64K Context**: Dense 128B weights (76.5 GB) + 64K KV Cache (19.8 GB) = **~96.3 GB**.
    * Total process memory: ~107 GB (~101 GB Wired Memory).
    * Memory pressure remains **solid green** with ~5.6 GB of unswapped system headroom. 100% of model layers execute inside Metal GPU VRAM.
* **At 128K Context**: Total demand reaches 76.5 GB + 39.7 GB = **116.2 GB for the runtime process alone**, pushing aggregate system demand over **135 GB**.
    * macOS spills 15+ model layers into CPU System RAM and Swap.
    * Prefill throughput collapses from **~140 tokens/sec down to ~10 tokens/sec** due to swap paging and memory bus thrashing.

### Client Architecture & Prompt Payload Dynamics

The choice of client interface drastically alters prompt payload volume and prefill latency:

* **IDE Auto-Dump** *(Open tabs, full file tree, git logs, linter states)*
    * *Turn #1 (~26k tokens):* **~2.5 to 7.0 minutes** prefill on Dense 128B; saturates memory bus and easily evicts prefix caches.
* **Explicit Context CLI** *(System prompt + explicit `@file` references)*
    * *Turn #1 (~500 tokens):* **~6.5 seconds** prefill on Dense 128B.
    * *Turn #2+ Delta (<50 tokens):* **<200 milliseconds** (`f_sim_best = 1.000`) via runtime Longest Common Prefix (LCP) caching (`OLLAMA_KEEP_ALIVE=30m`).

### The 4-Tier Local Model Arsenal

On workstation and laptop hardware, local models categorize into four operational tiers:

* **Tier 1: Heavyweight Architects (120B+)**
    * *Models:* `mistral-medium-3.5:128b` (80 GB), `qwen3.5:122b` (81 GB)
    * *Performance Profile:* Dense / ~3.5 – 6.5 tokens/sec / 64K VRAM
    * *Ideal Use Case:* Multi-file refactoring, security audits, and complex architectural reasoning.
* **Tier 2: Flagship Workhorses & Reasoning (70B+)**
    * *Models:* `deepseek-r1:70b` (42 GB), `qwen3-coder-next:q4_K_M` (51 GB)
    * *Performance Profile:* 70B+ RL / Q4 / ~25 – 54 tokens/sec
    * *Ideal Use Case:* Core engineering, logic puzzles, test generation, and pair-programming.
* **Tier 3: Mid-Weight Speedsters (26B – 35B)**
    * *Models:* `qwen3.6:35b-mlx` (21 GB), `gemma4:31b-mlx` (18 GB)
    * *Performance Profile:* MLX / ~60 – 90+ tokens/sec / ~18 – 21 GB VRAM
    * *Ideal Use Case:* Rapid completions, interactive CLI loops, and sweet spot for 36GB–48GB MacBooks.
* **Tier 4: Ultra-Lightweight Mobility (Sub-14B)**
    * *Models:* `gemma4:12b-mlx` (7.7 GB), `qwen3.5:9b-mlx` (8.9 GB)
    * *Performance Profile:* <10 GB VRAM / ~80 – 120+ tokens/sec / low power draw
    * *Ideal Use Case:* Fast command lookups and commit message drafting on base MacBooks.

## Comparison to Industry Standards

| Feature | Enterprise Datacenter | Local Workstation (M5 Max) |
|---|---|---|
| **Compute Fabric** | Thousands of H100/H200/Blackwell GPUs | Single SoC Apple Silicon M-Max/Ultra |
| **Interconnects** | NVLink 900 GB/s per GPU, NVL72 130 TB/s Backplane | On-die Unified Memory Bus (~800 GB/s) |
| **Context Capacity** | 500,000 to 2,000,000+ Tokens | 32,768 to 65,536 Tokens (VRAM-Locked) |
| **Mitigation Tech** | Disaggregated Prefill/Decode (RDMA), RadixAttention | In-Memory LCP Prefix Cache, Explicit Context Clients |
| **Best-Fit Workloads** | Multi-service incident tracing, massive log correlation, 1M+ token repo ingests. | Zero-cost daily coding, proprietary IP development, offline operation, instant sub-second local iterations. |
| **Cost & Privacy** | Usage-based API pricing, third-party network egress. | **$0 / month operating cost**, 100% private and air-gapped. |

## Risks & Mitigations

- **Memory Cliff Thrashing (OS Swap Spillover):** When process memory demand exceeds Metal GPU wired memory limits (~98 GB on 128 GB hardware), macOS spills layers into swap, collapsing prefill speed from 140 t/s to 10 t/s.
    - *Mitigation:* Hard-cap context windows to safe limits (`65536` for 128 GB setups, `16384` for 36 GB setups) and monitor wired memory allocations before expanding context depth.
- **Premature Prefill Interruption:** Canceling a request during prompt ingestion invalidates the unfinalized sequence chunk, forfeiting the KV cache for the next turn.
    - *Mitigation:* Allow the prefill phase to complete before canceling or re-prompting; canceling immediately as generation begins retains the full prefix in the cache.
- **Prefix Cache Busting:** Dynamic timestamps, non-deterministic system prompts, or fluctuating tool definitions at the start of prompts prevent LCP cache hits.
    - *Mitigation:* Structure prompts with static, deterministic prefixes (system prompt → tool definitions → workspace metadata) at the top of every turn, placing dynamic inputs strictly at the end.
- **Client Payload Bloat:** Automated editor extensions dumping uncompressed file trees, open tabs, and git logs inflate prompt sizes beyond 25,000 tokens, degrading initial response times.
    - *Mitigation:* Favor targeted CLI interfaces or explicit reference mechanisms (`@file`, bounded git diffs) that restrict Turn #1 payloads to relevant context.
