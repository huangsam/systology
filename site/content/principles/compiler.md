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

## Deterministic Semantics

Define a well-specified language subset with predictable behavior rather than attempting to support every edge case—unsupported constructs should fail fast with clear error messages instead of producing subtle bugs downstream.

## Error Reporting & UX

Provide diagnostics linked to source locations with actionable recovery suggestions; error messages are the first impression users have of your compiler, so they should be designed for clarity over terseness.

## Test Harnesses

Use filecheck-style output testing (AST dumps, IR) and maintain regression suites across different architectures and optimization levels—this catches silent correctness regressions that benchmarks miss.

## Incremental Compilation

Cache artifacts and track dependencies to avoid recompiling unchanged modules, speeding up the feedback loop during development without sacrificing correctness through overly aggressive caching.

## IR Validation

Validate generated IR against reference implementations and include runtime assertions for critical invariants—this catches code generation bugs early rather than letting them escape to production targets.

## Tooling & Teaching Aids

Provide AST and IR visualizers, interactive REPLs, and documentation with examples—these tools help both compiler developers and users understand the pipeline and debug problems faster.

## Performance vs. Correctness

Prioritize correctness first, then add optimizations incrementally with benchmarks to validate improvements. Document performance-correctness tradeoffs and use assertions to guard invariants.
