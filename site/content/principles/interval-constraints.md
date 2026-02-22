---
title: "Intervals & Constraints"
description: "Heuristics for choosing windowing strategies based on SLA tensions."
summary: "Balancing Latency (Completeness) against Verification (Integrity) by choosing between Speculative and Pessimistic intervals."
tags: ["analytics", "data-pipelines", "streaming"]
categories: ["principles"]
draft: false
---

## Choosing Intervals from Constraints

In data engineering, "Completeness" (receiving all data) and "Integrity" (validating the data is clean/final) operate on different timescales. The choice of windowing strategy—how you group and emit results—is a direct function of the gap between your **Latency SLA** (when the user must see data) and your **Integrity Window** (how long it takes for fraud, dedup, or late arrivals to settle).

When your Latency SLA is shorter than your Integrity Window, you are forced into **Speculative Windowing**. You must emit "dirty" results as soon as the window closes to satisfy the user, then emit "corrections" later as the data finalizes. Conversely, if your Latency SLA is generous, **Pessimistic Windowing** is preferred: hold the window in state until the integrity checks "seal" the interval, ensuring the first result emitted is also the final one.


- In Flink/Spark: use event-time watermarks and "allowed lateness" to control the speculation window; leverage `SideOutput` for events that arrive after the interval is "sealed."
- Cross-language: the concept of "settlement" is universal—data in motion is a series of evolving estimates until a finality threshold is reached.

**Anti-pattern — Speculative Result Blindness** — Emitting early results without a mechanism to correct them later. This leads to "Dashboard Drift," where real-time totals never match the final bill. If you speculate for speed, you must commit to the complexity of retractions.

## Pessimistic Interval Sealing

When Latency SLAs are generous enough to accommodate the full Integrity Window, **Pessimistic Windowing** provides a simpler and safer architecture. By holding the interval in the processor's state until it is "sealed," you guarantee that every event emitted is final and correct. This eliminates the need for complex retraction logic or versioned merges in the sink.

The core challenge in pessimistic windowing is determining the **Wait Threshold**—the specific point in time or signal that indicates the Integrity Window is closed and the data is safe to flush.

- In Flink/Spark: use a `WatermarkStrategy` with bounded out-of-orderness. The interval is only emitted when the watermark surpasses `window_end`.
- In Batch: the interval is naturally sealed by the job boundaries; a daily job only runs once the previous day's source data is confirmed "written" and verified.

**Anti-pattern — The Indefinite Wait** — Setting a Wait Threshold that is too long or failing to implement a timeout for slow-running integrity sidecars. This causes memory pressure in the stream processor as state for "unsealed" windows accumulates indefinitely. You must balance "absolute integrity" with "operational stability" by setting a hard cutoff for finality.

## Speculative Interval Merging

When operating in the speculative zone, the "final" result is not a single event but the **Merge** of an original estimate and one or more corrections. This requires a sink that is fundamentally commutative and idempotent. You must decide whether to overwrite previous estimates (Versioned Upsert) or adjust them (Retractions).

This pattern moves the complexity from the stream processor's memory to the storage layer's merge logic. It requires a robust "Finality Threshold"—a point in time where the system stops accepting corrections and locks the interval for audit or billing.


- In SQL/OLAP (ClickHouse, Druid): use `UPSERT` or `ReplacingMergeTree` with a version column (window_id + update_timestamp) to ensure the latest estimate wins.
- In Event Streams (Kafka): use a "Retraction Stream" pattern where the processor emits a negative event (e.g., `count: -10`) to undo a previous estimate before emitting the updated count.

**Anti-pattern — Non-Idempotent Merge** — Sending speculative corrections to a sink that only supports blind appends (e.g., a simple log). This results in double-counting or orphaned estimates. Your choice of interval strategy is a primary constraint on your choice of sink.

## Cross-principle Notes

This principle extends the **Time Semantics** section in [Data Pipelines]({{< ref "/principles/data-pipelines" >}}). For a production example of speculative intervals in action, see the **Deep Dive & Trade-offs** in the [Ad Click Aggregator]({{< ref "/designs/ad-click-aggregator" >}}), where a 1-minute reporting SLA forces the system to handle fraud corrections as late-arriving retractions.
