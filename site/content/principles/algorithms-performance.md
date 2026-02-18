---
title: "Algorithms & Performance"
description: "Best practices for algorithms and performance."
summary: "Principles for clear algorithms and performance engineering: micro-benchmarks, memory discipline, and deterministic generators."
tags: ["algorithms", "performance"]
categories: ["principles"]
draft: false
---

1. Algorithmic Clarity
    - Prefer clear, proven algorithms (bitmasking, MRV) with documented invariants.
    - Analyze and document time/space complexity for each approach.
    - Choose algorithms that balance correctness, performance, and maintainability.
    - Study canonical implementations (arrays, backtracking, dynamic programming, graphs, trees) for foundational understanding.

2. Micro-benchmarking
    - Add targeted benchmarks for hot paths using criterion or similar tools.
    - Track performance regressions in CI with automated thresholds.
    - Profile different input sizes and edge cases to identify bottlenecks.

3. Memory & Allocation Discipline
    - Minimize allocations in tight loops by reusing buffers and structures.
    - Prefer stack allocation and inline operations for speed-critical paths.
    - Use arena allocators or pools for repeated small allocations.

4. Deterministic Generators
    - Record and version random seeds for reproducible puzzle generation.
    - Use seeded generators to debug unusual or problematic cases.
    - Ensure generators produce diverse, valid puzzles within constraints.

5. Explainability & Debug Traces
    - Emit human-readable solve traces linking steps to algorithm names.
    - Include decision rationale and backtracking information in traces.
    - Support configurable trace levels for different debugging needs.

6. Profiling-driven Optimization
    - Use profiler data to identify real bottlenecks before optimizing.
    - Maintain comprehensive tests to validate correctness after changes.
    - Document optimization decisions and their performance impact.

7. Parallelism for Bulk Work
    - Use worker pools for scalable generation and verification tasks.
    - Preserve determinism per-worker through careful seed management.
    - Implement work stealing or partitioning for load balancing.
