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

Every data flow should start with the question: can this happen locally? For agents that process personal photos, email, or documents, local execution means the data never leaves the user's device. When cloud processing is genuinely needed (large model inference, cross-device sync), require an explicit opt-in dialog that explains what data will be transmitted, to where, and for how long.

See [Mailprune]({{< ref "/deep-dives/mailprune" >}}) for an agent that processes email locally with OAuth tokens stored in OS keychains, and [Ragchain]({{< ref "/deep-dives/ragchain" >}}) for a local-first RAG pipeline that keeps all embeddings and inference on-device.

**Anti-pattern — Cloud-first Default:** Sending user data to a cloud API by default with an opt-out buried in settings. Most users never change defaults, so "opt-out" effectively means "always on." GDPR and CCPA increasingly require opt-in consent for data processing. Design for local-first and let cloud be the exception, not the rule.

## Data Minimization

Collect only required fields and use derived features or hashes instead of raw sensitive text. Retention policies with automatic cleanup prevent creeping data hoarding.

Apply the principle: collect the minimum data needed to perform the function, retain it for the minimum time, and derive or aggregate rather than store raw data when possible. Instead of storing full email bodies, store hashes for dedup and summaries for display. Instead of GPS coordinates, store city-level location if that's sufficient.

**Anti-pattern — "Collect Everything, Filter Later":** Ingesting full user data streams into a data lake "in case we need it later." This maximizes risk and regulatory exposure for hypothetical future value. Define what you need upfront, collect only that, and add new collection explicitly when justified.

See the [Migration & Deduplication]({{< ref "/principles/migration-dedup" >}}) principles for related guidance on metadata fidelity—preserve what's needed, but don't hoard what isn't.

## Consent & Transparency

Surface clear descriptions of what data goes where and maintain detailed consent logs for audit. Consent is only meaningful if users understand what they're consenting to.

Implement a consent framework with: (1) plain-language descriptions of each data flow ("We'll send your photo to our cloud service for face detection"), (2) granular toggles per data type and destination, (3) a consent audit log that records when consent was granted or revoked, and (4) a mechanism to re-prompt when processing purposes change. Store consent records with timestamps and version IDs of the privacy notice the user agreed to.

**Anti-pattern — "By Using This App, You Agree to Everything":** A single accept-all consent dialog that bundles essential functionality with data sharing, analytics, and marketing. This isn't informed consent—it's coercion. Granular consent lets users participate in the features they want without surrendering all privacy.

## Token & Credential Safety

Use OS keychains for token management with short-lived tokens and automatic rotation. Never commit secrets to version control; use environment variables or vaults.

On macOS, use Keychain Services; on Linux, use libsecret or the Secret Service API; on Windows, DPAPI. For cloud services, use managed secret stores (AWS Secrets Manager, GCP Secret Manager, Vault). Store OAuth refresh tokens in the keychain and derive short-lived access tokens on demand. Rotate refresh tokens periodically and invalidate all tokens on security events.

See [Mailprune]({{< ref "/deep-dives/mailprune" >}}) for an example of encrypting OAuth tokens at rest and using OS keychains for credential storage in an email agent.

**Anti-pattern — Tokens in Config Files:** Storing API keys and tokens in `.env` files committed to Git, or in plaintext config files on disk. Secret scanning tools flag these in public repos, but even in private repos, any developer with access can see all secrets. Use a secret manager with access control and audit logging.

**Anti-pattern — Long-lived Bearer Tokens:** Issuing API tokens that never expire "for convenience." A leaked token with no expiration provides permanent access. Use short-lived tokens (hours, not months) with automatic refresh and immediate revocation when compromise is detected.

## Explainability & Audit Logs

Maintain readable logs of all agent actions and decisions including reasoning traces. Users won't trust automation they can't explain or audit.

