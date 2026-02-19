---
title: "Grit"
description: "VCS implementation with plumbing/porcelain architecture."
summary: "From‑scratch Git implementation in Rust focusing on object storage, performance, and plumbing/porcelain command compatibility."
tags: ["algorithms", "extensibility", "performance", "rust", "vcs"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/grit"
draft: false
---

## Context — Problem — Solution

**Context:** `Grit` is a from-scratch Git implementation in Rust, providing both low-level plumbing commands (hash-object, cat-file, write-tree) and high-level porcelain commands (init, add, commit, log, status, diff, reset). The architecture follows Git's own layered design where porcelain is composed entirely from plumbing primitives.

**Problem:** Building a performant VCS requires efficient object storage (SHA-1 hashing, zlib compression, loose objects), intelligent caching to avoid redundant IO for repeated object lookups, and correct implementations of staging, diffing, and history traversal. Grit uses its own `.grit/` directory rather than `.git/`, establishing it as its own VCS rather than a drop-in Git replacement.

**Solution (high-level):** Leverage Rust's ownership model for safe concurrent object access, implement LRU caching for objects and trees to amortize IO costs, use buffered read/write for all disk operations, and provide comprehensive test coverage with property-based testing (proptest) and compatibility tests against real Git repositories.

## The Local Implementation

- **Current Logic:** The object model implements blobs, trees, and commits as typed Rust structs with SHA-1 hashing and zlib compression. Objects are stored in Git's canonical format (header + content, compressed with flate2) in `.grit/objects/`. The index (staging area) maintains a sorted list of entries with file mode, path, and object hash, compatible with Git's index format. Porcelain commands compose plumbing operations: `grit add` calls `hash-object` to store file content, then updates the index; `grit commit` calls `write-tree` to serialize the index into a tree object, then creates a commit object with parent references.
- **Plumbing/porcelain split:** this layering is the core architectural decision. Plumbing commands (`hash-object`, `cat-file`, `write-tree`, `read-tree`, `update-ref`) each do one thing and expose it via both CLI and library API. Porcelain commands (`add`, `commit`, `status`, `log`, `diff`, `reset`) are implemented exclusively by composing plumbing functions—no porcelain command accesses `.grit/` directly. This means power users and scripts can automate at the plumbing level, and every porcelain command is testable by verifying its plumbing calls.
- **LRU caching strategy:** an LRU cache (`lru` crate, default 1024 entries) sits between object read requests and disk IO. Object lookups first check the cache by SHA; cache misses decompress from disk and populate the cache. Tree objects are cached separately since they're frequently re-read during status and diff operations (walking the tree for every `status` call without caching would read the same tree objects O(depth × files) times). Cache hit rates typically exceed 80% for `status` and `log` on repositories with stable working trees.
- **Bottleneck:** Full Git compatibility for complex operations (merge, rebase, worktrees) requires significant additional implementation. Performance scaling for large repositories (100k+ objects) depends on efficient packfile support, which is not yet implemented—all objects are stored loose. Status checks on large working trees require efficient filesystem traversal with `.gritignore` pattern support.

## Scaling Strategy

- **Vertical vs. Horizontal:** Focus on single-machine performance with aggressive caching and parallelized filesystem operations. For `status`, parallel stat() calls across working tree files using Rayon, with the index serving as the expected-state reference. For `log`, lazy object loading—only decompress commit messages when needed for display.
- **State Management:** LRU caches are persistent per CLI invocation (not across runs, for correctness). Incremental operations (add, status) read only changed entries by comparing working tree mtimes against the index.

## Comparison to Industry Standards

- **My Project:** High-performance, educational Git implementation emphasizing the plumbing/porcelain architecture, LRU caching for read performance, and property-based correctness testing. Achieves 3–4× speedups over Git on small-repo micro-benchmarks (init ~2.1ms at 4.1×, add ~4.1ms at 3.4×, status ~5.4ms at 3.3×, commit ~6.0ms at 4.2×) due to lower startup overhead and the Myers diff algorithm implementation.
- **Industry:** Git itself is highly optimized with decades of development—packfile deltification, bitmap indices for reachability, and multi-pack-index for large repos. Libgit2 provides a C library with comprehensive API coverage. Gitoxide (another Rust implementation) targets full compatibility with extensive packfile support.
- **Gap Analysis:** To approach Git's robustness: implement packfile support (delta compression, pack-index) for storage efficiency on large repos, add `merge` and `rebase` with three-way merge algorithms, support `.gritignore` patterns for status filtering, and implement `fetch`/`push` with Git's smart HTTP and SSH transport protocols.

## Experiments & Metrics

- **Performance benchmarks:** Criterion micro-benchmarks comparing `grit init`, `grit add`, `grit status`, `grit commit`, and `grit log` against standard Git on repositories of varying sizes (10, 100, 1k, 10k files). Measure both cold (empty cache) and warm (populated cache) performance.
- **Cache efficiency:** LRU hit rates and memory usage for different cache sizes (256, 512, 1024, 4096 entries) under `status` and `log` workloads. Find the knee where increasing cache size yields diminishing returns.
- **Correctness:** property-based tests with proptest for round-trip serialization (object → bytes → SHA → decompress → object), index sorting invariants, and tree construction. Integration tests that create a repository with `grit` and verify it's readable by standard Git (and vice versa).
- **Compatibility:** maintain a suite of Git repositories (empty, shallow, deep history, binary files, symlinks) and verify that `grit` reads and writes them correctly by comparing object hashes and ref states.

## Risks & Mitigations

- **Compatibility issues:** strict adherence to Git's object and index formats with byte-level tests. Run `grit` operations on repositories created by Git and verify with `git fsck` that no corruption is introduced.
- **Performance regressions:** Criterion benchmarks run in CI with statistical comparison. Alert on P95 regressions exceeding 5%. Monitor cache hit rates—a sudden drop indicates a code change is bypassing the cache.
- **Large repo degradation:** without packfiles, storage grows linearly with object count. Document the current limitation and provide a roadmap for packfile support. In the interim, recommend `grit` for repositories under 10k objects.
- **Index corruption:** validate index invariants (sorted entries, no duplicates, valid modes) on every read and write. Fail fast with a clear error rather than silently producing a malformed index that Git can't read.
