---
title: "Web App"
description: "Designing apps based on 12-factor principles."
summary: "Guiding principles for production-ready web apps (12-factor-inspired): scaling, static/media handling, background work, CI/CD, and observability."
tags: []
categories: ["principles"]
draft: false
---

## Twelve-Factor-ish Structure

Separate configuration from code using environment variables and treat logs as event streams. Stateless applications scale horizontally; stateful designs become bottlenecks.

## Static & Media Serving

Build static assets during CI with versioning and caching headers, serve via CDN for global performance, and store uploads in durable object storage. Serving from disk or memory doesn't scale.

## Scaling Web & DB

Use application servers (Gunicorn) with worker processes behind reverse proxies and implement database connection pooling. Horizontal scaling requires stateless design.

## Background Work

Offload expensive tasks to job queues and implement retry logic with idempotent operations. Synchronous long-running tasks create poor user experience and fail unpredictably.

## CI/CD & Migrations

Automate testing, building, and deployment with safe database migrations and rollback plans. Blue-green or canary deployments reduce blast radius of bad releases.

## Observability

Collect application metrics (latency, throughput, errors) with structured logging and correlation IDs. Observability is the feedback loop for production behavior.

## Security Basics

Enforce HTTPS/TLS, implement Content Security Policy and secure headers, and manage secrets outside version control. Security is easier to build than retrofit.

## Local Developer Experience

Provide docker-compose setups for consistent local environments with seed data and fixtures. Good DX multiplies developer productivity.
