---
title: "Rustoku"
description: "High-performance Sudoku solver in Rust."
summary: "Fast Sudoku solver and generator in Rust using bitmasking and MRV heuristics; emphasizes speed, determinism, and explainable solve traces."
tags: ["algorithms","sudoku","rust","performance"]
categories: ["deep-dives"]
---

## Context — Problem — Solution

**Context:** `Rustoku` implements fast Sudoku solving/generation in Rust using bitmasking and MRV heuristics, exposing both library and CLI.

**Problem:** Producing extremely fast solves while keeping generation deterministic, guaranteeing uniqueness, and providing human-understandable solve paths requires careful algorithm design and test coverage.

**Solution (high-level):** Optimize core algorithms (bitmask operations, ordering heuristics), instrument micro-benchmarks, and produce explainable step traces mapping to human techniques.

## 1. The Local Implementation

- **Current Logic:** Uses bitmasking for constraint propagation, backtracking with MRV heuristics, and generator that ensures unique solutions and configurable clue counts. CLI supports generate/solve/check workflows.
- **Bottleneck:** Worst-case backtracking paths for hard puzzles; ensuring generator produces targeted difficulty levels reliably.

## 2. Scaling Strategy

- **Vertical vs. Horizontal:** Focus on algorithmic speedups and low-level optimizations (avoid memory allocations, use iterators) rather than distributed scaling. For bulk generation, parallelize across worker threads or processes.
- **State Management:** Record generation seeds and solver traces to reproduce puzzles and debug edge cases.

## 3. Comparison to Industry Standards

- **My Project:** High-performance, explanatory solver with generation controls and human-like techniques.
- **Industry:** Research-grade solvers may use advanced deductive algorithms and heavy precomputation; Rustoku focuses on clarity and speed with a modest feature set.
- **Gap Analysis:** For research-scale solving, add more advanced strategies and profiling-guided optimizations.

## 4. Experiments & Metrics

- **Solve time distribution:** micro-benchmarks across puzzle difficulty buckets.
- **Generator quality:** ratio of generated puzzles that match intended difficulty; uniqueness validation cost.
- **Trace clarity:** user studies or heuristics to validate step-by-step explanations map to human techniques.

## 5. Risks & Mitigations

- **Incorrect difficulty classification:** instrument empirical metrics and tune generator heuristics.
- **Performance regressions:** add CI benchmarks and regression alerts.

## Related Principles

- [Algorithms & Performance](/principles/algorithms-performance): Bitmasking, MRV heuristics, micro-benchmarking, deterministic generators, and explainable traces.
