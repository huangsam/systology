---
title: "VirtuC"
description: "A Rust compiler for a C subset targeting the LLVM backend."
summary: "A from-scratch, Rust-implemented compiler designed for an expanding C subset (user-defined structs, multidimensional arrays, pointer semantics, rich control flow, standard headers) that emits verified LLVM IR and links native executables via clang."
tags: [algorithms, compilers, optimization, performance, systems-programming]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/virtuc"
draft: false
date: "2026-10-04T10:00:00-07:00"
---

## Context & Motivation

**Context:** `VirtuC` (driving the `vcc` CLI) is a Rust-implemented compiler for a C subset that emits LLVM IR and produces native executables via `clang`. It serves as both an educational tool for understanding compiler internals and a testbed for exploring IR generation, optimization passes, and error reporting design.

**Motivation:** I built part of a compiler in college with [huangsam/e2cprog](https://github.com/huangsam/e2cprog), but wanted to explore a more structured approach with Rust's type system, LLVM IR generation, and modern error reporting techniques.

## The Local Implementation

- **Four-Phase Modular Architecture:** The compilation pipeline flows through four modular phases:
  - **Phase 1 (Lexing):** `logos` tokenizes C source into a typed token stream with precise source span tracking. A custom lexer callback parses multi-line block comments (`/* ... */`) alongside single-line comments (`// ...`) and whitespace.
  - **Phase 2 (Parsing):** `nom` parser combinators consume tokens to construct a strongly-typed AST, annotating every statement and expression with `Span` metadata for downstream diagnostics.
  - **Phase 3 (Semantic Analysis):** Resolves symbols across scoped symbol tables, verifies types, enforces type coercion and compatibility, checks function signatures, and validates pointer/array/struct semantics.
  - **Phase 4 (Codegen):** `inkwell` (safe LLVM bindings) lowers the annotated AST into standard LLVM IR: allocating stack slots via `alloca`, structuring control flow with basic blocks and `phi` nodes, computing struct offsets, and setting up calling conventions for native linking via `clang`.
- **Supported C Language Subset:**
  - **User-Defined Structs:** Full support for `struct` declarations (`struct Point { int x; int y; };`), struct variable instances, pointer-to-struct types, and member field access via both direct dot (`pt.x`) and pointer arrow (`ptr->y`) operators. Lowered to composite LLVM structure types with targeted `getelementptr` instructions.
  - **Types & Memory:** Supports 64-bit `int`, 64-bit `float`, `void` return types and void functions, pointer types (`T*`), fixed-size 1D arrays (`T arr[N]`), and 2D arrays (`T matrix[R][C]`). Array parameters automatically decay to pointer types during function calls. Pointer operations support address-of (`&`), dereference (`*`), and pointer arithmetic. Nested array indexing (`matrix[i][j]`) lowers to chained LLVM `getelementptr` instructions with explicit boundary type checks.
  - **Operators & Expressions:** Full arithmetic support (`+`, `-`, `*`, `/`, `%`), unary negation and logical NOT (`-`, `!`), prefix and postfix increment/decrement (`++`, `--`), compound assignments (`+=`, `-=`, `*=`, `/=`, `%=`), and short-circuiting logical operations (`&&`, `||`) compiled via conditional branch execution.
  - **Control Flow:** `if`/`else` branching, `while` loops, `for` loops (including omitted clauses such as `for (;;) {}`), and jump statements (`break`, `continue`) managed via an active loop basic block stack.
  - **Standard Headers & Externs:** Native interop with `#include <stdio.h>` (`printf`, `puts`, `putchar`), `#include <stdlib.h>` (`exit`, `abs`), and `#include <math.h>` (`sqrt`, `pow`, `floor`, `ceil`, `sin`, `cos`).
- **Compiler CLI (`vcc`):** The driver binary is packaged as `vcc`, providing an ergonomic command-line interface for compiling `.c` files directly to LLVM IR (`-emit-llvm`) or native platform binaries.
- **Error Reporting & Diagnostics:** Compiler errors output the source file, line, column, an underline caret highlighting the offending span, and contextual suggestions (e.g., `"did you mean 'int'?"`). The parser synchronizes on statement boundaries (semicolons, closing braces) to report multiple independent diagnostics in a single run.
- **Verification & Test Rigor:** Testing is organized under a modular integration suite. This includes dedicated struct test suites (`struct_cases`), standalone algorithm fixtures (`algo_cases` executing sorting, searching, and recursion), CLI binary execution tests (`cli`), and negative diagnostic tests verifying compile-time error rejection and span precision.
- **Bottleneck:** While core imperative constructs, multi-dimensional arrays, pointers, and user structs are fully operational, expanding into unions, enums, and `switch` statements requires further schema expansions across all four compiler phases.

## Comparison to Industry Standards

- **My Project:** A modular, educational compiler in Rust focusing on clear phase boundaries, rich error diagnostics, and inspectable LLVM IR generation for an expressive C subset.
- **Industry:** Production compilers (`clang`, `gcc`) handle the full C/C++ specification with multi-stage optimization pipelines, vectorization, link-time optimization (LTO), and extensive sanitizers/fuzzers (`csmith`, `afl`).
- **Gap Analysis:** With structs, arrays, pointers, loop controls, and standard library headers now in place, the primary architectural milestones are `switch` dispatch lowering, an LLVM IR verification pass before object emission, and configurable optimization flags (`-O1`, `-O2`).

## Risks & Mitigations

- **IR correctness bugs:** compare VirtuC's output against `clang -S -emit-llvm` for identical C programs and diff the IR. Run LLVM module verification before lowering to catch structural or SSA violations early.
- **Undefined behavior from unhandled constructs:** reject unsupported C constructs explicitly with clear diagnostic messages rather than silently emitting flawed IR.
- **Error recovery correctness:** test that parser synchronization doesn't cascade false positives across statement boundaries. Maintain dedicated negative integration test suites verifying exact error outputs.
- **LLVM version drift:** pin the `inkwell`/LLVM version and test against multiple LLVM releases in CI to detect API breakage early.
