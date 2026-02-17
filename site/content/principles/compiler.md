---
title: "Compiler Design"
description: "Optimization, portability and resilience for compilers."
summary: "Guidelines for compiler design: clear IR boundaries, deterministic semantics, robust error reporting, and incremental compilation."
tags: ["compiler"]
categories: ["principles"]
---

1. Clean IR Boundaries
    - Maintain clear separation between AST parsing, semantic analysis, and IR lowering.
    - Define explicit invariants and contracts between each compilation stage.
    - Use intermediate representations that are easy to validate and transform.

2. Deterministic Semantics
    - Define a well-specified language subset with clear operational semantics.
    - Reject unsupported language constructs with informative error messages.
    - Ensure predictable behavior across different input programs and environments.

3. Error Reporting & UX
    - Provide source-location linked diagnostics with clear explanations.
    - Include recovery suggestions and examples for common errors.
    - Design error messages for both compiler developers and end users.

4. Test Harnesses
    - Use filecheck-style tests to verify IR and codegen outputs.
    - Maintain regression test suites covering edge cases and error conditions.
    - Automate testing across different target architectures and optimization levels.

5. Incremental Compilation
    - Cache intermediate artifacts to avoid redundant work on unchanged modules.
    - Implement dependency tracking for efficient rebuilds during development.
    - Support partial recompilation for faster iteration cycles.

6. IR Validation
    - Validate generated IR using existing toolchains and verification passes.
    - Compare compiled behavior against reference implementations or specifications.
    - Include runtime checks and assertions for generated code correctness.

7. Tooling & Teaching Aids
    - Provide AST and IR visualizers for debugging and learning.
    - Include interactive REPLs for exploring language features.
    - Document the compilation pipeline with examples and tutorials.

8. Performance vs Correctness
    - Prioritize correctness; add optimizations incrementally and protect with tests.
    - Use benchmarks to validate that optimizations produce measurable improvements.
    - Document performance-correctness trade-offs and guard invariants with assertions.
