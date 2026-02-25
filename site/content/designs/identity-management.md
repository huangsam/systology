---
title: "Privacy-First Identity & Access Management"
description: "Authentication and Authorization gateway with local-first isolation."
summary: "Design for an Auth0/Keycloak-style identity provider focused on OAuth2/OIDC federation, token lifecycle, and privacy-preserving RBAC."
tags: ["security", "privacy", "networking"]
categories: ["designs"]
draft: true
---

## Problem Statement & Constraints

Design a centralized Identity and Access Management (IAM) service. It must authenticate users, federate identity to internal microservices via tokens, and enforce centralized Role-Based Access Control (RBAC), all while adhering to strict privacy and data isolation principles.

### Functional Requirements

- User registration, login, and password management (or passwordless/MFA).
- Issue standard identity tokens (OIDC) and access tokens (OAuth2).
- Validate tokens for downstream services efficiently.
- Manage users, groups, and roles.

### Non-Functional Requirements

- **Scale:** Support 50M registered users, 10k authentications/sec.
- **Availability:** 99.999% uptime. If Auth is down, the entire platform is down.
- **Latency:** Token issuance < 200ms; Token validation < 5ms.
- **Security:** Immutable audit logs, hardened bcrypt/Argon2 hashing, protection against credential stuffing.

## High-Level Architecture

{{< mermaid >}}
graph TD
    Client[Web/Mobile] --> Edge[Edge Gateway]
    Edge --> AuthSvc[Auth Service]
    AuthSvc --> DB[(User DB)]
    AuthSvc --> Cache[(Session Cache / Redis)]

    Client -. "JWT Access Token" .-> Resource[Resource Microservice]
    Resource -. "Validate Signature" .-> JWKS[JWKS Endpoint]
{{< /mermaid >}}

Clients authenticate directly with the centralized Auth Service to receive a short-lived stateless JWT and a long-lived stateful Refresh Token. Downstream resource servers independently validate the JWT signatures using public keys fetched from the Auth Service's JWKS (JSON Web Key Set) endpoint, ensuring the Auth Service doesn't become a bottleneck for every network call.

## Data Design

### Secret & Key Management
- **Passwords:** Never stored in plaintext. Hashed exclusively using Argon2 or PBKDF2 with unique, per-user salts.
- **Signing Keys:** The private key used to sign JWTs is rotated regularly and managed via a secure KMS (Key Management Service).

### Core Schema (SQL)
| Table | Column | Type | Description |
| :--- | :--- | :--- | :--- |
| **users** | `id` | UUID (PK) | Immutable subject identifier. |
| | `email` | String | Encrypted or hashed for privacy. |
| | `password_hash` | String | Salty hash. |
| **sessions**| `session_id` | String | Refresh token ID. |
| | `user_id` | UUID | |
| | `expires_at`| Timestamp | |

## Deep Dive & Trade-offs

### Deep Dive

- **Stateless vs Stateful Tokens:** We use short-lived (e.g., 15 minute) JSON Web Tokens (JWTs) for fast, decentralized validation at the edge or within microservices. We use stateful, DB-backed Refresh Tokens for session revocation.
- **Data Minimization:** True to the [Privacy Agents]({{< ref "/principles/privacy-agents" >}}) principle, the central Auth system only knows what it must to assert identity. It does not store user profiles, application data, or behavioral logs.
- **RBAC in Tokens:** Role scopes are packed into the JWT payload (e.g., `"scopes": ["read:messages", "admin"]`). This allows downstream services to authorize actions immediately without a database round-trip.
- **Defense in Depth:** Rate limiting prevents brute force. Captchas stop botnets. Device fingerprinting detects anomalous logins (e.g., "New login from an unrecognized device in a new country").

### Trade-offs

- **JWT vs Opaque Tokens:** JWTs are stateless and incredibly fast to validate, but they cannot be easily revoked before they expire. Opaque tokens (where the microservice constantly asks the Auth server "is this string valid?") are perfectly revocable but create a massive bottleneck. The hybrid approach (Short JWT + State DB Refresh) balances these.
- **Token Bloat:** Packing too many claims, roles, or attributes into a JWT can make the HTTP headers massive, leading to bandwidth bloat and occasionally hitting proxy header size limits.
- **Centralized vs Decentralized DB:** A massive single database is easier to query, but sharding the user database by tenant or region dramatically improves blast-radius isolation in the event of a breach.

## Operational Excellence

- SLO: 99.99% successful login rate within 500ms.
- Security SLIs: failed_login_ratio (spikes indicate attacks), key_rotation_staleness.
- **Auditing:** Every permission change, role assignment, and login failure must emit an immutable event to a secure audit log for compliance.
