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

Include a `schema_version` field in every output document. When you need to add fields, bump the minor version and keep old fields intact. When you must remove or rename fields, bump the major version and provide a migration script. Downstream consumers can then filter on version and handle each schema explicitly rather than guessing what fields might exist.

See the [Feature ETL]({{< ref "/designs/feature-etl" >}}) design for how schema evolution applies to ML feature pipelines at scale.

**Anti-pattern — Schema-free JSON:** Emitting unversioned JSON blobs where field names and types change between releases. Downstream consumers resort to defensive `try/except` blocks around every field access, and silent failures creep in when a field is renamed from `blur_score` to `blurriness`. Explicit schemas with versions eliminate this entire class of bug.

## Cross-platform vs. Native

Use cross-platform C++/OpenCV for portable batch pipelines but leverage native APIs (Metal, Vision) for optimized on-device work. Portability and performance pull in different directions.

The decision depends on your deployment target. If you're processing media in a cloud pipeline or a heterogeneous fleet, cross-platform OpenCV gives you one codebase everywhere. If you're running on Apple devices where latency matters, Metal and Vision framework deliver hardware-accelerated performance that OpenCV can't match.

See [Vidicant]({{< ref "/deep-dives/vidicant" >}}) for a cross-platform C++ approach, and [Xcode Trial]({{< ref "/deep-dives/xcode-trial" >}}) for leveraging Apple-native APIs (Metal, Vision, Core ML) for on-device media processing.

**Anti-pattern — Lowest Common Denominator:** Using only cross-platform APIs even when 95% of your users are on one platform. You sacrifice significant performance and capabilities to serve a theoretical audience. If your data shows most processing happens on macOS, use Metal for the fast path and provide a generic fallback.

## Stream vs. Batch Processing

Implement streaming decode for long videos to avoid loading entire files into memory, and use batch processing with worker queues for archives. Support both modes with configurable buffers to avoid surprises.

For videos, streaming decode reads frames on demand using a decoder context (`cv::VideoCapture` in OpenCV, `AVAssetReader` in AVFoundation). This keeps memory constant regardless of video length. For batch processing of image archives, a worker pool processes files in parallel with a shared output sink.

**Anti-pattern — Load-then-Process:** Reading an entire 4K video file into memory before processing. A 1-hour 4K video at 60fps is ~1 TB of uncompressed frames—your process OOMs before analysis begins. Always decode incrementally, processing frame-by-frame or in small batches.

See the [Background Job Queue]({{< ref "/designs/background-job-queue" >}}) design for patterns on managing long-running media processing tasks with retries and progress tracking.

## Metadata Preservation

Preserve EXIF data, timestamps, and codec information alongside analysis results and record processing parameters for reproducibility. Metadata enables audit trails and helps trace data provenance.

When your pipeline processes an image, carry forward the original's EXIF (camera model, GPS, timestamp), the processing parameters used (blur threshold, motion sensitivity, model version), and the output features. Store this as a sidecar JSON or embedded in the output format. This lets you answer "why did the system flag this image?" months later.

**Anti-pattern — Metadata Stripping:** Silently discarding EXIF and codec data during processing because "we only need the pixels." When a downstream consumer needs to sort by capture date, geolocate images, or audit which camera produced artifacts, that metadata is irrecoverable. Preserve everything; let consumers decide what to discard.

See the [Migration & Deduplication]({{< ref "/principles/migration-dedup" >}}) principles for related guidance on metadata fidelity during large-scale file processing.

## Performance Engineering

Profile decode, transform, and inference operations to find actual bottlenecks rather than guessing. Hardware acceleration (GPU, SIMD) and request batching multiply throughput but require measurement to pay off.

Use profilers specific to media workloads: `perf` with hardware counters for CPU-bound decode, GPU profilers (NSight, Metal System Trace) for GPU inference, and IO profilers for storage-bound workflows. Typical bottleneck progression: IO (reading files from disk/network) → decode (decompressing frames) → transform (resizing, color conversion) → inference (ML model). Fix them in order.

See the [Algorithms & Performance]({{< ref "/principles/algorithms-performance" >}}) principles for broader guidance on profiling and micro-benchmarking that applies directly to media pipelines.

**Anti-pattern — GPU Cargo Cult:** Moving everything to the GPU because "GPUs are faster." Moving small images to GPU memory, running a trivial kernel, and copying back is slower than CPU processing due to transfer overhead. Profile the full pipeline including data transfer costs before committing to GPU acceleration.

## Calibration & False Positives

Provide tools for threshold tuning and include labeled test datasets for validation. False positives multiply costs downstream; invest in calibration to reduce them.

Ship a calibration CLI that takes a labeled dataset (images with known blur/motion/face ground truth) and sweeps threshold values, producing a precision-recall curve. Let users pick their operating point based on their cost of false positives vs. false negatives. Different use cases have wildly different tolerances—a security camera tolerates more false positives than a photo organizer.

**Anti-pattern — One Threshold Fits All:** Shipping a hardcoded threshold (e.g., blur score > 0.7 = blurry) without considering the variability of input data. A threshold calibrated on professional photos will flag every smartphone photo as blurry. Always expose thresholds as configurable parameters with documented calibration procedures.

## Packaging & Distribution

Build wheels and native binaries for easy installation and provide CI/CD for cross-platform testing. Installation friction determines adoption; make it trivial.

For Python libraries with native components, build manylinux wheels (using `cibuildwheel`) and macOS universal2 wheels so users can `pip install` without compiling from source. For CLI tools, provide prebuilt binaries for major platforms via GitHub Releases or Homebrew. Test installation on bare VMs in CI to catch missing dependencies.

See [Vidicant]({{< ref "/deep-dives/vidicant" >}}) for an example of managing cross-platform C++ packaging with Python bindings—where CI-built wheels and cmake instructions reduce installation friction.

**Anti-pattern — "Just Build From Source":** Requiring users to install CMake, OpenCV, and platform-specific SDKs to try your library. 90% of potential users will give up at the first compilation error. Prebuilt packages aren't just convenient—they're essential for adoption.

## Privacy & On-device Processing

Prefer on-device processing for sensitive media with clear documentation of what data leaves the device. Privacy violations are hard to repair; design for it upfront.

For applications that analyze personal photos or videos (face detection, location extraction, content moderation), process locally by default. If cloud processing is needed for heavier models, require explicit user opt-in with a clear explanation of what data is transmitted, how it's processed, and when it's deleted. Log all cloud transmissions for audit.

See the [Privacy & Agents]({{< ref "/principles/privacy-agents" >}}) principles for comprehensive guidance on consent, data minimization, and audit logging that applies directly to media processing of personal data.

**Anti-pattern — Silent Cloud Upload:** Sending images to a cloud API for analysis without informing the user. Even if the API's privacy policy is fine, the user didn't consent to their photos leaving the device. Explicit opt-in isn't just good practice—it's increasingly a legal requirement (GDPR, CCPA).
