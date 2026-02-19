---
title: "Algorithms & Performance"
description: "Best practices for algorithms and performance."
summary: "Principles for clear algorithms and performance engineering: micro-benchmarks, memory discipline, and deterministic generators."
tags: ["algorithms", "performance"]
categories: ["principles"]
draft: false
---

## Algorithmic Clarity

Choose algorithms that are well-understood and documented, with clear complexity analysis—correctness and maintainability often outweigh marginal performance gains. Study canonical implementations (dynamic programming, graphs, backtracking) to build deep patterns into your mental model.

## Micro-benchmarking

Add targeted benchmarks for hot paths and track them in CI to catch regressions early. Profile various input sizes to understand where bottlenecks actually live rather than optimizing hunches.

## Memory & Allocation Discipline

Minimize allocations in tight loops through buffer reuse and prefer stack allocation for speed-critical paths. Arena allocators or pools are valuable for repeated small allocations, but the upfront cost isn't worth it without evidence.

## Deterministic Generators

Record and version random seeds to make debug traces reproducible and allow investigation of edge cases. This discipline turns unlucky failures into debuggable scenarios that you can revisit.

## Explainability & Debug Traces

Emit human-readable traces that link each step to algorithm decisions and reasoning—this bridges the gap between "what happened" and "why it happened," critical for both debugging and learning.

## Profiling-driven Optimization

Use profiler data to avoid optimizing the wrong thing; maintain comprehensive tests to ensure changes actually improve the metric you care about without breaking correctness.

## Parallelism for Bulk Work

Use worker pools and data partitioning to scale bulk tasks horizontally, but keep per-worker state management simple and deterministic to stay maintainable.
