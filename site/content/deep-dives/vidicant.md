---
title: "Vidicant"
description: "Video processing for media pipelines."
summary: "Cross-platform video/image feature extractor (C++ core, Python bindings) for ML preprocessing focusing on throughput, accuracy, and packaging."
tags: ["media","video","feature-extraction","extensibility"]
categories: ["deep-dives"]
---

## Context — Problem — Solution

**Context:** `vidicant` extracts image and video features using C++ core and Python bindings (pybind11) to serve ML preprocessing and batch analysis.

**Problem:** Processing large media collections requires balancing IO, algorithm accuracy (motion / blur / color), and cross-platform packaging/ABI compatibility.

**Solution (high-level):** Optimize core algorithms for batch throughput, expose a stable Python API with well-defined output schemas, and provide packaging channels (wheels, binaries) per platform.

## 1. The Local Implementation

- **Current Logic:** C++ code uses OpenCV for feature extraction; Python bindings provide `process_image` and `process_video` APIs. CLI exists for batch runs and a simple output JSON schema is produced.
- **Bottleneck:** IO-bound video decoding, memory usage for long videos, and tuning motion/blur heuristics to avoid false positives.

## 2. Scaling Strategy

- **Vertical vs. Horizontal:** Parallel worker pools per-file with careful CPU/GPU binding; use streaming decode to limit memory. For large datasets, split by file ranges and run across multiple machines or containers.
- **State Management:** Track processed files via a job-state DB (SQLite/Postgres) and checkpoint per-file progress for resumability.

## 3. Comparison to Industry Standards

- **My Project:** Lightweight cross-platform extractor prioritizing speed and Python UX.
- **Industry:** Cloud video processing services offer managed pipelines and auto-scaling, but require data egress and cost trade-offs.
- **Gap Analysis:** For large-scale media pipelines, integrate with cloud object stores and worker autoscaling; for on-prem needs, focus on packaging and native acceleration (Metal/FFmpeg optimizations).

## 4. Experiments & Metrics

- **Throughput:** files/hour for different worker counts and video lengths.
- **Detection quality:** precision/recall for motion, face, and blur detection on labeled subsets.
- **Resource usage:** per-file memory and decode CPU cost.

## 5. Risks & Mitigations

- **Platform packaging friction:** provide CI-built wheels and homebrew/cmake instructions for macOS, Linux, Windows.
- **False positives in detection:** provide calibration tools and thresholding per-dataset.

## See Also

- [xcode-trial](/deep-dives/xcode-trial): Native macOS video analysis as counterpart to cross-platform approach.
- [Photohaul](/deep-dives/photohaul): Similar media handling concerns for photos with EXIF preservation.
