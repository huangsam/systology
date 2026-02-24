---
title: "Compiler Design"
description: "Optimization, portability and resilience for compilers."
summary: "Guidelines for compiler design: clear IR boundaries, deterministic semantics, robust error reporting, and incremental compilation."
tags: ["compiler"]
categories: ["principles"]
draft: false
---

## Clean IR Boundaries

Maintain clear separation between parsing, semantic analysis, and IR lowering with explicit invariants between stages. This isolation makes each pass easier to test, understand, and optimize independently.

In practice, each compiler phase should consume a well-typed input and produce a well-typed output. The parser emits an AST, semantic analysis produces an annotated AST, and lowering generates an IR—each boundary is a contract. When you need to change how optimization works, you modify one pass without worrying about ripple effects in parsing or code generation.

**Anti-pattern — Monolithic Pass:** Combining parsing, type-checking, and code generation into a single function. This makes bugs nearly impossible to isolate and kills incremental compilation potential. If adding a new language feature requires touching every stage simultaneously, your boundaries are too blurry.

## Deterministic Semantics

Define a well-specified language subset with predictable behavior rather than attempting to support every edge case—unsupported constructs should fail fast with clear error messages instead of producing subtle bugs downstream.

Write a specification (even an informal one) that answers: what happens for every input? Undefined behavior is the enemy of debuggability. If your language inherits UB from a host language (C, C++), document exactly which constructs are safe and add runtime checks in debug builds for the rest.

**Anti-pattern — Implicit Coercion Soup:** Allowing automatic type coercion everywhere (like JavaScript's `[] + {}`) to be "flexible." This creates a combinatorial explosion of edge cases that surprises users and generates subtle bugs. Be explicit about conversions and require casts for lossy operations.

## Error Reporting & UX

Provide diagnostics linked to source locations with actionable recovery suggestions; error messages are the first impression users have of your compiler, so they should be designed for clarity over terseness.

Great error messages include:

1. Where the error is (file, line, column with a source snippet)
2. What went wrong in plain language
3. How to fix it

Rust's compiler errors are the gold standard—study them. Consider colorized output, ASCII art for pointer arrows, and "did you mean?" suggestions for typos.

**Anti-pattern — Cryptic Error Codes:** Emitting `"E0042: type mismatch"` with no context. If the user has to search a separate manual to understand an error, you've failed at UX. Inline the explanation and show the relevant code snippet with the mismatch highlighted.

**Anti-pattern — Error Avalanche:** Reporting 200 errors when the first one (a missing semicolon) caused all subsequent ones. Implement error recovery in the parser so you can continue past the first error and report genuinely independent issues—but cap the output and prioritize the first few.

## Test Harnesses

Use filecheck-style output testing (AST dumps, IR) and maintain regression suites across different architectures and optimization levels—this catches silent correctness regressions that benchmarks miss.

Structure your test suite in tiers: (1) unit tests for individual passes, (2) snapshot tests that compare AST/IR dumps against golden files, (3) end-to-end tests that compile and run programs checking output, and (4) fuzz tests that generate random programs and verify the compiler doesn't crash.

**Anti-pattern — Testing Only Happy Paths:** Writing tests that only compile valid programs. Your compiler will spend most of its time handling invalid input—invest heavily in tests for error paths, edge cases, and adversarial inputs.

## Incremental Compilation

Cache artifacts and track dependencies to avoid recompiling unchanged modules, speeding up the feedback loop during development without sacrificing correctness through overly aggressive caching.

The key insight is dependency tracking: for each compilation unit, record what it depends on (imported symbols, macros, type definitions). When a dependency changes, invalidate only the affected units. Use content hashing (not timestamps) to detect actual changes—a file save that doesn't change content shouldn't trigger recompilation.

**Anti-pattern — Cache Everything Forever:** Aggressively caching without proper invalidation logic. Stale caches cause mysterious "it works after a clean build" bugs that destroy trust in the build system. When in doubt, invalidate more rather than less—correctness over speed.

## IR Validation

Validate generated IR against reference implementations and include runtime assertions for critical invariants—this catches code generation bugs early rather than letting them escape to production targets.

Build a verifier pass that runs after each transformation and checks structural invariants: types are consistent, control flow is well-formed, SSA dominance properties hold. This is cheap insurance—most IR bugs manifest as violated invariants that a verifier catches instantly but would otherwise produce wrong code silently.

**Anti-pattern — Trust the Transform:** Assuming that if a transformation pass compiles, it produces correct IR. Compiler bugs are insidious because they produce programs that *almost* work. A verifier catches the subtle cases where a register is used before definition or a phi node references a non-dominating block.

See [VirtuC]({{< ref "/deep-dives/virtuc" >}}) for an implementation of a compiler that emits LLVM IR and explicitly runs a verifier pass before backend compilation.

## Tooling & Teaching Aids

Provide AST and IR visualizers, interactive REPLs, and documentation with examples—these tools help both compiler developers and users understand the pipeline and debug problems faster.

A `--dump-ast` flag, an IR pretty-printer, and a step-through mode that shows each optimization pass's effect on the IR are invaluable. For educational compilers, a web playground where users can type code and see the AST/IR live (à la [Compiler Explorer](https://godbolt.org/)) dramatically lowers the learning curve.

See the [Extensibility & Plugin Architecture]({{< ref "/principles/extensibility" >}}) principles for related guidance on making compiler internals composable and inspectable.

## Performance vs. Correctness

Prioritize correctness first, then add optimizations incrementally with benchmarks to validate improvements. Document performance-correctness tradeoffs and use assertions to guard invariants.

The ordering matters: a correct slow compiler can be optimized, but a fast incorrect compiler generates wrong programs that erode trust. Gate optimizations behind flags (`-O0`, `-O1`, `-O2`) so users can disable them when debugging, and ensure the unoptimized path is always available as a correctness baseline.

**Anti-pattern — Optimization Without Tests:** Adding an optimization pass (constant folding, dead code elimination, loop unrolling) without adding regression tests that exercise the corner cases. Every optimization is a potential source of miscompilation—test the edge cases explicitly, not just the obvious wins.

## Decision Framework

Choose your compiler architecture based on the target audience and longevity of the language:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Instructional Clarity**| Single-Pass/Tree-Walk | Easiest for students to map source code to execution. |
| **Production Speed** | Multi-Pass with SSA | Allows for complex optimizations like DCE and inlining. |
| **Developer Velocity** | Incremental Artifacts | Minimizes recompile times for large codebases. |
| **Reliable Portability**| Stable C-API / LLVM | Leverages existing backends for multiple CPU targets. |

**Decision Heuristic:** "Choose **Clean IR Boundaries** over performance hacks. A well-structured pipeline is easier to optimize later than a tangled monolithic pass is to fix."
