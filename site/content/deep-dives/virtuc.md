---
title: "VirtuC"
description: "Virtualization for system isolation."
summary: "Rust-implemented compiler for a C subset that emits LLVM IR and focuses on AST design, semantic checks, and IR validation for teaching."
tags: ["compiler", "rust"]
categories: ["deep-dives"]
github: "https://github.com/huangsam/virtuc"
draft: false
---

## Context — Problem — Solution

**Context:** `VirtuC` is a Rust-implemented compiler for a C subset that emits LLVM IR and produces native executables via `clang`.

**Problem:** Building a correct, maintainable compiler pipeline requires clear AST design, sound semantic checks, and robust error reporting while keeping codegen predictable and debuggable.

**Solution (high-level):** Solidify AST and type-system invariants, add regression tests and IR-level validation, and provide tooling to visualize compilation phases for teaching and debugging.

## 1. The Local Implementation

- **Current Logic:** Uses `logos` + `nom` for lexing/parsing, builds an AST, runs semantic analysis (type checking, symbol resolution), then emits LLVM IR via `inkwell`. The CLI compiles and links with `clang`.
- **Bottleneck:** Complex language features expand semantic checks; ensuring correct IR lowering for edge cases needs coverage and test harnesses.

## 2. Scaling Strategy

- **Vertical vs. Horizontal:** Not applicable in the typical sense — focus on codebase modularity to support new language features and incremental compilation to speed rebuilds.
- **State Management:** Add incremental compilation metadata (hashes of source/AST) to skip unchanged modules and provide persistent caches for generated IR.

## 3. Comparison to Industry Standards

- **My Project:** Small, focused compiler aimed at education and experimentation with LLVM IR.
- **Industry:** Mature compilers (clang/gcc) provide highly-optimized codegen and sophisticated optimizers.
- **Gap Analysis:** To approach production compiler robustness requires extensive test suites, IR optimizations, and careful integration with platform toolchains.

## 4. Experiments & Metrics

- **Correctness:** comprehensive test cases covering parsing, semantic checks, and codegen output validation.
- **Performance:** compile time for large codebases and runtime performance of generated executables.
- **Incremental build gains:** time saved with cache-enabled incremental builds.

## 5. Risks & Mitigations

- **IR correctness bugs:** run `clang -S` comparisons and lit-style tests; integrate `FileCheck`-like assertions.
- **Undefined behavior from unhandled constructs:** add graceful error messages and reject unsupported constructs explicitly.

## Related Principles

- [Compiler Design](/principles/compiler): Clean IR boundaries, deterministic semantics, error reporting, test harnesses, and incremental compilation.
- [Algorithms & Performance](/principles/algorithms-performance): Profiling-driven optimization and memory discipline for codegen.
