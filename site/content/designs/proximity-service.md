---
title: "Proximity Service (Yelp/Maps)"
description: "High-performance location-based search using geospatial indexing."
summary: "Design for finding nearby points of interest with low latency, focusing on geospatial data structures like Geohashing or Quadtrees."
tags: ["caching", "database", "geo"]
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Design a service that allows users to search for businesses or points of interest (POIs) based on their current geographic location (latitude/longitude). The system must support high-frequency updates (for moving POIs) and extremely low-latency read requests for static business data.

- **Functional Requirements:** Add/delete/update POI locations, search nearby POIs within a given radius or box.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 100 million POIs globally; 50k queries per second (QPS).
    - **Latency:** Search results returned in < 200ms.
    - **Availability:** 99.99% (read-heavy workload).
    - **Accuracy:** Precision decreases as distance increases; eventual consistency for location updates is acceptable.

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
