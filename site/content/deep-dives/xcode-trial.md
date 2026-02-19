---
title: "xcode-trial"
description: "iOS/macOS development with app architecture."
summary: "Multimodal video analysis on macOS using AVFoundation, Vision, and Core Image — extracts faces, scenes, colors, motion, audio, and text with JSON output."
tags: ["concurrency", "feature-extraction", "media"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/xcode-trial"
draft: false
---

## Context & Motivation

**Context:** `xcode-trial` is a Swift-based multimodal video analysis tool leveraging Apple-native frameworks—AVFoundation for media IO, Vision for computer vision tasks (face detection, scene classification, text recognition), and Core Image for image transforms. It targets macOS 15.0+ and Xcode 26.0+, producing JSON output for downstream analysis.

**Motivation:** I always wanted to see how Apple-native frameworks could be combined to perform comprehensive video analysis on macOS, leveraging hardware acceleration and modern Swift features while maintaining modularity and reproducibility.

## The Local Implementation

- **Current Logic:** Swift Package Manager project structured as a pipeline: video and image inputs are processed through multiple analysis tracks—Vision `VNDetectFaceRectanglesRequest` for face detection, `VNClassifyImageRequest` for scene classification, Core Image filters for color and visual analysis, plus motion and audio extraction via AVFoundation. Each track processes media independently and produces structured feature records. Results are aggregated and output as JSON per input file.
- **Framework integration:** the project demonstrates how Vision, AVFoundation, and Core Image complement each other. Vision handles high-level recognition tasks (faces, scenes, text), AVFoundation provides media decoding and audio analysis, and Core Image enables image-level feature extraction. SPM manages the build with clean dependency boundaries.
- **Hardware acceleration:** Core Image filters and Vision requests automatically route to the GPU on Apple Silicon when available. The pipeline benefits from Apple's integrated hardware without requiring explicit Metal or Neural Engine configuration.
- **Bottleneck:** Vision pipeline latency varies per request type—face detection, scene classification, and text recognition have different computational profiles. Coordinating results from multiple analysis tracks while preserving structure adds complexity. macOS version differences affect API availability for certain Vision request types.

## Scaling Strategy

- **Vertical vs. Horizontal:** Optimize for Apple Silicon—the frameworks automatically leverage GPU and hardware acceleration. For larger workloads (processing video libraries), run job-level parallelism across multiple macOS machines, with each handling a subset of files. Apple's frameworks are optimized for single-machine throughput on their own hardware.
- **State Management:** Per-video checkpoints store the last processed frame index and accumulated features, enabling resume after interruption. Chunked processing (5-minute segments) bounds memory and allows intermediate result persistence for long videos.

## Comparison to Industry Standards

- **My Project:** Native macOS analysis leveraging Apple's Vision, AVFoundation, and Core Image frameworks for multimodal extraction. JSON output for downstream compatibility. Built with SPM for clean dependency management.
- **Industry:** Cloud video analysis (Google Video Intelligence, AWS Rekognition) offers managed scaling and broader model coverage but lacks Apple-specific optimizations and incurs data egress costs and privacy implications. FFmpeg + OpenCV provides cross-platform portability but misses Metal/Neural Engine acceleration.
- **Gap Analysis:** For production deployment: add SPM artifact caching and CI on macOS runners (GitHub Actions macOS, Buildkite Mac), implement schema versioning for downstream ML ingestion, and add structured error handling for partial analysis failures (e.g., Vision request fails on corrupted frames but pipeline continues).

## Risks & Mitigations

- **API drift across macOS versions:** pin minimum macOS version and Xcode version, add CI matrix jobs across macOS versions. Vision API availability varies by version—use `#available` checks and provide fallback paths.
- **Memory pressure on long videos:** stream frames with a bounded buffer and release resources eagerly. Monitor with `os_signpost` to detect memory pressure events.
- **CI environment constraints:** macOS CI runners may have limited GPU access. Ensure the pipeline degrades gracefully when hardware acceleration is unavailable, falling back to CPU-based processing with clear logging of the compute path.
