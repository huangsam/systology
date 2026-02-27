---
title: "Networking & Services"
description: "API design, rate limiting, retries, and resilient service communication."
summary: "Practical guidance for API design, retries/backoff, rate limiting, connection pooling, and service resilience."
tags: ["networking"]
categories: ["principles"]
draft: false
---

## API Design & Contracts

Define clear, versioned API contracts with request/response schemas and use REST conventions or gRPC for performance-critical paths. Explicit contracts prevent misunderstandings and enable independent evolution.

Start with OpenAPI (Swagger) for REST APIs or Protocol Buffer definitions for gRPC. These schemas serve as the single source of truth—generate client SDKs, server stubs, and documentation from the same spec. Version your API in the URL path (`/v1/`, `/v2/`) or via content negotiation headers. When adding fields, make them optional with sensible defaults so existing clients don't break.

See the [Notification System]({{< ref "/designs/notification-system" >}}) design for an example of a well-defined internal API with priority routing and channel adapters.

**Anti-pattern — Implicit Contracts:** Documenting your API in a README that drifts from the actual implementation. Without a machine-readable schema, clients are built on assumptions that break silently when the server changes. A typo in a field name becomes a production incident. Use contract-first design: write the spec, generate the code.

## Error Handling & Retries

Implement exponential backoff with jitter for transient failures (5xx, timeouts) but never retry non-retryable errors (4xx). Cap retries to prevent infinite loops and differentiate error types to avoid wasted effort.

Use a standard formula: `delay = min(base * 2^attempt + random_jitter, max_delay)`. Start at 1s, cap at 60s, add ±25% jitter to prevent thundering herd when many clients retry simultaneously. Classify errors: 429 (rate limited) → retry with the `Retry-After` header; 500/502/503 → retry with backoff; 400/401/403/404 → do not retry (fix the request).

See [Photohaul]({{< ref "/deep-dives/photohaul" >}}) for an example of handling exponential backoff and retries when dealing with cloud storage API rate limits.

**Anti-pattern — Retry Storms:** Retrying immediately without backoff or jitter. When a service is overloaded and returns 503, 1000 clients immediately retrying at the same instant creates a thundering herd that prevents recovery. Exponential backoff with jitter spreads retries across time, giving the service room to recover.

**Anti-pattern — Retrying Non-retryable Errors:** Retrying a 400 Bad Request. The request is malformed; sending it again won't fix it. You burn resources, fill logs with identical errors, and delay the real fix (correcting the request). Classify errors before retrying.

## Rate Limiting & Throttling

Respect external rate limits with adaptive throttling and implement client-side rate limiting to avoid overwhelming downstream services. Token bucket algorithms provide smooth traffic shaping.

Implement both client-side and server-side rate limiting. Client-side: use a token bucket that tracks your API quota and blocks requests proactively before hitting the server. Server-side: return `429 Too Many Requests` with a `Retry-After` header. For adaptive throttling, track recent 429 responses and reduce request rate proportionally—like TCP congestion control for APIs.

See the [Flash Sale]({{< ref "/designs/flash-sale" >}}) design for production-grade rate limiting and connection shedding at extreme scale (1M concurrent users).

**Anti-pattern — Ignoring Rate Limits:** Treating 429 responses as transient errors and retrying immediately at full speed. This escalates to IP bans, API key revocation, and provider relationship damage. Parse the `Retry-After` header and back off accordingly.

## Timeouts & Deadlines

Set appropriate timeouts (connection, read, total) and propagate deadlines across service boundaries for coordinated cancellation. Timeouts prevent indefinite hangs; deadlines ensure requests fail consistently.

Use three timeout layers: connection timeout (how long to wait for TCP handshake, ~3s), read timeout (how long to wait for response data, ~10s), and total timeout (end-to-end including retries, ~30s). For service-to-service calls, propagate deadlines: if the API gateway has 5s remaining on its deadline, pass `deadline: now + 4.5s` to the downstream service so it can abort early rather than doing work that will be discarded.

**Anti-pattern — No Timeout:** Making HTTP requests without timeouts. A downstream service hangs, your thread pool fills up, your service stops responding, your upstream callers time out and retry, creating cascading failure. Every network call must have a timeout. Every. Single. One.

## Connection Management

Use connection pooling to avoid repeated handshake overhead and implement keep-alive for reuse. Pool size matters: too small causes queueing, too large wastes resources.

Configure pool size based on expected concurrency: for a service making 100 concurrent requests to a downstream, a pool of 100 connections avoids queueing. But 1000 connections to a database that only handles 100 concurrent queries wastes file descriptors and causes server-side contention. Use health checks on pooled connections to evict stale or broken sockets. For HTTP/2 or gRPC, multiplexing multiple streams over a single connection reduces the need for large connection pools.

