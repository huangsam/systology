---
title: "Video Transcoding & Streaming Pipeline"
description: "Video transcoding through distributed pipeline."
summary: "An inherently scalable video ingestion and transcoding system architecture; asynchronously chunking heavy media, extracting actionable features, and steadily outputting adaptive bitrates via worker pools."
tags: ["data-pipelines", "distributed-systems", "media", "streaming"]
categories: ["designs"]
draft: false
date: "2026-02-24T22:34:51-08:00"
---

## Problem Statement & Constraints

Design a video processing platform (like YouTube or Netflix) capable of ingesting high-definition raw video uploads, processing them asynchronously, and producing Adaptive Bitrate Streaming (ABS) ready artifacts (like HLS/DASH).

### Functional Requirements

- Ingest raw video uploads resiliently.
- Asynchronously process video into multiple resolutions (1080p, 720p, 480p).
- Extract necessary metadata, thumbnails, and audio features.
- Publish processed artifacts to a CDN for streaming.

### Non-Functional Requirements

- **Scale:** Handle thousands of concurrent uploads; petabytes of storage.
- **Availability:** Ensure no data loss upon successful upload (durability).
- **Latency:** Target 1:1 processing time (e.g., a 10-minute video processes in < 10 minutes).
- **Workload Profile:**
    - Extremely IO-bound (high network ingress/egress for video files) and CPU-bound (FFmpeg transcoding).

## High-Level Architecture

{{< mermaid >}}
graph TD
    Users --> GW[API Gateway]
    GW --> Uploader[Upload Service]
    Uploader --> RawStorage[Raw Object Store]
    Uploader --> Queue[Kafka/Message Queue]
    Queue --> Chunker[Chunking Service]
    Chunker --> ChunkStorage[Chunk Object Store]
    Chunker --> TaskQueue[Job Queue]
    TaskQueue --> Workers[Transcoder Worker Pool]
    Workers --> Merger[Merger Service]
    Merger --> CDNStorage[CDN Origin Store]
{{< /mermaid >}}

The architecture splits the massive problem of transcoding a single large file into a MapReduce-like pattern. An initial service splits the video into small chunks (e.g., 5 seconds each). A horizontally scaled worker pool processes these chunks independently. Finally, a merger service reassembles the processed chunks into continuous streaming manifests.

## Data Design

### Storage Layers
- **Raw Object Store (S3-compatible):** Stores the original user upload. Usually configured for high durability (Standard tier).
- **Chunk Object Store:** Temporary cache for intermediate 5-second raw chunks. Requires high throughput/low latency as workers constantly pull from here.
- **CDN Origin Store:** The final destination for transcoded segments and `.m3u8` manifests.

### Video Metadata Schema (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **videos** | `video_id` | UUID (PK) | Unique identifier for the video. |
| | `user_id` | UUID (FK) | Owner of the video. |
| | `status` | Enum | `uploading`, `processing`, `ready`, `failed`. |
| | `raw_s3_key` | String | Path to original upload. |

### Transcode Job State
| Key Pattern (Redis/DB) | Value | Description |
| :--- | :--- | :--- |
| `task:<video_id>:<chunk_idx>:<resolution>` | Enum | `pending`, `running`, `completed`. |

## Deep Dive & Trade-offs

{{< pseudocode id="video-worker" title="Worker Node Transcoding Loop" >}}
```python
def process_transcode_task(queue, obj_store):
    while True:
        # 1. Pull the next chunk task from the queue
        task = queue.poll()
        if not task:
            continue

        try:
            # 2. Download the 5-second raw video chunk
            raw_chunk = obj_store.download(task.s3_key)

            # 3. Transcode using hardware acceleration or libx264
            transcoded_chunk = ffmpeg_transcode(raw_chunk, target_res=task.resolution)

            # 4. Upload the processed chunk to the CDN origin store
            out_key = f"processed/{task.video_id}/{task.resolution}/chunk_{task.idx}.mp4"
            obj_store.upload(out_key, transcoded_chunk)

            # 5. Acknowledge completion and update tracking DB
            queue.ack(task.id)
            update_job_status(task, "completed")

        except Exception as e:
            queue.nack(task.id) # Re-queue for another worker
            update_job_status(task, "failed")
```
{{< /pseudocode >}}

### Deep Dive

- **Chunking (Map Phase):** Instead of one server transcoding a 2-hour movie, we split it into 5-second chunks. This allows 1440 workers to process a 2-hour movie entirely in parallel.
- **Worker Pools:** The transcoders run FFmpeg. They are stateless, pulling a chunk, calculating the new resolution, and pushing the artifact. See the [Video Analysis]({{< ref "/deep-dives/video-analysis" >}}) deep-dive for extraction logic.
- **Resumable Uploads:** The edge uses multipart uploads (like S3 Multipart API) so if a user drops connection, they only retry the last 5MB chunk.
- **Adaptive Bitrate Streaming (ABS):** The system outputs fragments and a playlist file (like HLS). The client player dynamically chooses the 1080p or 480p chunks based on current network bandwidth.

### Trade-offs

- **Granularity of Chunks:** Smaller chunks (e.g., 2 seconds) yield faster parallel processing and lower stream latency, but increase the orchestration overhead and metadata storage. Larger chunks (10 seconds) optimize compression efficiency (better Keyframe distribution) but increase end-to-end processing time.
- **Hardware Acceleration vs. CPU:** Using GPU arrays (NVENC) for transcoding is blazing fast but expensive. CPU transcoding (libx264) is slower but cheaper, easier to orchestrate, and typically provides strictly better visual quality per bit.

## Operational Excellence

- SLO: 99% of 10-minute HD videos are fully available in all resolutions within 12 minutes.
- SLIs: `queue_depth`, `worker_cpu_utilization`, `upload_success_rate`.
