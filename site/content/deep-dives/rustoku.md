---
title: "Rustoku"
description: "High-performance Sudoku solver in Rust."
summary: "Fast Sudoku solver and generator in Rust using bitmasking and MRV heuristics; emphasizes speed, determinism, and explainable solve traces."
tags: ["algorithms", "performance", "rust"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/rustoku"
draft: false
---

## Context & Motivation

**Context:** `Rustoku` implements fast Sudoku solving and generation in Rust, exposing both a library crate and a CLI. The core uses bitmasking for constraint tracking and Minimum Remaining Values (MRV) heuristics to guide backtracking, producing solve traces that map to human-understandable techniques.

**Motivation:** I wanted to recall the lessons I learned in college from building a Sudoku solver in C++, but this time with a focus on Rust's strengths (safety, expressiveness) and modern algorithmic techniques. The challenge was to design a solver that is not only fast (sub-millisecond solves for easy/medium puzzles) but also produces deterministic outputs and human-readable solve paths. Additionally, I wanted to implement a generator that can produce puzzles of varying difficulty while ensuring uniqueness of the solution.

## The Local Implementation

- **Current Logic:** Each cell's candidate set is represented as a `u32` bitmask where bit `i` indicates digit `i` is still possible. Constraint propagation uses bitwise AND/OR to update row, column, and box masks (27 `u32` values totaling 108 bytes) in O(1) per elimination. The solver selects the cell with the fewest remaining candidates (MRV heuristic), which empirically reduces backtracking depth by 3–5× compared to left-to-right scanning. The generator produces puzzles by filling a solved grid with a seeded RNG, then iteratively removing clues while verifying the solution remains unique by running the solver and checking that no second solution exists.
- **Allocation discipline:** the inner solve loop avoids heap allocations entirely—the board is a fixed `[u8; 81]` array (81 bytes for cell values), with 81 `u32` candidate masks (324 bytes) tracking possibilities per cell. Candidate iteration uses `trailing_zeros()` on the bitmask rather than collecting into a `Vec`, and the backtracking stack uses a fixed-size array rather than a `Vec<Frame>`. This keeps the hot path in L1 cache and eliminates allocator overhead, which was critical for achieving microsecond-level solve times on easy/medium puzzles.
- **Trace generation:** each solve step emits a structured record: `{ cell: (row, col), candidates: [digits], chosen: digit, technique: "naked_single" | "mrv_backtrack" | ... }`. These traces serve dual purposes—debugging incorrect solves and providing human-readable explanations of the solution path.
- **Bottleneck:** Worst-case backtracking on adversarial puzzles (e.g., 17-clue minimal puzzles designed to maximize search depth) can still take milliseconds. Generator difficulty targeting is heuristic—clue count correlates with difficulty but doesn't guarantee it, so some generated "hard" puzzles solve in microseconds while some "medium" puzzles require deep backtracking.

## Comparison to Industry Standards

- **My Project:** High-performance, explanatory solver with generation controls and human-like technique mapping. Prioritizes clarity and auditability alongside speed.
- **Industry:** Research-grade solvers (e.g., tdoku) use SIMD-vectorized constraint propagation and cache-line-aligned data structures for maximum throughput. Competition-grade generators use SAT solvers for difficulty classification.
- **Gap Analysis:** To approach research-level performance, explore SIMD-based candidate elimination (processing multiple cells per instruction). For reliable difficulty classification, integrate a technique-counting heuristic that scores puzzles based on which human techniques are required (naked singles = easy, X-wings = hard) rather than relying solely on clue count.

## Risks & Mitigations

- **Incorrect difficulty classification:** instrument empirical metrics (technique counting, backtracking depth) and tune generator heuristics. Maintain a labeled test set of puzzles with known difficulty grades.
- **Performance regressions:** Criterion benchmarks run in CI with statistical comparison against the baseline. Alert on P95 regressions exceeding 5%.
- **Bitmask correctness:** property-based tests with `proptest` verify that constraint propagation maintains invariants—every valid digit remains in the candidate set and every eliminated digit is genuinely constrained.
- **Generator non-termination:** cap the number of clue-removal attempts and fall back to regeneration if uniqueness checking exceeds a timeout. Log seeds for puzzles that hit the cap for later investigation.
