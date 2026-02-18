---
title: "Ad Click Aggregator"
description: "Real-time big data processing for ad events."
summary: "Design for aggregating ad clicks at massive scale, focusing on deduplication, exactly-once processing, and low-latency reporting."
tags: ["analytics", "streaming"]
categories: ["designs"]
draft: true
---

## 1. Problem Statement & Constraints

Design a system to aggregate millions of ad click events in real-time to provide up-to-the-minute reporting for advertisers. The system must handle high-volume streams, filter out fraudulent or duplicate clicks, and ensure that click counts are accurate for billing purposes.

- **Functional Requirements:** Aggregate clicks by ad ID and time window (e.g., 1 minute), detect/filter duplicates, provide an API for real-time query results.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 10 billion click events per day (peak 200k events/sec).
    - **Latency:** End-to-end data delay (event time to ingestion in report) < 1 minute.
    - **Accuracy:** Exactly-once semantics for billing; hyper-accurate counts (probabilistic structures acceptable for pre-aggregation).
    - **Fault Tolerance:** Robustness against regional outages or stream spikes.

## 2. High-Level Architecture

Include a diagram and brief component responsibilities.

{{< mermaid >}}
graph LR
  Client --> API[API Layer]
  API --> Worker[Worker/Workers]
  Worker --> Store[(Data store)]
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

Describe key components, data model, and interfaces.

## 4. Operational Excellence

List SLIs/SLOs, monitoring/alerting strategy, and any operational considerations (e.g., canary releases, rollbacks, etc.).
