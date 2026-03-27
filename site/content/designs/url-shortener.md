---
title: "URL Shortener & Pastebin"
description: "Unique ID generation patterns and robust distributed caching."
summary: "A robust structural design for a highly available, extremely read-heavy service bridging short aliases to long URLs; implementing Base62 encoding, Snowflake IDs, and strict collision avoidance."
tags: [algorithms, caching, encoding, redirection]
categories: ["designs"]
draft: false
date: "2026-02-24T22:57:53-08:00"
---

## Problem Statement & Constraints

Design a URL shortening service (like TinyURL or bit.ly) or a Pastebin that accepts a long string of data and returns a highly compact, unique alias. When a user navigates to the short alias, they must be seamlessly redirected to the original destination.

### Functional Requirements

- Given a long URL, return an alias (e.g., `https://sh.rt/8aBc1`).
- Redirect an alias to its original URL via HTTP 301/302.
- (Optional) Allow users to specify a custom vanity alias.
- (Optional) Enforce link expiration.

### Non-Functional Requirements

- **Scale:** High read-to-write ratio (100:1). E.g., 100M new URLs per month, 10B redirects per month.
- **Availability:** Extremely high availability (99.999%). If redirects fail, all links in the world break.
- **Latency:** Server-side redirect processing must happen in < 10ms (excluding network round-trip).
- **Data Retention:** Keep data for 5 years by default. (100M/month * 12 * 5 = 6 Billion links total).

## High-Level Architecture

{{< mermaid >}}
graph TD
    User([User]) --> Edge[CDN / API Gateway]

    %% Write Path
    Edge -->|POST /api/v1/shorten| WriteAPI[Write Service]
    WriteAPI --> IDGen[ID Generator<br/>Snowflake]
    WriteAPI --> DBPrimary[DB Primary]
    DBPrimary --> DBReplica[DB Replica]

    %% Read Path
    Edge -->|GET /8aBc1| EdgeCache[Edge Cache]
    EdgeCache -->|Hit| User
    EdgeCache -->|Miss| ReadAPI[Read Service]
    ReadAPI --> RedisCache[Redis Cache]
    RedisCache -->|Hit| ReadAPI
    RedisCache -->|Miss| ReadAPI
    ReadAPI -->|Fetch| DBReplica
{{< /mermaid >}}

Reads and writes are logically (or physically) separated. The Write Service relies on a distributed ID generator to avoid database write collisions before converting the numerical ID to a Base62 string. The Read Service heavily leverages a Redis cache (and CDN edge caching) to serve 301 redirects instantly without touching the persistent store.

## Data Design

### Unique Identifier Math
To store 6 Billion links, we need an alias length. Using Base62 ([a-z, A-Z, 0-9]):
- 6 character alias = 62 ^ 6 = ~56.8 Billion possible combinations.
This easily covers the 6 Billion requirement, so a 6 or 7 character string is sufficient.

### Storage Schema (NoSQL or SQL)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | BigInt (PK) | Unique numerical ID (from Snowflake or DB sequence). |
| `hash` | String(7) | Base62 encoded version of the ID (e.g., `8aBc1`). Indexed. |
| `long_url` | String(2048) | The destination. |
| `created_at` | Timestamp | |
| `expires_at` | Timestamp | For automatic cleanup mechanisms. |

*Note: Since there are no complex joins, a Wide-Column store like Cassandra/DynamoDB is excellent here, but PostgreSQL is also perfectly fine for 6 Billion rows if partitioned or indexed on the `hash`.*

## Deep Dive & Trade-offs

### Deep Dive

- **ID Generation (Snowflake vs. Auto-Increment):** Using a single PostgreSQL database with an `AUTO_INCREMENT` primary key creates a massive single point of failure and write bottleneck. Instead, use Twitter's **Snowflake** algorithm: a decentralized microservice that generates unique 64-bit integers based on the current timestamp, a machine ID, and an internal counter. This provides highly available, causally-ordered IDs with no per-ID network call (though machine IDs must be pre-assigned via coordination, e.g., ZooKeeper).
- **Base62 Encoding:** Rather than hashing the URL directly (which requires checking the DB for hash collisions), we take the practically unique [Snowflake ID](https://en.wikipedia.org/wiki/Snowflake_ID) (e.g., `2009215674938`)—unique assuming correct machine ID assignment and well-behaved clocks—and simply convert it from Base10 to Base62.
- **Custom Vanity Aliases:** When a user requests `https://sh.rt/my-sale`, the system cannot use the ID Generator. It must attempt to insert the record with a `hash` of `my-sale`. If the DB throws a unique constraint violation, the service rejects the request.

### Trade-offs

- **HTTP 301 vs. 302 Redirects:**
  - **301 (Moved Permanently):** The browser aggressively caches the redirect. This drastically reduces the load on your servers, but you lose the ability to track click analytics (because the browser never contacts your server again for that link).
  - **302 (Found):** The redirection is temporary. The browser will hit your server every single time by default. This allows real-time metric tracking at the cost of higher server load. (Note: CDN edge caches can still cache 302s if explicit `Cache-Control` headers are set, so 302 does not inherently prevent all caching.)
- **Hash Collisions (Truncated Hashing vs. Unique ID):** If we hashed the long URL (e.g., with MD5 or SHA-256) and took the first 7 characters, two different URLs could easily collide on those characters—the collision risk comes from truncation (~35–42 bits of entropy), not from the hash algorithm itself. Generating a unique integer first and encoding it Base62 avoids the collision problem entirely.

## Operational Excellence

- SLO: 99.9% of redirects (reads) < 10ms. 99.9% of generation (writes) < 100ms.
- SLIs: `cache_hit_ratio`, `id_generation_exhaustion`, `redirect_latency_p99`.
- **Scaling:** If cache hit ratio drops unexpectedly (e.g., a massive spike of *distinct* URLs rather than one viral URL), the DB read capacity must instantly auto-scale.
