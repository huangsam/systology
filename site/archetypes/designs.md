---
title: "Short title"
description: "Short description"
summary: "One-line summary used on index pages"
tags: []
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Write a concise problem statement and clearly list hard constraints (SLA, budget, data residency, latency, etc.).

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
