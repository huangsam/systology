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

**Context:** Modern software engineering workflows are moving toward local-first AI runtimes. High-spec workstations, particularly Apple Silicon SoCs with unified memory, can now host 70B+ and 120B+ parameter models directly on device. This makes it practical to run terminal tools, shell helpers, and interactive coding agents entirely on local hardware.

**Motivation:** Running local models gives developers free inference, offline workflows, and total confidentiality for proprietary codebases. But local hardware behaves very differently from cloud clusters. Instead of distributing computation across a fleet of networked GPUs, local serving runs against a single unified memory bus. Performance is dictated by raw memory bandwidth, OS-level GPU memory limits, and prompt size. Understanding these physical boundaries (such as prefill vs. decode bottlenecks and memory cliffs) is essential for building fast, reliable local AI tools.

## The Local Implementation

> [!NOTE]
> **Test Environment:** All benchmarks and empirical measurements were conducted on an **Apple Silicon M5 Max workstation with 128 GB Unified Memory**, serving models via **Ollama** (leveraging the `llama.cpp` Metal GPU backend) alongside native **MLX** runtimes.

### The Two Phases of LLM Inference

Every Large Language Model request consists of two distinct phases with fundamentally different hardware bottlenecks:

| Phase | Bottleneck | Core Operation |
|---|---|---|
| **Prefill** | **Compute (FLOPs)** | Ingests and processes the input prompt in parallel to populate the working memory (KV cache). |
| **Decode** | **Memory Bandwidth** | Generates output tokens one by one, sweeping through the entire model and cache for every new token. |

{{< mermaid >}}
graph LR
    Prompt[Prompt Input] --> Prefill["Prefill<br>Compute-Bound Ops"]
    Prefill --> Cache[KV Cache in VRAM]
    Cache --> Decode["Decode<br>Bandwidth-Bound Sweep"]
    Decode --> Token[Next Token]
    Token -.->|Feedback Loop| Decode
{{< /mermaid >}}

### Cancellation Dynamics: Prefill vs. Generation

When you cancel an in-flight query, the lifecycle state of the KV cache determines whether computed work is preserved for your next turn:

#### Canceling During Generation (Text Output)
* **Execution State**: The model has already ingested the full prompt and stored its representations in VRAM.
* **Effect of Cancel**: Output generation stops immediately, but the prompt prefix remains intact in memory.
* **Subsequent Turn**: The runtime reuses the existing cache. Your next turn achieves an immediate **100% cache hit** and begins answering instantly without re-reading the prompt.

#### Canceling During Prefill (Prompt Ingestion)
* **Execution State**: The model is actively digesting the prompt in sequential batches (e.g., chunks of 512 tokens).
* **Effect of Cancel**: The runtime halts ingestion and rolls back unfinalized blocks (`memory_seq_rm`).
* **Subsequent Turn**: Only chunks completed before cancellation remain. The server suffers a **cache miss** on the rest of the prompt and must re-process it from scratch.

### Model Architecture & Memory Bandwidth on Unified Memory

On unified memory systems (like Apple Silicon), generation speed during the decode phase is strictly limited by how fast the GPU can read model weights from memory:

```text
Generation Speed (tokens/sec) = GPU Memory Bandwidth (GB/s) / Active Model Size in VRAM (GB)
```

Because every generated token requires a full pass over the active model weights in RAM, larger models produce slower token streams regardless of available compute cores:

* **Dense Models (120B+):** `mistral-medium-3.5:128b`, `qwen3.5:122b`
    * *Footprint:* 122B – 128B active parameters (~76.5 – 81 GB VRAM)
    * *Throughput:* ~3.5 – 6.5 tokens/sec (M-Max ~800 GB/s)
    * *Best Fit:* Deep architectural refactoring, zero-hallucination audits, complex logic.
* **Dense / Quantized Models (70B+):** `deepseek-r1:70b`, `qwen3-coder-next:q4_K_M`
    * *Footprint:* 70B+ parameters (~42 – 51 GB VRAM)
    * *Throughput:* ~25 – 54 tokens/sec
    * *Best Fit:* Balanced sweet spot of high generation speed, reasoning depth, and memory headroom.
* **Optimized MLX / MoE Models:** `qwen3.6:35b-mlx`, `gemma4:31b-mlx`
    * *Footprint:* Parameter-efficient MLX runtime (~18 – 21 GB VRAM)
    * *Throughput:* ~60 – 90+ tokens/sec
    * *Best Fit:* High-throughput interactive pair programming, fast shell completions, responsive chat.

### macOS Metal GPU Allocation Limits & KV Cache Sizing

Apple Silicon manages Unified Memory using thresholds enforced by the Metal graphics driver and XNU kernel:

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
* **16K Context (`16,384` tokens)**: **~4.9 GB VRAM** (Ideal for 36 GB machines)
* **32K Context (`32,768` tokens)**: **~9.9 GB VRAM**
* **64K Context (`65,536` tokens)**: **~19.8 GB VRAM** (Ideal for 128 GB machines)
* **131K Context (`131,072` tokens)**: **~39.7 GB VRAM**

