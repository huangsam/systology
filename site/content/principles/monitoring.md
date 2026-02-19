---
title: "Monitoring & Observability"
description: "Metrics, logging, tracing, alerting for observable systems."
summary: "Best practices for metrics, structured logging, tracing, alerting, and SLO-driven reliability."
tags: ["monitoring"]
categories: ["principles"]
draft: false
---

## Metrics & KPIs

Emit structured metrics for throughput, latency, and error rates alongside business KPIs using consistent naming conventions. This provides both technical and product perspectives on system health.

Follow the RED method for services (Rate, Errors, Duration) and the USE method for resources (Utilization, Saturation, Errors). Use a consistent naming convention like `{service}_{component}_{metric}_{unit}` (e.g., `api_orders_request_duration_seconds`). Emit both counters and histograms—counters tell you *how many*, histograms tell you *how long*. Expose business KPIs (revenue per minute, signups per hour) alongside technical metrics so on-call engineers can correlate system behavior with business impact.

**Anti-pattern — Metric Overload:** Emitting thousands of high-cardinality metrics (one per user ID, one per URL path) without aggregation. This explodes storage costs, slows dashboards, and makes it impossible to find signal in the noise. Aggregate at the source: use bounded label sets (HTTP method, status code bucket, service name) and push high-cardinality data to logs or traces instead.

## Structured Logging

Use JSON logs with consistent fields (timestamp, level, correlation ID, context) and treat logs as event streams for centralized analysis. Unstructured logging is noise; structured logging enables aggregation and debugging at scale.

Every log line should include: `timestamp`, `level`, `service`, `correlation_id` (trace ID), and `message`. Add contextual fields as needed: `user_id`, `request_path`, `duration_ms`. Output as JSON so log aggregation tools (ELK, Loki, CloudWatch) can index and query fields directly. Use log levels consistently: DEBUG for development, INFO for normal operations, WARN for recoverable issues, ERROR for failures requiring attention.

**Anti-pattern — Printf Debugging in Production:** Sprinkling `print(f"got here: {data}")` throughout code and leaving it in production. These unstructured, contextless messages are impossible to filter, impossible to aggregate, and degrade logging signal-to-noise ratio. Use a structured logger from day one; the effort is minimal and the payoff is enormous.

**Anti-pattern — Logging Everything at DEBUG:** Setting production log level to DEBUG "just in case." This generates orders of magnitude more data, increases costs, and can actually cause performance issues (log serialization in hot paths). Use INFO in production and enable DEBUG selectively per-service when investigating specific issues.

## Distributed Tracing

Add trace IDs and span IDs across service boundaries to track requests end-to-end and identify latency bottlenecks in distributed systems. This is essential infrastructure for diagnosing multi-service interactions.

Instrument your services with OpenTelemetry (the industry standard), propagating trace context via HTTP headers (`traceparent`) or gRPC metadata. Each service creates spans for its work and passes the trace ID downstream. The trace collector (Jaeger, Tempo, Zipkin) assembles the full request tree, showing exactly where time was spent, which service caused the delay, and which calls failed.

See how the [Notification System]({{< ref "/designs/notification-system" >}}) design tracks notifications through priority queues, dispatchers, and channel adapters—tracing reveals which stage introduces latency.

**Anti-pattern — Tracing Only at the Edge:** Adding trace instrumentation only to the API gateway and assuming you'll figure out downstream latency from logs. Without spans from intermediate services, your trace shows a single long span with no visibility into whether the database, cache, or third-party API caused the delay.

## Alerting & SLOs

Define Service Level Objectives and error budgets for critical systems, then set up alerts on threshold violations with carefully tuned thresholds to avoid alert fatigue. An alert that fires constantly trains people to ignore alerts.

Start by defining SLIs (Service Level Indicators): request latency P99, error rate, availability. Then set SLOs: "99.9% of requests complete in < 500ms" and "error rate < 0.1% over a 7-day window." Calculate the error budget (0.1% of 7 days ≈ 10 minutes of downtime). Alert when the burn rate threatens to exhaust the error budget within the SLO period—not on instantaneous spikes.

See the operational excellence sections in the [Flash Sale]({{< ref "/designs/flash-sale" >}}) and [Ad Click Aggregator]({{< ref "/designs/ad-click-aggregator" >}}) designs for concrete SLO/SLI examples in production systems.

**Anti-pattern — Threshold on Instantaneous Values:** Alerting on `latency_p99 > 500ms` with a 1-minute window. A single slow garbage collection pause triggers a page at 3 AM. Instead, alert on burn rate: "at the current error rate, we'll exceed our monthly error budget within 6 hours." This distinguishes brief transients from sustained degradation.

## Health Checks & Readiness

Implement health endpoints that check dependencies and differentiate between liveness (is it running?) and readiness (can it handle traffic?). This distinction is crucial for orchestrators and load balancers.

The liveness probe (`/healthz`) answers "is this process alive?"—it should be cheap and dependency-free (return 200 if the event loop is running). The readiness probe (`/readyz`) answers "can this instance handle traffic?"—it should check database connectivity, cache availability, and downstream service health. Kubernetes uses these to decide whether to restart a pod (liveness) or remove it from the service load balancer (readiness).

**Anti-pattern — Liveness Check That Queries the Database:** Making the liveness probe depend on external services. If the database goes down, Kubernetes sees liveness failures and restarts all your pods—now you have a cascading outage: database overload from reconnections, plus service downtime from restarts. Liveness should be trivial; readiness handles dependency health.

## Resource Profiling

Profile CPU, memory, and IO to identify hotspots and validate optimization impact. Production profiling catches regressions that benchmarks miss, especially in stateful systems where state size growth can silently degrade performance.