**Anti-pattern — Connection Per Request:** Opening a new TCP connection (with TLS handshake) for every HTTP request. TLS negotiation alone adds 1–3 round trips (~50–150ms). At 1000 requests/second, that's 1000 unnecessary handshakes. Pool and reuse connections.

## Service Discovery & Load Balancing

Use service discovery (DNS, Kubernetes services) for dynamic endpoints and implement health-check-based routing. Load balancing reduces tail latency better than round-robin alone.

In Kubernetes, services provide built-in L4 load balancing. For more intelligent routing, use an L7 load balancer (Envoy, NGINX) with health-check-based routing that removes unhealthy backends and least-connections balancing that sends traffic to the least loaded instance. For client-side load balancing (common in gRPC), maintain a local service registry and use weighted round-robin with health checks.

**Anti-pattern — Hardcoded Endpoints:** Configuring downstream service URLs as static strings (`api.internal.company.com:8080`). When the service moves, scales, or fails over, your config requires a manual update and restart. Use service discovery for dynamic resolution and health-aware routing.

## Authentication & Authorization

Use OAuth 2.0 flows for third-party integrations and implement token refresh logic with secure credential storage. Apply least privilege for service-to-service auth.

For user-facing APIs, use OAuth 2.0 with PKCE (for public clients) or client credentials (for server-to-server). Store tokens in OS keychains or encrypted config, never in plaintext files or environment variables visible in process listings. Implement automatic token refresh with jitter to prevent synchronized refresh storms. For service-to-service auth, use mutual TLS (mTLS) or signed JWTs with short expiration.

See [Mailprune]({{< ref "/deep-dives/mailprune" >}}) for an example of implementing OAuth 2.0 flows with local secure credential storage for an email processing agent. For broader guidance on token and credential safety in automated systems, see the [Privacy & Agents]({{< ref "/principles/privacy-agents" >}}) principles.

**Anti-pattern — Long-lived API Keys:** Using a single API key with no rotation that has admin-level access. If the key leaks (and it will—in logs, configs, error messages), the blast radius is maximum. Use short-lived tokens with automatic rotation and scope permissions to the minimum required.

### JWT vs. Opaque Tokens

Use short-lived stateless JWTs for fast, decentralized validation and long-lived stateful refresh tokens for revocable sessions. Neither alone is sufficient—the hybrid covers both performance and revocability.

JWTs are verified by any service that holds the public key (fetched from a JWKS endpoint) without a network call to the Auth service. This is critical at scale: with 10k authentications/sec, making a database call per validation would bottleneck the entire platform. The tradeoff is irrevocability—a stolen JWT is valid until it expires. Counter this with short expiry windows (15 minutes) and refresh token rotation: each refresh issues a new refresh token and invalidates the old one, so reuse of a stolen refresh token is detectable.

**Anti-pattern — Long-lived JWTs:** Setting JWT expiry to 24 hours or longer for UX convenience. A stolen long-lived JWT provides day-long unauthorized access with no practical way to revoke it. Short expiry + refresh tokens gives you both convenience and a revocation safety valve.

**Anti-pattern — Token Bloat:** Embedding large user profiles, full role hierarchies, or feature flags into JWT payloads. JWT bytes appear in every HTTP request header. A 4 KB JWT sent 1M times/hour adds 4 GB of header overhead. Encode only the minimum claims needed for authorization (user ID, scopes, expiry). Fetch additional context from a cache if needed.

### RBAC in Tokens

Embed scopes and roles directly in JWT claims for stateless authorization decisions in downstream services. Services can authorize a request without a round-trip to the Auth service or a database.

Structure the `scopes` claim as an array of fine-grained permission strings (e.g., `["read:messages", "write:comments", "admin:billing"]`) rather than coarse-grained role names. Downstream services check the presence of a specific scope—not a role name—which decouples authorization logic from role management. Roles are an admin concern; scopes are an enforcement concern. Keep them separate.

## Data Serialization & Formats

Choose formats based on tradeoffs: JSON for human debugging, Protocol Buffers for efficiency. Plan for schema evolution with backward/forward compatibility.

JSON is human-readable, universally supported, and debug-friendly—ideal for public APIs and configuration. Protocol Buffers (protobuf) are binary, strongly typed, and 3–10x smaller than JSON—ideal for high-throughput internal services. For message queues, Avro provides schema evolution with a registry. Whichever you choose, plan for schema evolution: add fields as optional, never reuse field numbers, and maintain a compatibility policy.

