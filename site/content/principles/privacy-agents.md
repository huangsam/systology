---
title: "Privacy & Agents"
description: "Designing safe, transparent, user-centric agents for sensitive data."
summary: "Privacy-first design rules for agents: local-first defaults, data minimization, consent, and auditable actions."
tags: ["privacy"]
categories: ["principles"]
draft: false
---

## Local-first Default

Process sensitive data on-device or locally wherever possible, with explicit opt-in for any cloud integrations. Network exposure multiplies risk; local processing is the baseline.

## Data Minimization

Collect only required fields and use derived features or hashes instead of raw sensitive text. Retention policies with automatic cleanup prevent creeping data hoarding.

## Consent & Transparency

Surface clear descriptions of what data goes where and maintain detailed consent logs for audit. Consent is only meaningful if users understand what they're consenting to.

## Token & Credential Safety

Use OS keychains for token management with short-lived tokens and automatic rotation. Never commit secrets to version control; use environment variables or vaults.

## Explainability & Audit Logs

Maintain readable logs of all agent actions and decisions including reasoning traces. Users won't trust automation they can't explain or audit.

## Rate Limits & Backoff

Implement exponential backoff for API calls and set local resource limits to prevent cascading failures. Rate limit violations are signs that something broke; alert on them.

## Testing & Simulation

Create synthetic test environments that mimic real scenarios without sensitive data. Test safety checks and use property-based testing for agent behaviors.

## Policy Configurations

Allow user-configurable safety policies with whitelists, blacklists, and max-effect thresholds. Presets (conservative, balanced, permissive) help users calibrate risk tolerance.
