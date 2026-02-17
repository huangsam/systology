---
title: "Monitoring & Observability"
description: "Metrics, logging, tracing, alerting for observable systems."
summary: "Best practices for metrics, structured logging, tracing, alerting, and SLO-driven reliability."
tags: ["monitoring"]
categories: ["principles"]
---

1. Metrics & KPIs
    - Emit structured metrics for throughput, latency, error rates, and resource utilization.
    - Use consistent naming conventions and labels for aggregation and filtering.
    - Track both technical metrics (CPU, memory) and business KPIs (processing rate, job completion).

2. Structured Logging
    - Use structured logs (JSON) with consistent fields: timestamp, level, correlation ID, message.
    - Include contextual information like user IDs, request IDs, and workflow stages.
    - Design logs as event streams for centralized collection and analysis.

3. Distributed Tracing
    - Add trace IDs and span IDs across service boundaries for end-to-end request tracking.
    - Instrument critical paths to identify bottlenecks in distributed systems.
    - Use tools like OpenTelemetry for standardized tracing.

4. Alerting & SLOs
    - Define Service Level Objectives (SLOs) and error budgets for critical systems.
    - Set up automated alerts for threshold violations and anomalies.
    - Avoid alert fatigue by tuning thresholds and using multi-window detection.

5. Health Checks & Readiness
    - Implement health endpoints that check dependencies (database, cache, external APIs).
    - Differentiate between liveness (is the service running?) and readiness (can it handle traffic?).
    - Include version and build information in health responses.

6. Resource Profiling
    - Profile CPU, memory, and IO usage to identify hotspots and optimize performance.
    - Use continuous profiling in production to catch regressions.
    - Monitor state size growth in stateful systems (Flink, Spark).

7. Observability in Data Pipelines
    - Track backlog sizes, processing lag, and watermark progression for streaming jobs.
    - Emit partition-level metrics to detect skew and bottlenecks.
    - Monitor checkpoint duration and failure rates for fault tolerance health.

8. Dashboard & Visualization
    - Build operational dashboards showing key metrics and system health.
    - Provide drill-down views for debugging specific jobs or requests.
    - Use time-series visualization for trend analysis and capacity planning.

9. Error Budget & Postmortems
    - Track error budgets to balance feature velocity and reliability.
    - Conduct blameless postmortems after incidents to identify systemic issues.
    - Document runbooks and recovery procedures for common failure modes.

10. Cost Monitoring
    - Track infrastructure costs by service, environment, and resource type.
    - Monitor egress, storage, and compute costs for cloud workloads.
    - Set budget alerts and forecast spending based on usage trends.

11. Development & Testing Observability
    - Include debug/verbose logging modes for local development.
    - Provide test fixtures that emit metrics and logs for validation.
    - Use observability data to validate system behavior in integration tests.

12. Privacy & Compliance
    - Scrub sensitive data (PII, credentials) from logs and metrics.
    - Implement retention policies for logs and traces.
    - Document what data is collected and how long it's retained.
