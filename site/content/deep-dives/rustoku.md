---
title: "Rustoku"
description: "A high-performance Sudoku solver implementation in Rust."
summary: "A highly optimized Sudoku engine engineered in Rust, featuring advanced human-like techniques, multi-platform support (Python, WASM), and microsecond-level performance."
tags: [optimization, search-algorithms, systems-programming]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/rustoku"
  demo: "https://sambyte.net/rustoku/"
draft: false
date: "2026-10-11T10:00:00-07:00"
---

## Context & Motivation

**Context:** `Rustoku` implements fast Sudoku solving and generation in Rust, exposing a library crate, a CLI, and native bindings for Python and WebAssembly. The core uses bitmasking for constraint tracking and Minimum Remaining Values (MRV) heuristics to guide backtracking, producing solve traces that map to complex human-understandable techniques.

**Motivation:** I wanted to recall the lessons I learned in college from building a Sudoku solver in C++, but this time with a focus on Rust's strengths (safety, expressiveness) and modern algorithmic techniques. The challenge was to design a solver that is not only fast (sub-millisecond solves) but also produces deterministic outputs and human-readable solve paths. By expanding to WASM and Python, I wanted to prove the portability of the Rust core across different ecosystems.

## The Local Implementation

- **Advanced Techniques:** The solver has evolved beyond simple backtracking to include a full suite of human-like solving strategies. Using a `bitflags`-based classifier, it handles **Swordfish**, **Jellyfish**, **Skyscraper**, **W-Wings**, **XY-Wings**, and **Alternating Inference Chains (AIC)**. These allow the generator to produce puzzles with precise difficulty tiers (Easy to Expert) and provide explainable solve traces for any valid puzzle.
- **Multi-Platform Architecture & Solution Counting:** To support the web and Python, I implemented a `rustoku-lib::bind` layer. This internal module provides a simplified, serializable API that the `rustoku-wasm` and `rustoku-py` crates use to marshal data. The v0.16.0 release introduced a dedicated `count` API across all bindings, allowing consumers to determine the exact number of valid solutions for a puzzle (essential for difficulty classification and uniqueness verification) without paying the allocation and marshalling overhead of full solution grids.
- **Allocation discipline:** The inner solve loop avoids heap allocations entirely. The central `Rustoku` struct has a tiny **1KB footprint** (81-byte board + 108-byte mask + 324-byte candidate cache), allowing it to live entirely in the CPU's L1 cache. Backtracking uses a fixed-size stack rather than a `Vec<Frame>`, eliminating allocator overhead and enabling microsecond-level solve times.
- **Trace generation:** Each solve step emits a structured record: `{ cell: (row, col), candidates: [digits], chosen: digit, technique: "Swordfish" | "Naked Pair" | ... }`. These traces power the interactive web demo, showing users exactly how the engine derived a solution without brute force.
- **Generator logic:** The generator produces puzzles by filling a solved grid with a seeded RNG, then iteratively removing clues while verifying uniqueness via the solver in `solve_all` mode (utilizing **Rayon** for parallel search). Puzzles can be generated with specific symmetric layout constraints (e.g., rotational, diagonal, or bilateral symmetry) using a flexible builder pattern.
- **Web Demo Enhancements:** The interactive web demo received major UX upgrades across the v0.15 release cycle. A **visual step trace** mode (`demo/src/trace.ts`) animates each solver step directly on the grid, highlighting the current cell, candidate eliminations, and the applied technique to give users a frame-by-frame view of the solve path. Custom typography and refined styling were applied across UI buttons and grid components. Undo/redo history is fully validated: duplicate board states are rejected on push and guarded against off-by-one hydration bugs, with accessibility supported by proper modal ARIA roles and focus trapping.
- **Keyless OIDC Multi-Registry Publishing:** The release pipeline uses keyless GitHub Actions OIDC Trusted Publishing across crates.io (`crates-release.yml`), PyPI (`py-release.yml`), and npm (`wasm-release.yml`). Tag pushes automatically build, test, and publish packages (including cross-platform precompiled Python wheels for Linux, macOS, and Windows) without storing long-lived static API tokens.
- **Documentation & Doctest Rigor:** Achieved 100% rustdoc API coverage (111/111 public items) across `rustoku-lib`, backed by 25 runnable, CI-verified `# Examples` doctests exercising solver execution, puzzle generation, formatting, and binding paths alongside strict clippy warning enforcement.
- **Workspace Build Configuration:** A `.cargo/config.toml` standardizes cross-crate build targets and linker flags for the entire Cargo workspace, while demo build verification is integrated directly into main CI workflows.

