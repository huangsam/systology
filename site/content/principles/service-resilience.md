---
title: "Service Resilience"
description: "Idempotency, circuit breakers, async IO, and background job patterns."
summary: "Patterns for reliable service behavior: idempotency, async IO, circuit breakers, background job queues, and observability."
tags: ["networking", "distributed-systems", "queues"]
categories: ["principles"]
draft: false
---

## Idempotency

Design operations to be idempotent using idempotency keys and unique request IDs. Retries are only safe if they can't cause side effects.

Generate a unique idempotency key per logical operation (UUID or deterministic hash of the operation parameters). Send it with each request. The server checks a short-lived store (Redis with 15-minute TTL) for the key: if found, return the cached response; if not, process the request and cache the result. This makes retries safe for state-changing operations like payments and order creation.

See the [Payment System]({{< ref "/designs/payment-system" >}}) design for a production-grade implementation of idempotency in financial transactions.

**Anti-pattern — POST Without Idempotency:** Using POST for state-changing operations without idempotency keys. A network timeout causes the client to retry, and the server processes the request twice—creating duplicate orders, double-charging a credit card, or sending duplicate notifications. Idempotency keys are cheap insurance against expensive duplicates.

## Async & Non-blocking IO

Use async/await patterns for scalability and avoid blocking operations in critical paths. Backpressure handling prevents memory exhaustion under load.

Async IO shines for workloads with many concurrent connections where most time is spent waiting for IO (network, disk). A single async thread can handle thousands of concurrent connections where a thread-per-connection model would exhaust memory. In Python, use `asyncio`/`aiohttp`; in Rust, use `tokio`; in Go, goroutines provide lightweight concurrency natively.

**Anti-pattern — Async Everything:** Making CPU-bound work async. Async IO helps when threads are waiting on network responses; for CPU-intensive computation (compression, hashing, ML inference), async provides no benefit and adds complexity. Use thread pools for CPU-bound work and async for IO-bound work.

## Network Resilience

Implement graceful degradation when optional services fail and use fallbacks and caching for reliability. Test failure scenarios regularly—surprises belong in labs, not production.

Use the circuit breaker pattern: after N consecutive failures to a downstream service, open the circuit (stop making requests) for a cooldown period, then half-open (try a single request) to see if recovery has occurred. During the open state, serve from cache, return a degraded response, or surface "temporarily unavailable" to the user rather than timing out on every request.

{{< mermaid >}}
stateDiagram-v2
    [*] --> Closed
    Closed --> Open : N consecutive failures
    Open --> HalfOpen : cooldown expires
    HalfOpen --> Closed : probe succeeds
    HalfOpen --> Open : probe fails
    Closed : Closed
    note right of Closed : Normal operation
    Open : Open
    note right of Open : Fail fast — serve cache
    HalfOpen : Half-Open
    note right of HalfOpen : One probe request
{{< /mermaid >}}

See the [Distributed Cache]({{< ref "/designs/distributed-cache" >}}) design for how caching provides resilience layers alongside performance.

**Anti-pattern — All-or-Nothing Dependency:** Treating every downstream service as critical. If the recommendation service is down, should the entire product page fail? Usually not—show the product without recommendations. Classify dependencies as critical (payment must succeed) vs. optional (recommendations are nice-to-have) and degrade gracefully for optional ones.

## Background Job Processing

Use pull-based workers with visibility timeouts and idempotency keys for reliable async task execution. Separate queue backends, retry policies, and DLQ handling from application logic.

Pull-based workers (vs. push-based) give you natural backpressure: workers consume at their own pace and the queue buffers the difference. Visibility timeouts prevent tasks from being lost if a worker crashes mid-execution—the task reappears in the queue after the timeout expires and is picked up by another worker. Pair this with a heartbeat mechanism: long-running workers periodically extend the timeout to signal liveness, preventing premature redelivery.

For idempotency, key each job write on a stable `(owner_id, operation_hash)` combination so client retries during network timeouts don't enqueue duplicate jobs. Persist deduplication keys to a database rather than an in-process cache so restarts don't lose them.

See the [Algorithms & Performance]({{< ref "/principles/algorithms-performance" >}}) principles for worker sizing and parallelism tuning guidance.

