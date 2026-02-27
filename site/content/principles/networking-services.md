---
title: "Networking & Services"
description: "API design, rate limiting, retries, connection management, and auth."
summary: "Practical guidance for API contracts, retries/backoff, rate limiting, timeouts, connection pooling, service discovery, auth, serialization, and TLS."
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

For idempotency, circuit breakers, async IO, and background job patterns, see the [Service Resilience]({{< ref "/principles/service-resilience" >}}) principles.

## Decision Framework

Choose your networking protocol based on the latency and reliability requirements of the communication:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **High-Throughput** | gRPC (HTTP/2) | Binary serialization and multiplexing reduce overhead. |
| **Wide Compatibility** | REST (HTTP/1.1) | Easiest for browser and external partner integration. |
| **Real-time Events** | WebSockets | Persistent duplex connection for instant updates. |
| **Resilient Retries** | Service Mesh | Offloads retry, timeout, and circuit breaking from app code. |

**Decision Heuristic:** "Choose **gRPC** for internal service-to-service calls and **REST** for public-facing edge APIs."