{{< pseudocode id="rustoku-mrv-solver" title="Bitmask MRV Backtracking Solver" >}}
```rust
// Minimum Remaining Values (MRV) Backtracking Search Loop
struct RustokuSolver {
    board: [u8; 81],       // 0 for empty, 1..=9 for clues/digits
    row_masks: [u16; 9],   // Bitmask of digits placed in each row
    col_masks: [u16; 9],   // Bitmask of digits placed in each column
    box_masks: [u16; 9],   // Bitmask of digits placed in each 3x3 box
    candidates: [u16; 81], // Bitmask of valid candidate digits per cell
}

impl RustokuSolver {
    // 1. Select the most constrained unassigned cell (MRV Heuristic)
    fn find_mrv_cell(&self) -> Option<(usize, usize)> {
        let mut min_candidates = 10;
        let mut best_cell = None;

        for (r, c) in self.empty_cells() {
            // Hardware POPCNT instruction counts remaining candidate bits
            let count = self.candidates[r * 9 + c].count_ones();
            if count < min_candidates {
                min_candidates = count;
                best_cell = Some((r, c));
                if count == 1 {
                    return best_cell; // Immediate shortcut for naked singles
                }
            }
        }
        best_cell
    }

    // 2. Recursive depth-first search with forward-checking and constraint propagation
    fn solve_backtrack(&mut self) -> bool {
        // Base case: All cells filled -> valid solution reached
        let Some((r, c)) = self.find_mrv_cell() else {
            return true;
        };

        let candidate_mask = self.candidates[r * 9 + c];
        for num in 1..=9 {
            let bit = 1 << (num - 1);
            if (candidate_mask & bit) == 0 {
                continue; // Digit violates current row, col, or box mask
            }

            // Forward move: place digit on board, set mask bits, prune peer candidates
            self.place_number(r, c, num);

            if self.solve_backtrack() {
                return true; // Propagate success
            }

            // Backtrack: clear cell, restore mask bits, recalculate peer candidates
            self.remove_number(r, c, num);
        }

        false // Trigger backtracking in parent caller
    }
}
```
{{< /pseudocode >}}

## Comparison to Industry Standards

- **My Project:** A multi-target, explanatory Sudoku engine engineered for auditability and human-like logic. It uniquely integrates library, CLI, Python, and WASM interfaces from a single high-performance source with keyless multi-registry release automation.
- **Industry:** Research-grade solvers (e.g., tdoku) use SIMD-vectorized constraint propagation and cache-line-aligned data structures for maximum throughput. Competition-grade generators use SAT solvers for difficulty classification.
- **Gap Analysis:** To approach research-level performance, explore SIMD-based candidate elimination (processing multiple cells per instruction). On the qualitative side, the `bitflags` classifier now covers nearly all major human techniques (Swordfish, AIC), significantly narrowing the gap with professional grade scorers.

## Risks & Mitigations

- **Technique Complexity:** With the addition of advanced techniques like AIC and wings, logic regressions are harder to spot. **Mitigation:** Replaced hardcoded unit tests with a **comprehensive CSV dataset** for batch validation, ensuring every technique correctly prunes candidates across thousands of edge cases.
- **Package Publishing Security:** Static long-lived API tokens for PyPI, npm, and crates.io present credential leakage risks. **Mitigation:** Configured pure OIDC Trusted Publishing with short-lived cryptographic identity tokens bound to GitHub Actions workflow environments.
- **Demo State Integrity:** Undo/redo history and startup persistence are subtle to test across all game sequences. Duplicate states or stale history on hydration can silently corrupt game state. **Mitigation:** A dedicated `demo/src/state.ts` test suite validates edge cases (duplicate push prevention, redo after mid-sequence moves, empty-history boundaries) using Vitest unit tests. Modal accessibility regressions are guarded with ARIA role audits.
- **Performance regressions:** Criterion benchmarks run in CI with statistical comparison against the baseline. Alert on P95 regressions exceeding 5%.
- **Bitmask correctness:** property-based tests with `proptest` verify that constraint propagation maintains invariants: every valid digit remains in the candidate set and every eliminated digit is genuinely constrained.
- **Generator non-termination:** cap the number of clue-removal attempts and fall back to regeneration if uniqueness checking exceeds a timeout. Log seeds for puzzles that hit the cap for later investigation.
