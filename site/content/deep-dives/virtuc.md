---
title: "VirtuC"
description: "Rust compiler for a C subset targeting LLVM IR."
summary: "Rust-implemented compiler for a C subset that emits LLVM IR and focuses on AST design, semantic checks, and IR validation for teaching."
tags: ["algorithms", "compiler", "performance", "rust"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/virtuc"
draft: false
---

## Context & Motivation

**Context:** `VirtuC` is a Rust-implemented compiler for a C subset that emits LLVM IR and produces native executables via `clang`. It serves as both an educational tool for understanding compiler internals and a testbed for exploring IR generation, optimization passes, and error reporting design.

**Motivation:** I built part of a compiler in college with [huangsam/ec2prog](https://github.com/huangsam/ec2prog), but wanted to explore a more structured approach with Rust's type system, LLVM IR generation, and modern error reporting techniques.

## The Local Implementation

- **Current Logic:** The pipeline flows through four distinct phases. Phase 1 (Lexing): `logos` tokenizes source into a typed token stream with source spans. Phase 2 (Parsing): `nom` combinators consume tokens and build a typed AST with `Span` annotations on every node. Phase 3 (Semantic Analysis): a pass over the AST resolves symbols (variable/function lookup via a scoped symbol table), checks types (integer widths, pointer compatibility, function signatures), and annotates the AST with resolved type information. Phase 4 (Codegen): `inkwell` (a safe LLVM binding) lowers the annotated AST to LLVM IR—`alloca` for locals, proper `phi` nodes for control flow merges, and correct calling conventions for function calls. The CLI compiles the IR to an object file and links with `clang`.
- **Error reporting:** diagnostics include source file, line, column, a snippet of the offending code with an underline caret, and a suggestion when possible (e.g., `"did you mean 'int'?"` for typos). The parser implements error recovery by synchronizing on statement boundaries (semicolons, closing braces), allowing it to report multiple independent errors per compilation rather than bailing on the first one. Error output is modeled after Rust's compiler—clear, actionable, and never cryptic.
- **Bottleneck:** Expanding the supported C subset (structs, unions, enums, switch statements) requires extending all four phases in coordination. Ensuring correct IR lowering for edge cases (pointer arithmetic, implicit integer promotions, short-circuit evaluation) requires both snapshot tests of emitted IR and end-to-end execution tests.

## Scaling Strategy

- **Vertical vs. Horizontal:** Not applicable in the distributed sense—focus on codebase modularity so each compiler phase can be extended independently. Incremental compilation metadata (content hashes of source files and their ASTs) enables skipping unchanged modules during rebuilds, speeding the developer feedback loop.
- **State Management:** Cache parsed ASTs and generated IR keyed by source content hash. Track inter-module dependencies (which functions/types are imported from other modules) to invalidate only affected modules when a dependency changes. Use content hashing rather than timestamps to avoid phantom rebuilds.

## Comparison to Industry Standards

- **My Project:** Small, focused compiler aimed at education and experimentation with LLVM IR. Emphasizes clear phase boundaries, readable error messages, and inspectable intermediate representations over optimization depth.
- **Industry:** Production compilers (clang, gcc) have decades of optimization passes, sophisticated register allocation, link-time optimization, and support for the full C/C++ specification. They also have extensive fuzz testing infrastructure (csmith, afl) for finding miscompilation bugs.
- **Gap Analysis:** To approach production robustness: add a verifier pass after IR generation that checks structural invariants (SSA dominance, type consistency, well-formed control flow), expand the fuzz testing suite with random program generation, implement at least basic optimization passes (constant folding, dead code elimination) gated behind `-O` flags, and add cross-compilation support for multiple target architectures.

## Risks & Mitigations

- **IR correctness bugs:** compare VirtuC's output against `clang -S -emit-llvm` for the same input programs and diff the IR. Integrate FileCheck-style assertions for IR structure. Run a verifier pass after every codegen to catch malformed IR before it reaches LLVM's backend.
- **Undefined behavior from unhandled constructs:** reject unsupported C constructs explicitly with clear error messages ("VirtuC does not support `goto`; use structured control flow") rather than silently generating wrong code. Maintain a documented list of supported vs. unsupported features.
- **Error recovery correctness:** test that parser recovery doesn't produce cascading false errors. Maintain a regression suite of multi-error programs and verify that only genuine errors are reported.
- **LLVM version drift:** pin the `inkwell`/LLVM version and test against multiple LLVM releases in CI to detect API breakage early.
