---
title: "Vidicant"
description: "Video processing for media pipelines."
summary: "Cross-platform video/image feature extractor (C++ core, Python bindings) for ML preprocessing focusing on throughput, accuracy, and packaging."
tags: ["extensibility", "feature-extraction", "media"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/vidicant"
draft: false
---

## Context — Problem — Solution

**Context:** `vidicant` is a cross-platform video and image feature extractor with a C++ core (OpenCV) and Python bindings via pybind11. It serves ML preprocessing pipelines by extracting motion, blur, color, and face features from media files, producing structured JSON output for downstream training and analysis.

**Motivation:** After experimenting with xcode-trial, I wanted to create a cross-platform solution that could handle large-scale video preprocessing for ML pipelines, leveraging C++ for performance-critical tasks and Python for ease of use and integration.

## The Local Implementation

- **Current Logic:** C++ core uses OpenCV's `VideoCapture` (with FFmpeg backend) for sequential, file-based frame extraction and implements feature extractors: frame difference for motion detection, Laplacian variance for blur scoring, color k-means clustering for color analysis, and edge detection. For video files, it extracts frame count, FPS, resolution, duration, and motion detection metrics by reprocessing the file for each metric. Each analysis operation (motion score, dominant colors, scene detection) reopens the video and reads a limited sample (50-100 frames) for performance. pybind11 binds these as `process_image(path) -> dict` and `process_video(path, opts) -> dict` Python callables, handling type conversions (cv::Mat ↔ numpy array) at the boundary. An interface-based design (`IImageLoader`/`IVideoLoader`) provides clean abstraction over the processing pipeline. A CLI wraps the Python API for batch runs with glob patterns and outputs per-file JSON.
- **C++/Python boundary design:** pybind11 bindings are defined in a single `vidicant_py.cpp` that exposes the high-level functions—not the internal OpenCV types. Python callers never handle `cv::Mat` directly; the binding layer converts results to dicts and numpy arrays. Error handling maps C++ exceptions to Python exceptions with meaningful messages. This follows the principle of wrapping once, correctly, idiomatically—rather than exposing raw FFI.
- **Bottleneck:** IO-bound video decoding dominates processing time for large files (60%+ of wall-clock time for 1080p video) due to sequential file-based decoding and redundant reopens across multiple analysis passes. Memory usage is controlled by sampling only the first 50-100 frames per metric, avoiding full video decoding. Heuristic detectors (blur, motion) require per-dataset threshold tuning to avoid false positives—a hardcoded threshold calibrated on professional video flags most smartphone footage incorrectly.

## Scaling Strategy

- **Vertical vs. Horizontal:** Thread-pool workers process files in parallel (one file per worker, configurable concurrency). Within each file, sampling the first 50-100 frames keeps memory constant and decoding time bounded. For large datasets, split file lists across containers or machines and merge JSON outputs; each worker is stateless with respect to other files.
- **State Management:** Track processed files via a job-state DB (SQLite for local, Postgres for shared) with per-file status (`PENDING` → `PROCESSING` → `DONE` | `FAILED`). Skip already-processed files on re-runs for incremental batch processing. Store processing parameters (thresholds, model versions) alongside results for reproducibility.

## Comparison to Industry Standards

- **My Project:** Lightweight cross-platform extractor prioritizing speed and Python UX. Single binary/wheel distribution with no cloud dependencies. Focused on preprocessing features for ML pipelines.
- **Industry:** Cloud video processing services (Google Video Intelligence, AWS Rekognition Video) offer managed pipelines with auto-scaling and broader model coverage, but require data egress, incur per-minute costs, and introduce privacy concerns for sensitive media. FFmpeg-based pipelines offer similar portability but lack integrated ML feature extraction.
- **Gap Analysis:** For large-scale production media pipelines, integrate with cloud object stores (S3/GCS) for input/output, add worker autoscaling (Kubernetes HPA on queue depth), and build a calibration suite for threshold tuning per-dataset. For on-prem deployments, focus on native acceleration (FFmpeg hardware decoders, CUDA where available).

## Risks & Mitigations

- **Platform packaging friction:** CI builds wheels using scikit-build-core with CMake `FetchContent` for pybind11 integration. Provide cmake instructions as fallbacks for source builds. Test installation in CI on clean environments to catch missing native dependencies.
- **False positives in detection:** ship a calibration CLI that sweeps thresholds against a labeled dataset and recommends operating points. Document that default thresholds are tuned for professional video and must be recalibrated for other content types.
- **ABI compatibility:** pin OpenCV version in the build and statically link core dependencies into wheels to avoid system library conflicts. Run binary compatibility tests across target platforms in CI.
- **pybind11 version drift:** pin pybind11 version and test against minimum and latest supported Python versions (3.9–3.12) in the CI matrix.