Enable continuous profiling in production (Pyroscope, Google Cloud Profiler, `async-profiler` for JVM) with low overhead (~2% CPU). This captures flame graphs over time, letting you compare before/after deployments and identify regressions. For memory profiling, track heap size, GC frequency, and allocation rates—a steady climb in heap size indicates a leak even if the system hasn't OOMed yet.

See the [Algorithms & Performance]({{< ref "/principles/algorithms-performance" >}}) principles for guidance on micro-benchmarking and profiling-driven optimization.

**Anti-pattern — Profile Only in Development:** Running profilers only on dev machines with toy data. Production workloads have different data distributions, concurrency levels, and memory pressure. A function that's fast on 100 items might be catastrophically slow on 10 million. Continuous production profiling catches these scale-dependent regressions.

## Observability in Data Pipelines

Track consumer lag, watermark progression, and checkpoint health for streaming jobs. Pipeline observability reveals whether you're truly delivering the low-latency guarantees you promise.

For Kafka-based pipelines, monitor `consumer_group_lag` (records behind the latest offset), `checkpoint_duration_ms`, and `records_per_second`. For Flink, track watermark delay (how far behind event-time the watermark is) and backpressure indicators per operator. Alert when consumer lag exceeds your freshness SLO—if you promise 1-minute freshness and lag is 5 minutes, you're violating your contract.

See the [Data Pipelines]({{< ref "/principles/data-pipelines" >}}) principles for deeper treatment of backpressure, partitioning, and fault tolerance that directly affect observability.

## Dashboard & Visualization

Build operational dashboards showing key metrics and drill-down views for debugging specific jobs. Time-series visualization reveals trends and patterns that raw numbers obscure.

Structure dashboards in layers: (1) a top-level "golden signals" dashboard (latency, traffic, errors, saturation) for at-a-glance health, (2) per-service dashboards with detailed metrics, and (3) drill-down views for specific subsystems (database queries, cache hit rates, queue depths). Use Grafana, Datadog, or equivalent. Include annotation markers for deployments and incidents so you can visually correlate changes with metric shifts.

**Anti-pattern — Dashboard Without Context:** A wall of graphs with no annotations, no baselines, and no explanation of what "normal" looks like. A dashboard that requires tribal knowledge to interpret is useless to an on-call engineer at 3 AM who's never seen it before. Add thresholds, annotations, and documentation links to every panel.

## Error Budget & Postmortems

Track error budgets to balance velocity and reliability, and conduct blameless postmortems to identify systemic issues rather than individual mistakes. This creates a feedback loop that systematically improves reliability.

Run the error budget as a decision-making tool: when budget is healthy, prioritize feature velocity; when budget is thin, prioritize reliability work. After every significant incident, write a postmortem with: (1) timeline of events, (2) root cause analysis (5 Whys), (3) contributing factors, (4) action items with owners and deadlines. Publish postmortems internally—learning from incidents is more valuable than the fix itself.

**Anti-pattern — Blame-based Incident Response:** Finding the person who "caused" the outage and assigning blame. This drives engineers to hide mistakes and avoid taking on risky but important work. Blameless postmortems focus on *systems*: "Why did the system allow a single config change to take down production?" is more useful than "Who pushed the bad config?"

## Cost Monitoring

Track infrastructure costs by service and environment, setting budget alerts and forecasting based on usage trends. Cloud costs are easy to ignore until you get a surprise bill.

Tag all cloud resources by service, team, and environment (dev/staging/production). Use cloud cost explorers (AWS Cost Explorer, GCP Billing) and set budget alerts at 80% and 100% of expected monthly spend. For variable workloads, forecast based on trailing usage trends and set alerts on anomalous spikes. Review costs monthly in team meetings to build awareness.

**Anti-pattern — "The Cloud is Someone Else's Problem":** Ignoring cloud costs because "infrastructure manages the budget." Engineers who deploy services should see the cost impact of their decisions. A poorly tuned Spark job that runs 10x longer than necessary is an engineering problem, not just a finance problem. Make cost a first-class metric alongside latency and availability.

## Development & Testing Observability

Include verbose logging modes, observability-friendly test fixtures, and use metrics to validate system behavior during integration tests. This surfaces bugs in the lab rather than production.

In integration tests, assert on metrics: "after processing 1000 messages, the `processed_total` counter should equal 1000 and the `error_total` counter should equal 0." Use test-scoped Prometheus registries or metric interceptors to capture and assert on emitted metrics. This catches instrumentation bugs (wrong labels, missing metrics) before they reach production.

**Anti-pattern — Observability as Afterthought:** Adding metrics and tracing after the system is built and deployed. Retrofitting observability means you have no visibility during the most critical phase—initial deployment and first production traffic. Instrument from day one; it's 10x easier to build in than to bolt on.

## Privacy & Compliance

Never log PII or credentials, implement retention policies for logs and traces, and document what data is collected and why. Privacy violations are easier to prevent than remediate.

Implement log scrubbing at the structured logging layer: redact fields matching patterns for emails, phone numbers, credit cards, and API keys before they reach the log aggregator. Set retention policies (30 days for detailed logs, 90 days for aggregated metrics, 13 months for compliance-required audit logs) and automate deletion. Document your data collection in a privacy manifest that answers: what data, why, how long, who has access.

See the [Privacy & Agents]({{< ref "/principles/privacy-agents" >}}) principles for comprehensive guidance on data minimization and consent that applies to all observability data.

**Anti-pattern — Logging Request Bodies:** Logging full HTTP request and response bodies for debugging. This captures passwords, tokens, personal data, and sensitive business data in your log aggregator—which may not have the same access controls as your application database. Log metadata (status codes, durations, paths) and mask or omit bodies.
