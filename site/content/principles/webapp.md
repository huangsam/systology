---
title: "Web App"
description: "Designing apps based on 12-factor principles."
summary: "Guiding principles for production-ready web apps (12-factor-inspired): scaling, static/media handling, background work, CI/CD, and observability."
tags: ["extensibility"]
categories: ["principles"]
draft: false
---

## Twelve-Factor-ish Structure

Separate configuration from code using environment variables and treat logs as event streams. Stateless applications scale horizontally; stateful designs become bottlenecks.

The [Twelve-Factor App](https://12factor.net/) methodology provides the foundation for modern web application design. At its core: store config in the environment (not in code or config files committed to Git), make processes stateless and share-nothing (session state goes to Redis or a database, not local memory), and treat each deployment as disposable (any instance can be killed and replaced without data loss).

See how [Chowist]({{< ref "/deep-dives/chowist" >}}) applies 12-factor principles with environment-based config, stateless application processes, and external session/data stores.

**Anti-pattern — Config in Code:** Hardcoding database URLs, API keys, or feature flags in source code. This means different configs require different builds—you can't promote a staging build directly to production. Environment variables let one build artifact run in any environment.

**Anti-pattern — Sticky Sessions:** Routing users to specific server instances because session state is stored in local memory. When that instance crashes or scales down, the user loses their session. Externalize all state to Redis, Memcached, or a database so any instance can serve any user.

## Static & Media Serving

Build static assets during CI with versioning and caching headers, serve via CDN for global performance, and store uploads in durable object storage. Serving from disk or memory doesn't scale.

Use content-hashed filenames (`app.a1b2c3.js`) for cache busting—users always get the latest version without manual cache invalidation. Set `Cache-Control: max-age=31536000, immutable` for hashed assets (they never change). Serve through a CDN (CloudFront, Fastly, Cloudflare) so users hit edge nodes rather than your origin server. Store user uploads (images, documents) in object storage (S3, GCS) with pre-signed URLs for direct upload, bypassing your application server.

See the [CDN & Media]({{< ref "/designs/cdn-media" >}}) design for a production architecture covering origin shielding, edge caching, and media transformation pipelines.

**Anti-pattern — Serving Uploads from Application Servers:** Storing user uploads on the application server's local filesystem and serving them via the app process. This is a single point of failure (disk dies, files are gone), doesn't scale (each server has different files), and wastes application server resources on IO. Use object storage with CDN.

## Scaling Web & DB

Use application servers (Gunicorn) with worker processes behind reverse proxies and implement database connection pooling. Horizontal scaling requires stateless design.

For Python, run Gunicorn with `2 * num_cores + 1` workers (sync) or fewer workers with async (`uvicorn`/`hypercorn` for ASGI). Put NGINX in front for TLS termination, static file serving, and request buffering. For the database, use connection pooling (PgBouncer for PostgreSQL, ProxySQL for MySQL) to avoid the overhead of per-request connections. As traffic grows, add read replicas for read-heavy workloads and consider partitioning or sharding for write-heavy ones.

**Anti-pattern — Vertical Scaling Only:** Upgrading to bigger servers instead of adding more instances. This has a ceiling (there's a largest server you can buy) and creates a single point of failure. Design for horizontal scaling from the start—it's much harder to retrofit statelessness into a stateful application.

**Anti-pattern — Unbounded Connection Creation:** Each application server process opening its own database connection without pooling. With 20 Gunicorn workers across 5 servers, that's 100 direct database connections—many databases perform poorly beyond a few dozen concurrent connections. Pool at the application level and/or use a connection proxy.

## Background Work

Offload expensive tasks to job queues and implement retry logic with idempotent operations. Synchronous long-running tasks create poor user experience and fail unpredictably.

When a user uploads a video for processing, don't process it in the HTTP request—return 202 Accepted immediately and enqueue the work. Use Celery (Python), Sidekiq (Ruby), or Bull (Node.js) for task queues backed by Redis or RabbitMQ. Every task must be idempotent (safe to retry) because workers crash and queues deliver at-least-once. Provide a status endpoint (`GET /jobs/{id}`) so clients can poll or use webhooks for completion notification.

See the [Background Job Queue]({{< ref "/designs/background-job-queue" >}}) design for a comprehensive treatment of job queues with retries, DLQ handling, prioritization, and autoscaling.

**Anti-pattern — Synchronous Everything:** Processing a 2-minute video encoding job inside the HTTP request handler. The user sees a spinner, the load balancer times out at 60 seconds, the request fails, and the user retries—now you have two encoding jobs for the same video. Offload anything that takes more than a few seconds to a background queue.

## CI/CD & Migrations

Automate testing, building, and deployment with safe database migrations and rollback plans. Blue-green or canary deployments reduce blast radius of bad releases.

Structure your deployment pipeline as: lint → test → build → deploy to staging → smoke test → deploy to production (canary → full rollout). For database migrations, use tools like Alembic (Python), Flyway (Java), or Knex (Node.js) with sequential, versioned migration files. Every migration should be backward-compatible: add columns as nullable with defaults, create new tables before writing to them, deprecate old columns before removing them. Test rollback procedures regularly—a migration that can't be reversed is a one-way door.

**Anti-pattern — Big-bang Deploys:** Deploying to all production instances simultaneously. If the release has a bug, 100% of users are affected immediately. Use canary deployments (1% → 10% → 50% → 100%) with automated rollback triggered by error rate increases. Blue-green deployments let you switch back to the old version in seconds.

**Anti-pattern — Breaking Migrations:** Running `ALTER TABLE DROP COLUMN` in a migration while the old code is still running. The old code tries to read the dropped column and crashes. Use a multi-phase approach: (1) deploy code that doesn't use the column, (2) run the migration to drop the column. Never couple code changes with destructive schema changes in the same deployment.

## Observability

Collect application metrics (latency, throughput, errors) with structured logging and correlation IDs. Observability is the feedback loop for production behavior.

Instrument your application with middleware that automatically captures: request count, request latency (histogram), error rate, and active connections. Add a correlation ID (trace ID) to every request at the edge and propagate it through all internal calls and log entries. When a user reports "the page was slow 5 minutes ago," you can search logs by timestamp, find the correlation ID, and trace the exact request path through every service.

See the [Monitoring & Observability]({{< ref "/principles/monitoring" >}}) principles for comprehensive guidance on metrics, structured logging, distributed tracing, and SLO-driven alerting.

**Anti-pattern — Observability After Launch:** Deploying to production without metrics or logging, then scrambling to add them after the first incident. By the time you have visibility, you've already lost trust. Instrument from day one—even a simple request latency histogram and error counter provide enormous diagnostic value.

## Security Basics

Enforce HTTPS/TLS, implement Content Security Policy and secure headers, and manage secrets outside version control. Security is easier to build than retrofit.

At minimum, configure these HTTP security headers: `Strict-Transport-Security` (force HTTPS), `Content-Security-Policy` (prevent XSS and injection), `X-Content-Type-Options: nosniff` (prevent MIME sniffing), `X-Frame-Options: DENY` (prevent clickjacking). Use a secrets manager (Vault, AWS Secrets Manager) or at minimum encrypted environment variables—never commit secrets to Git. Implement CSRF protection for form submissions and use parameterized queries (never string interpolation) for all database access.

See the [Networking & Services]({{< ref "/principles/networking-services" >}}) principles for TLS, authentication, and authorization guidance that extends to web applications.

**Anti-pattern — Security as Sprint Work:** Treating security as a feature to be scheduled alongside product work. SQL injection, XSS, and CSRF prevention should be built into your framework and middleware from the start, not added in a "security sprint" six months after launch. By then, you've likely already been vulnerable.

## Local Developer Experience

Provide docker-compose setups for consistent local environments with seed data and fixtures. Good DX multiplies developer productivity.

A new developer should be able to: `git clone && docker-compose up && open localhost:8000` and see a running application with realistic seed data within 15 minutes. Include: a `docker-compose.yml` with the app, database, cache, and any dependent services; a seed script that populates the database with realistic test data; and a Makefile or justfile with common commands (`make test`, `make lint`, `make seed`, `make shell`). Document common workflows in CONTRIBUTING.md.

**Anti-pattern — "Check the Wiki for Setup":** A setup process that requires reading a 20-page wiki, installing 15 tools manually, obtaining credentials from other team members, and following platform-specific instructions. Every friction point in local setup is a multiplier on wasted developer time. Containerize the environment and automate the setup to a single command.

## Decision Framework

Choose your web application architecture based on the interactivity and SEO requirements:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **SEO / Fast Loading** | Server-Side Rendering (SSR)| Pre-renders pages on the server for crawlers and slow clients. |
| **High Interactivity** | Single-Page App (SPA) | Provides a fluid, app-like experience after the initial load. |
| **Static Content** | Static Site Gen (SSG) | Maximizes security and speed for content that changes infrequently. |
| **Resilient State** | Optimistic UI Updates | Improves perceived latency by updating the UI before the server confirms. |

**Decision Heuristic:** "Choose **SSR/SSG** for the content shell and **SPA/Islands** for the interactive features. Don't force a heavy JS bundle on users just to read text."
