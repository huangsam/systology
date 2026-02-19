---
title: "Chowist"
description: "Web app for food features with twelve-factor scaling."
summary: "Monolithic Django app for place listings; focus on production hardening: static serving, background jobs, connection pooling, and CI/CD."
tags: ["monitoring", "networking"]
categories: ["deep-dives"]
links:
  github: "https://github.com/huangsam/chowist"
draft: false
---

## Context & Motivation

**Context:** `Chowist` is a Django-based web application that replicates Yelp-like features: place listings, profiles, and a marketing homepage. It supports local development, demo data, Docker compose, and production deployment via Gunicorn.

**Motivation:** During lunch hours at my past companies, figuring out the next place to eat was a common challenge. Chowist was built as a fun project to practice web development and demonstrate production hardening techniques. The core problem is building a web app that can reliably serve traffic, handle file uploads, and scale beyond a single process while maintaining a good developer experience.

## The Local Implementation

- **Current Logic:** Standard Django app with models for places and users, views for list/detail, demo fixtures for local testing, and management commands for setup. Development flow uses `virtualenv` or `docker-compose` for local stacks.
- **Bottleneck:** Single-process dev server, static file handling in production, potential lack of connection pooling and background job processing for heavier workloads (image processing, notifications).

## Comparison to Industry Standards

- **My Project:** Monolithic Django app focused on rapid dev and UX demos.
- **Industry:** Modern production web apps separate concerns: API layer, static CDN, background workers, autoscaling, and managed DB services.
- **Gap Analysis:** To be production-ready, add CI/CD pipelines, health checks, rolling deploys, and infra-as-code for reproducible environments.

## Risks & Mitigations

- **Static/media serving issues:** integrate proper build and CDN-backed serving; ensure collectstatic is run in builds.
- **Data loss/migrations:** use migrations with backups and run schema changes in safe, backward-compatible steps.
- **Scaling DB connections:** use pgbouncer and limit active connections per app instance.