**Anti-pattern — Custom Binary Format:** Inventing a bespoke binary serialization format "for performance." You spend months debugging encoding edge cases, building tooling, and onboarding teammates. Protobuf, FlatBuffers, and Cap'n Proto have already solved this—use them.

## Async & Non-blocking IO

Use async/await patterns for scalability and avoid blocking operations in critical paths. Backpressure handling prevents memory exhaustion under load.

Async IO shines for workloads with many concurrent connections where most time is spent waiting for IO (network, disk). A single async thread can handle thousands of concurrent connections where a thread-per-connection model would exhaust memory. In Python, use `asyncio`/`aiohttp`; in Rust, use `tokio`; in Go, goroutines provide lightweight concurrency natively.

**Anti-pattern — Async Everything:** Making CPU-bound work async. Async IO helps when threads are waiting on network responses; for CPU-intensive computation (compression, hashing, ML inference), async provides no benefit and adds complexity. Use thread pools for CPU-bound work and async for IO-bound work.

## SSL/TLS & Security

Enforce HTTPS/TLS and validate certificates with pinning where needed. Keep TLS libraries current as new attacks emerge.

Use TLS 1.3 (faster handshake, stronger security) and disable TLS 1.0/1.1. Configure HSTS headers to prevent downgrade attacks. For internal service communication, implement mTLS where both client and server verify each other's certificates. Automate certificate rotation with tools like cert-manager (Kubernetes) or Let's Encrypt.

See the [Web App]({{< ref "/principles/webapp" >}}) principles for related guidance on HTTPS, CSP, and secure headers in web application contexts.

**Anti-pattern — Self-signed Certs with Verification Disabled:** Using `verify=False` in development and accidentally shipping it to production. This completely negates TLS by accepting any certificate, including man-in-the-middle attacks. Use proper CA-signed certificates in all environments and never disable verification.

## Idempotency

Design operations to be idempotent using idempotency keys and unique request IDs. Retries are only safe if they can't cause side effects.

Generate a unique idempotency key per logical operation (UUID or deterministic hash of the operation parameters). Send it with each request. The server checks a short-lived store (Redis with 15-minute TTL) for the key: if found, return the cached response; if not, process the request and cache the result. This makes retries safe for state-changing operations like payments and order creation.

See the [Payment System]({{< ref "/designs/payment-system" >}}) design for a production-grade implementation of idempotency in financial transactions.

**Anti-pattern — POST Without Idempotency:** Using POST for state-changing operations without idempotency keys. A network timeout causes the client to retry, and the server processes the request twice—creating duplicate orders, double-charging a credit card, or sending duplicate notifications. Idempotency keys are cheap insurance against expensive duplicates.

## Monitoring & Debugging

Log request/response metadata (status codes, latencies) and emit metrics for success/failure rates. Distributed tracing reveals cross-service latency problems.

For every outbound HTTP call, log: method, URL (without query params containing secrets), status code, and duration. Emit metrics: `http_client_requests_total{method, host, status}` and `http_client_request_duration_seconds{method, host}`. Use these to build dashboards that show error rates and latency percentiles per downstream dependency.

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for comprehensive guidance on structured logging, tracing, and alerting.

## Local Development & Mocking

Provide mock servers and environment-based config to switch backends. Integration tests validate contract compliance without external dependencies.

Use tools like WireMock (Java), `responses` (Python), or `nock` (Node.js) to stub external APIs in tests. For local development, provide a Docker Compose setup that spins up mock versions of downstream services. Use environment-based configuration to switch between real and mock backends: `PAYMENT_SERVICE_URL=http://localhost:8081` in development vs. the real endpoint in production.

**Anti-pattern — Testing Against Production APIs:** Running integration tests against real external services. This is slow, flaky (dependent on external availability), expensive (some APIs charge per call), and dangerous (you might accidentally create real orders or send real notifications). Use mocks and contract tests locally, and reserve real API testing for a staging environment with sandboxed accounts.

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

## Decision Framework

Choose your networking protocol based on the latency and reliability requirements of the communication:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **High-Throughput** | gRPC (HTTP/2) | Binary serialization and multiplexing reduce overhead. |
| **Wide Compatibility** | REST (HTTP/1.1) | Easiest for browser and external partner integration. |
| **Real-time Events** | WebSockets | Persistent duplex connection for instant updates. |
| **Resilient Retries** | Service Mesh | Offloads retry, timeout, and circuit breaking from app code. |

**Decision Heuristic:** "Choose **gRPC** for internal service-to-service calls and **REST** for public-facing edge APIs."