#### The 64K vs. 128K Context Cliff:
* **At 64K Context**: Dense 128B weights (76.5 GB) + 64K KV Cache (19.8 GB) = **~96.3 GB**.
    * Total process memory: ~107 GB (~101 GB Wired Memory).
    * Memory pressure remains **solid green** with ~5.6 GB of unswapped system headroom. All model layers run inside fast GPU VRAM.
* **At 128K Context**: Total demand reaches 76.5 GB + 39.7 GB = **116.2 GB for the runtime process alone**, pushing total system demand over **135 GB**.
    * macOS hits its wired limit and begins spilling model layers to disk swap.
    * Prompt ingestion collapses from **~140 tokens/sec down to ~10 tokens/sec** as the system spends its time swapping memory pages rather than executing matrix multiplications.

### Client Design & Prompt Overhead

How a client tool structures its requests has a dramatic impact on prefill delay and cache hits:

* **IDE Workspace Auto-Context (e.g., VS Code / Continue)**
    * *Turn #1 (~26k tokens):* **~2.5 to 7.0 minutes** prefill on 128B models; saturates the memory bus and risks evicting existing prefix caches.
* **Targeted Context CLI (e.g., OpenCode)**
    * *Turn #1 (~500 tokens):* **~6.5 seconds** prefill on 128B models.
    * *Turn #2+ Delta (<50 tokens):* **<200 milliseconds** (`f_sim_best = 1.000`) by reusing cached prefixes via Longest Common Prefix (LCP) matching (`OLLAMA_KEEP_ALIVE=30m`).

### Local Model Hardware Tiers

On local hardware, models naturally fall into four practical tiers based on footprint and response speed:

* **Tier 1: Heavyweight Reasoning (120B+)**
    * *Models:* `mistral-medium-3.5:128b` (80 GB), `qwen3.5:122b` (81 GB)
    * *Performance Profile:* Dense / ~3.5 – 6.5 tokens/sec / 64K VRAM
    * *Ideal Use Case:* Multi-file refactoring, security audits, and complex architectural reasoning.
* **Tier 2: General-Purpose Workhorses (70B+)**
    * *Models:* `deepseek-r1:70b` (42 GB), `qwen3-coder-next:q4_K_M` (51 GB)
    * *Performance Profile:* 70B+ RL / Q4 / ~25 – 54 tokens/sec
    * *Ideal Use Case:* Core daily engineering, algorithmic logic, test generation, and pair programming.
* **Tier 3: Fast Interactive Models (26B – 35B)**
    * *Models:* `qwen3.6:35b-mlx` (21 GB), `gemma4:31b-mlx` (18 GB)
    * *Performance Profile:* MLX / ~60 – 90+ tokens/sec / ~18 – 21 GB VRAM
    * *Ideal Use Case:* Rapid inline completions, CLI interactive loops, and sweet spot for 36GB–48GB MacBooks.
* **Tier 4: Lightweight Utility Models (Sub-14B)**
    * *Models:* `gemma4:12b-mlx` (7.7 GB), `qwen3.5:9b-mlx` (8.9 GB)
    * *Performance Profile:* <10 GB VRAM / ~80 – 120+ tokens/sec / low power draw
    * *Ideal Use Case:* Quick terminal command lookups and commit message drafting on base laptops.

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

- **Memory Cliff Thrashing (OS Swap):** Exceeding Metal GPU wired memory limits (~98 GB on 128 GB hardware) spills layers into swap, collapsing prefill speed from 140 t/s to 10 t/s.
    - *Mitigation:* Hard-cap context windows to safe limits (`65536` for 128 GB setups, `16384` for 36 GB setups) and monitor wired memory allocations before expanding context depth.
- **Premature Prefill Interruption:** Canceling a request during prompt ingestion invalidates the unfinalized sequence chunk, forfeiting the KV cache for the next turn.
    - *Mitigation:* Allow the prefill phase to complete before canceling or re-prompting; canceling immediately as generation begins retains the full prefix in the cache.
- **Prefix Cache Busting:** Dynamic timestamps, non-deterministic system prompts, or fluctuating tool definitions at the start of prompts prevent LCP cache hits.
    - *Mitigation:* Structure prompts with static, deterministic prefixes (system prompt → tool definitions → workspace metadata) at the top of every turn, placing dynamic inputs strictly at the end.
- **Client Payload Bloat:** Automated editor extensions dumping uncompressed file trees, open tabs, and git logs inflate prompt sizes beyond 25,000 tokens, degrading initial response times.
    - *Mitigation:* Favor targeted CLI interfaces or explicit reference mechanisms (`@file`, bounded git diffs) that restrict Turn #1 payloads to relevant context.
