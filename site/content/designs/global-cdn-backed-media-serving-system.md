---
title: "Global CDN-Backed Media Serving System"
description: "Distributed media delivery worldwide"
summary: "CDN-backed media delivery architecture for low-latency, highly-available global media serving with background upload processing."
tags: ["design","cdn","media","performance","networking","monitoring"]
---

## 1. Problem Statement & Constraints

Develop a global media serving system that efficiently delivers static and dynamic assets worldwide using a content delivery network, while handling background processing for user uploads. The architecture must optimize for low latency, high availability, and cost-effectiveness, ensuring secure and reliable access to media content across diverse geographic regions.

- **Functional Requirements:** Serve static/media assets globally, with background processing for uploads.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** 1M requests/sec, global distribution.
    - **Availability:** 99.99%.
    - **Consistency:** Eventual for media updates.
    - **Latency Targets:** P99 < 100ms.

## 2. High-Level Architecture

{{< mermaid >}}
graph LR
  Users[Users] --> CDN[CDN Edge Locations]
  CDN --> Origin[Origin Server]
{{< /mermaid >}}

## 3. Deep Dive & Trade-offs

Lorem ipsum dolor sit amet.

## 4. Operational Excellence

Lorem ipsum dolor sit amet.