Every agent action should be logged with: (1) what was done (action type, target resource), (2) why it was done (triggering rule, user request, automated policy), (3) what data was accessed or modified, and (4) the outcome (success, failure, skipped). Store audit logs in append-only storage with integrity guarantees (signed entries or write-once storage) so they can't be tampered with after the fact.

See the [Algorithms & Performance]({{< ref "/principles/algorithms-performance" >}}) principles on Explainability & Debug Traces—the same structured trace approach applies to agent reasoning.

**Anti-pattern — "Trust the AI":** Running an agent that makes decisions (deleting emails, moving files, scheduling meetings) with no log of what it did or why. When the agent archives an important email, the user has no way to understand or reverse the decision. Audit logs are the accountability mechanism that makes automation trustworthy.

## Rate Limits & Backoff

Implement exponential backoff for API calls and set local resource limits to prevent cascading failures. Rate limit violations are signs that something broke; alert on them.

Agents often interact with multiple APIs (email, calendar, cloud storage), each with its own rate limits. Maintain per-API rate limit tracking: track the remaining quota from response headers (`X-RateLimit-Remaining`), preemptively throttle before hitting limits, and use exponential backoff with jitter when limits are hit. Set local resource limits too: cap concurrent operations, memory usage, and disk writes to prevent a runaway agent from consuming all system resources.

See the [Networking & Services]({{< ref "/principles/networking-services" >}}) principles for comprehensive guidance on rate limiting, retry strategies, and backoff patterns.

**Anti-pattern — Unbounded Agent Loops:** An agent that retries a failing operation indefinitely in a tight loop. If the API is down, the agent burns CPU and network bandwidth, potentially triggers IP-level blocking, and drains the user's battery on mobile devices. Cap retries, increase delays, and alert the user after sustained failures.

## Testing & Simulation

Create synthetic test environments that mimic real scenarios without sensitive data. Test safety checks and use property-based testing for agent behaviors.

Build a test harness with mock APIs that simulate both happy paths and failure modes: rate limits, auth failures, partial data, malformed responses. Use property-based testing (Hypothesis for Python, proptest for Rust) to generate random action sequences and verify invariants: "no matter what sequence of operations the agent performs, PII is never written to an unencrypted location." Include chaos scenarios: "what happens if the network drops mid-operation?"

**Anti-pattern — Testing with Real User Data:** Using production user data (real emails, real photos) in automated tests. A test failure could leak sensitive data to CI logs, test result databases, or error reporting services. Use synthetic data that has the same structure and edge cases but contains no real PII.

## Policy Configurations

Allow user-configurable safety policies with whitelists, blacklists, and max-effect thresholds. Presets (conservative, balanced, permissive) help users calibrate risk tolerance.

Implement a policy configuration file that defines: (1) allowed actions (whitelist of operations the agent may perform), (2) prohibited actions (blacklist of sensitive operations), (3) max-effect thresholds (e.g., "may delete at most 50 emails per run"), and (4) confirmation requirements (e.g., "require approval before deleting anything older than 1 year"). Provide presets: conservative (read-only, no destructive actions), balanced (moderate automation with confirmations), and permissive (full automation for power users).

**Anti-pattern — All-or-Nothing Permission:** An agent that either has full access or doesn't work. "Grant full email access or uninstall the app" is not a reasonable choice. Implement granular permissions so users can allow reading but not deleting, or allow processing attachments but not forwarding emails. Partial functionality is better than no functionality.

## Decision Framework

Choose your privacy pattern based on the sensitivity of the data and the required utility for the model:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Maximum Safety** | Client-side Processing | Sensitive PII never leaves the user's device. |
| **High Model Utility** | Tokenization/Masking | Replaces PII with synthetic IDs while keeping context. |
| **Audit Compliance** | Local-only Logging | Ensures debugging data isn't centralized or persistent. |
| **User Trust** | Differential Privacy | Adds noise to aggregates to prevent specific identification. |

**Decision Heuristic:** "Choose **Client-side Execution** when the privacy risk involves high-value PII (keys, auth, identity) that the model doesn't need to see."
