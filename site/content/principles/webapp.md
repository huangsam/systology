---
title: "Web App"
description: "Principles for designing apps based on 12-factor principles"
summary: "Guiding principles for production-ready web apps (12-factor-inspired): scaling, static/media handling, background work, CI/CD, and observability."
tags: ["web"]
categories: ["principles"]
---

1. Twelve-Factor-ish App Structure
    - Separate configuration from code using environment variables.
    - Treat logs as event streams for centralized collection.
    - Make applications stateless and horizontally scalable.

2. Static & Media Serving
    - Build static assets during CI with versioning and caching headers.
    - Serve static files via CDN for global performance.
    - Store user uploads in durable object storage with access controls.

3. Scaling Web & DB
    - Use application servers (Gunicorn) with worker processes behind reverse proxies.
    - Implement database connection pooling to handle concurrent requests.
    - Design for horizontal scaling with load balancers and session management.

4. Background Work
    - Offload expensive tasks to background workers with job queues.
    - Implement retry logic and idempotent operations for reliability.
    - Provide visibility into job status and failure handling.

5. CI/CD & Migrations
    - Automate testing, building, and deployment pipelines.
    - Run database migrations safely with backups and rollback plans.
    - Use blue-green or canary deployments for zero-downtime updates.

6. Observability
    - Collect application metrics (latency, throughput, error rates).
    - Implement structured logging with correlation IDs.
    - Set up error tracking and alerting for proactive monitoring.

7. Security Basics
    - Enforce HTTPS/TLS for all communications.
    - Implement Content Security Policy and secure headers.
    - Manage secrets securely outside version control.

8. Local Developer Experience
    - Provide docker-compose setups for consistent local environments.
    - Include seed data and fixtures for quick development setup.
    - Document setup and contribution processes clearly.
