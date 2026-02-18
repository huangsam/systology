---
title: "Flash Sale / Ticketmaster"
description: "High-concurrency inventory management for massive traffic spikes."
summary: "Design for handling extreme bursts of traffic where limited inventory must be distributed fairly and consistently under heavy load."
tags: ["concurrency", "database", "distributed-systems"]
categories: ["designs"]
---

## 1. Problem Statement & Constraints

Design a ticketing or flash sale system capable of handling millions of users simultaneously trying to purchase a limited set of items (e.g., concert tickets). The system must prevent over-selling, ensure fair access (e.g., virtual waiting rooms), and maintain stable performance during extreme traffic bursts.

- **Functional Requirements:** Browse inventory, reserve items, complete purchases, and manage a "waiting room" queue.
- **Non-Functional Requirements (NFRs):**
    - **Scale:** Handle 1 million concurrent users at the start of a sale.
    - **Latency:** Inventory check and reservation in < 500ms under peak load.
    - **Consistency:** Linearizable consistency for inventory counts; no double-selling.
    - **Availability:** 99.99% for the duration of the sale event.

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
