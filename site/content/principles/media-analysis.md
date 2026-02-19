---
title: "Media Analysis"
description: "Feature extraction and real-time handling for media data."
summary: "Best practices for media feature extraction: stable schemas, streaming vs. batch modes, metadata preservation, and performance engineering."
tags: ["feature-extraction", "media"]
categories: ["principles"]
draft: false
---

## Define Stable Output Schema

Design versioned JSON schemas for consistent downstream consumption with clear field semantics. Schema changes are costly downstream, so explicit versions and migrations matter more than backwards compatibility.

## Cross-platform vs. Native

Use cross-platform C++/OpenCV for portable batch pipelines but leverage native APIs (Metal, Vision) for optimized on-device work. Portability and performance pull in different directions.

## Stream vs. Batch Processing

Implement streaming decode for long videos to avoid loading entire files into memory, and use batch processing with worker queues for archives. Support both modes with configurable buffers to avoid surprises.

## Metadata Preservation

Preserve EXIF data, timestamps, and codec information alongside analysis results and record processing parameters for reproducibility. Metadata enables audit trails and helps trace data provenance.

## Performance Engineering

Profile decode, transform, and inference operations to find actual bottlenecks rather than guessing. Hardware acceleration (GPU, SIMD) and request batching multiply throughput but require measurement to pay off.

## Calibration & False Positives

Provide tools for threshold tuning and include labeled test datasets for validation. False positives multiply costs downstream; invest in calibration to reduce them.

## Packaging & Distribution

Build wheels and native binaries for easy installation and provide CI/CD for cross-platform testing. Installation friction determines adoption; make it trivial.

## Privacy & On-device Processing

Prefer on-device processing for sensitive media with clear documentation of what data leaves the device. Privacy violations are hard to repair; design for it upfront.