**Anti-pattern — Fire-and-Forget Enqueue:** Treating job submission as a best-effort operation with no deduplication and no status visibility. When the client retries after a timeout, the job runs twice. When it silently fails, no one knows. Always confirm enqueue, track job status in a backing store, and surface failures.

### Dead-Letter Queues and Retry Policies

Route jobs to a Dead-Letter Queue (DLQ) after a configurable number of retries with exponential backoff and jitter. The DLQ is not a graveyard—it's an inspection queue that enables informed replay or discard decisions.

Use backoff: `delay = min(base × 2^attempt + jitter, max_delay)` (e.g., 5s base, 5-minute cap, ±25% jitter). Jitter prevents synchronized retry storms when a downstream dependency recovers. After max retries (3–5 for most workloads), move the message to the DLQ with a full context envelope: original payload, error log, attempt count, and timestamps. Alert on DLQ depth—sustained DLQ growth signals a systemic failure, not transient errors.

**Anti-pattern — Silent Discard:** Dropping jobs that have failed N times without routing them to a DLQ or alerting. From the system's perspective, the job completed. From the user's perspective, nothing happened. DLQs are the difference between "this job failed and we know why" and "something went wrong and we have no idea what."

### Priority and QoS

Use dedicated queues per job type or priority tier rather than a single shared queue. This prevents batch workloads from starving latency-sensitive jobs.

For example: a `high_priority` queue for user-initiated requests (must start within 30s), a `default` queue for system-triggered jobs (must start within 5 min), and a `batch` queue for overnight analytics (best-effort). Workers for the `high_priority` queue should never be saturated by batch work. Token-bucket rate limiters on queue admission protect downstream services from burst overload.

## Monitoring & Debugging

Log request/response metadata (status codes, latencies) and emit metrics for success/failure rates. Distributed tracing reveals cross-service latency problems.

For every outbound HTTP call, log: method, URL (without query params containing secrets), status code, and duration. Emit metrics: `http_client_requests_total{method, host, status}` and `http_client_request_duration_seconds{method, host}`. Use these to build dashboards that show error rates and latency percentiles per downstream dependency.

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for comprehensive guidance on structured logging, tracing, and alerting.

## Local Development & Mocking

Provide mock servers and environment-based config to switch backends. Integration tests validate contract compliance without external dependencies.

Use tools like WireMock (Java), `responses` (Python), or `nock` (Node.js) to stub external APIs in tests. For local development, provide a Docker Compose setup that spins up mock versions of downstream services. Use environment-based configuration to switch between real and mock backends: `PAYMENT_SERVICE_URL=http://localhost:8081` in development vs. the real endpoint in production.

**Anti-pattern — Testing Against Production APIs:** Running integration tests against real external services. This is slow, flaky (dependent on external availability), expensive (some APIs charge per call), and dangerous (you might accidentally create real orders or send real notifications). Use mocks and contract tests locally, and reserve real API testing for a staging environment with sandboxed accounts.

## Decision Framework

Choose your resilience pattern based on the failure mode you're designing against:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Safe Retries** | Idempotency Keys | State-changing retries converge without side effects. |
| **Fault Isolation** | Circuit Breaker | Stops cascading failure; restores automatically after cooldown. |
| **Throughput under Load** | Async / Non-blocking IO | One thread handles thousands of concurrent IO-bound requests. |
| **Reliable Async Tasks** | Pull Workers + DLQ | Natural backpressure; failed jobs are inspectable, not silently dropped. |
| **Priority Isolation** | Dedicated Queues per Tier | Prevents batch work from starving latency-sensitive jobs. |

**Decision Heuristic:** "Choose **idempotency first**, then **circuit breakers** at service boundaries, then **dedicated queues** for async work. Any retryable operation without idempotency is a latent duplicate bug."

## Decision Framework

Use this section to provide a clear heuristic or trade-off matrix for the principle. This should help the reader make a choice based on their specific constraints.

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Constraint A** | Option 1 | Benefit/Trade-off |
| **Constraint B** | Option 2 | Benefit/Trade-off |

**Decision Heuristic:** "Choose **[Tactic]** when **[Context]** is more important than **[Alternative]**."

## Cross-principle Notes

Optionally, relate multiple principles to each other or reference other pages in the site that go deeper for a production example of this principle in practice.
