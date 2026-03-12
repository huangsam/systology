---
title: "Rustoku"
description: "A high-performance Sudoku solver implementation in Rust."
summary: "A highly optimized Sudoku engine engineered in Rust, featuring advanced human-like techniques, multi-platform support (Python, WASM), and microsecond-level performance."
tags: ["algorithms", "performance", "rust"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/rustoku"
  demo: "https://sambyte.net/rustoku/"
draft: false
date: "2026-03-12T10:22:20-08:00"
---

## Context & Motivation

**Context:** `Rustoku` implements fast Sudoku solving and generation in Rust, exposing a library crate, a CLI, and native bindings for Python and WebAssembly. The core uses bitmasking for constraint tracking and Minimum Remaining Values (MRV) heuristics to guide backtracking, producing solve traces that map to complex human-understandable techniques.

**Motivation:** I wanted to recall the lessons I learned in college from building a Sudoku solver in C++, but this time with a focus on Rust's strengths (safety, expressiveness) and modern algorithmic techniques. The challenge was to design a solver that is not only fast (sub-millisecond solves) but also produces deterministic outputs and human-readable solve paths. By expanding to WASM and Python, I wanted to prove the portability of the Rust core across different ecosystems.

## The Local Implementation

- **Advanced Techniques:** The solver has evolved beyond simple backtracking to include a full suite of human-like solving strategies. Using a `bitflags`-based classifier, it handles **Swordfish**, **Jellyfish**, **Skyscraper**, **W-Wings**, **XY-Wings**, and **Alternating Inference Chains (AIC)**. These allow the generator to produce puzzles with precise difficulty tiers (Easy to Expert) and provide explainable solve traces for any valid puzzle.
- **Multi-Platform Architecture:** To support the web and Python, I implemented a `rustoku-lib::bind` layer. This internal module provides a simplified, serializable API that the `rustoku-wasm` and `rustoku-py` crates use to marshal data. This ensures the core solving logic remains "single-source" while appearing native to JavaScript and Python users.
- **Allocation discipline:** The inner solve loop avoids heap allocations entirely. The central `Rustoku` struct has a tiny **1KB footprint** (81-byte board + 108-byte mask + 324-byte candidate cache), allowing it to live entirely in the CPU's L1 cache. Backtracking uses a fixed-size stack rather than a `Vec<Frame>`, eliminating allocator overhead and enabling microsecond-level solve times.
- **Trace generation:** Each solve step emits a structured record: `{ cell: (row, col), candidates: [digits], chosen: digit, technique: "Swordfish" | "Naked Pair" | ... }`. These traces power the interactive web demo, showing users exactly how the engine derived a solution without brute force.
- **Generator logic:** The generator produces puzzles by filling a solved grid with a seeded RNG, then iteratively removing clues while verifying the solution remains unique by running the solver in `solve_all` mode (utilizing **Rayon** for parallel search when needed).

## Comparison to Industry Standards

- **My Project:** A cross-platform, explanatory Sudoku engine that prioritizes auditability and human-like logic. It uniquely combines library, CLI, Python, and WASM interfaces into a single source.
- **Industry:** Research-grade solvers (e.g., tdoku) use SIMD-vectorized constraint propagation and cache-line-aligned data structures for maximum throughput. Competition-grade generators use SAT solvers for difficulty classification.
- **Gap Analysis:** To approach research-level performance, explore SIMD-based candidate elimination (processing multiple cells per instruction). On the qualitative side, the `bitflags` classifier now covers nearly all major human techniques (Swordfish, AIC), significantly narrowing the gap with professional grade scorers.

## Risks & Mitigations

- **Technique Complexity:** With the addition of advanced techniques like AIC and wings, logic regressions are harder to spot. **Mitigation:** Replaced hardcoded unit tests with a **comprehensive CSV dataset** for batch validation, ensuring every technique correctly prunes candidates across thousands of edge cases.
- **Performance regressions:** Criterion benchmarks run in CI with statistical comparison against the baseline. Alert on P95 regressions exceeding 5%.
- **Bitmask correctness:** property-based tests with `proptest` verify that constraint propagation maintains invariants—every valid digit remains in the candidate set and every eliminated digit is genuinely constrained.
- **Generator non-termination:** cap the number of clue-removal attempts and fall back to regeneration if uniqueness checking exceeds a timeout. Log seeds for puzzles that hit the cap for later investigation.
