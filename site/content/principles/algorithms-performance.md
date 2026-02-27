---
title: "Algorithms & Performance"
description: "Best practices for algorithms and performance."
summary: "Principles for clear algorithms and performance engineering: micro-benchmarks, memory discipline, and deterministic generators."
tags: ["algorithms", "performance"]
categories: ["principles"]
draft: false
---

## Algorithmic Clarity

Choose algorithms that are well-understood and documented—correctness and maintainability often outweigh marginal performance gains. Study canonical implementations (dynamic programming, graphs, backtracking) to build deep expertise.

See how [Rustoku]({{< ref "/deep-dives/rustoku" >}}) applies MRV heuristics and bitmasking to keep backtracking tight, and how [Grit]({{< ref "/deep-dives/grit" >}}) uses LRU caching for object storage—both prioritize clarity alongside speed.

Practicing [LeetCode](https://leetcode.com/) is a great way to improve algorithmic thinking and problem-solving skills. It's a platform that provides a wide range of algorithm problems with varying difficulty levels.

**Anti-pattern — Premature Cleverness:** Reaching for exotic data structures (skip lists, Fibonacci heaps) before proving the simple approach is too slow. The debugging cost of a clever structure you don't fully understand outweighs the theoretical speedup.

## Micro-benchmarking

Add targeted benchmarks for hot paths and track them in CI to catch regressions early. Profile various input sizes to understand where bottlenecks actually live rather than optimizing hunches.

Use a framework appropriate to your language: [Criterion](https://bheisler.github.io/criterion.rs/book/) for Rust, JMH for Java, `pytest-benchmark` for Python, or BenchmarkDotNet for C#. Run benchmarks with statistical rigor—multiple iterations, warm-up phases, and outlier detection—so you're measuring signal, not noise.

**Anti-pattern — Benchmark Theater:** Writing benchmarks that only test the happy path with trivial inputs. If your production workload is 10 million rows and your benchmark tests 100, the numbers are meaningless. Always benchmark at representative scale with realistic data distributions.

**Anti-pattern — Optimizing Without a Baseline:** Making changes and eyeballing "feels faster." Without a versioned baseline measurement, you can't distinguish real improvement from noise. Track benchmark results in CI artifacts and alert on regressions.

## Memory & Allocation Discipline

Minimize allocations in tight loops through buffer reuse and prefer stack allocation for speed-critical paths. Arena allocators or pools are valuable for repeated small allocations, but the upfront cost isn't worth it without evidence.

In Rust, this means preferring `&str` over `String` in hot paths, using `Vec::with_capacity` when sizes are known, and leveraging `SmallVec` or `ArrayVec` for bounded collections. In Java, watch for autoboxing in tight loops (`int` vs `Integer`). In Python, use `__slots__` for data-heavy classes and generator expressions over list comprehensions when you only need iteration.

**Anti-pattern — Allocation Blindness:** Ignoring allocator behavior because "the GC will handle it." In latency-sensitive code, GC pauses can dominate your P99. Use allocation profilers (`DHAT` for Rust, `async-profiler` for JVM, `tracemalloc` for Python) to quantify allocation rates before assuming they don't matter.

See the [Rustoku deep-dive]({{< ref "/deep-dives/rustoku" >}}) for an example of allocation-conscious Sudoku solving where avoiding heap allocations in the inner loop was critical for microsecond-level solve times.

## Deterministic Generators

Record and version random seeds to make debug traces reproducible and allow investigation of edge cases. This discipline turns unlucky failures into debuggable scenarios that you can revisit.

In practice, this means every random decision (puzzle generation, test data synthesis, training shuffles) should accept an explicit seed parameter that gets logged. When a test fails or a user reports a bug, you can reproduce the exact sequence of events by replaying the seed.

**Anti-pattern — Implicit Randomness:** Calling `rand()` without seeding and hoping for the best. When you can't reproduce a failure, you can't fix it with confidence. Even worse: using system time as a seed without logging it—you get different behavior every run with no way to replay.

[Rustoku]({{< ref "/deep-dives/rustoku" >}}) records generation seeds and solver traces so every puzzle is reproducible and debuggable—a direct application of this principle.

## Explainability & Debug Traces

Emit human-readable traces that link each step to algorithm decisions and reasoning—this bridges the gap between "what happened" and "why it happened," critical for both debugging and learning.

Good traces are structured. Instead of `"processing item 42"`, emit `"step=backtrack cell=(3,7) candidates=[1,4,9] chosen=4 reason=MRV"`. This level of detail lets you reconstruct the decision tree after the fact, whether for debugging a wrong answer or teaching someone how the algorithm works.

**Anti-pattern — Binary Logging:** Only logging "success" or "failure" with no intermediate state. By the time you know something failed, you've lost all the context about how it got there. Invest in trace infrastructure proportional to algorithm complexity.

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for broader guidance on structured logging that applies well to algorithm traces.

## Profiling-driven Optimization

Use profiler data to avoid optimizing the wrong thing; maintain comprehensive tests to ensure changes actually improve the metric you care about without breaking correctness.

Start with a flame graph (`perf` + `flamegraph` on Linux, Instruments on macOS, `py-spy` for Python) to identify where time actually goes. The bottleneck is almost never where you think it is—profiling typically reveals that 80% of time is spent in 5% of the code.

**Anti-pattern — Gut-feel Optimization:** Rewriting a function because it "looks slow" without profiling first. This wastes effort on cold paths while the real bottleneck hides elsewhere. Always measure, then optimize, then measure again to confirm improvement.

## Parallelism for Bulk Work

Use worker pools and data partitioning to scale bulk tasks horizontally, but keep per-worker state management simple and deterministic to stay maintainable.

Partition work by natural keys (file ID, user ID, shard number) and assign partitions to workers. Each worker should be stateless or carry only its partition's state—shared mutable state across workers introduces synchronization costs that often negate parallelism gains.

For CPU-bound work (hashing, compression, solving), thread pools with work-stealing (Rayon in Rust, `ForkJoinPool` in Java) are effective. For IO-bound work (API calls, file downloads), async task pools or process pools avoid GIL contention in Python.

**Anti-pattern — Parallelism Without Measurement:** Spinning up 64 threads because "more is faster." Thread contention, context switching, and memory overhead can make parallel code slower than sequential. Benchmark with varying worker counts and find the knee of the curve. See the [Networking & Services]({{< ref "/principles/networking-services" >}}) principles for a production-grade approach to worker scaling and background job queues.

## Decision Framework

When optimizing algorithms, use the following guide to choose your battle:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Maintainability** | Clarity & O(n log n) | Lower cognitive load for the team; easier to fix bugs. |
| **P99 Latency** | Memory Discipline | Avoiding allocations reduces GC/allocator jitter. |
| **Bulk Throughput** | Parallelism | Horizontally scaling work processes more data per second. |
| **Reproducibility** | Deterministic Seeds | Essential for debugging production failures. |

**Decision Heuristic:** "Choose **Profiling** before **Cleverness**. Only reach for complex data structures when a flame graph proves the simple way is your primary bottleneck."

## Cross-principle Notes

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for broader guidance on structured logging that applies well to algorithm traces.
