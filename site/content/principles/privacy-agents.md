---
title: "Privacy & Agents"
description: "Designing safe, transparent, user-centric agents for sensitive data."
summary: "Privacy-first design rules for agents: local-first defaults, data minimization, consent, and auditable actions."
tags: ["privacy"]
categories: ["principles"]
---

1. Local-first Default
    - Prefer on-device or local-only processing for sensitive data to avoid network exposure.
    - Use local storage and computation; avoid cloud uploads unless explicitly opted-in.
    - Require explicit user consent and clear warnings for any external API integrations.

2. Data Minimization
    - Collect and store only the minimal fields required for functionality.
    - Use derived features or hashes instead of raw sensitive text where possible.
    - Implement data retention policies with automatic cleanup of unused data.

3. Consent & Transparency
    - Surface clear descriptions of what data is sent to external services.
    - Retain detailed consent logs for audit and user review.
    - Provide data flow diagrams and privacy impact assessments in documentation.

4. Token & Credential Safety
    - Use OS keychains or secure credential stores for token management.
    - Implement short-lived tokens with automatic rotation and refresh.
    - Never commit secrets to version control; use environment variables or vaults.

5. Explainability & Audit Logs
    - Maintain human-readable logs of all agent actions and decisions.
    - Support reversible changes with dry-run modes and undo capabilities.
    - Include reasoning traces for automated decisions to build user trust.

6. Rate Limits & Backoff
    - Implement exponential backoff for API calls to handle rate limits gracefully.
    - Set local resource limits (CPU, memory) to prevent cascade failures.
    - Monitor and alert on usage patterns that approach limits.

7. Testing & Simulation
    - Create synthetic test environments that mimic real scenarios without real data.
    - Write unit tests for safety checks and edge case handling.
    - Use property-based testing for agent behaviors and decision logic.

8. Policy Configurations
    - Allow user-configurable safety policies like whitelists and blacklists.
    - Implement max-effect thresholds to limit the scope of automated actions.
    - Provide presets (conservative, balanced, permissive) for different risk tolerances.
