---
title: "Distributed Web Crawler"
description: "High-scale, hostile-network data ingestion and graph traversal."
summary: "Design for a Google-scale web crawler focusing on Breadth-First Search (BFS), DNS resolution caching, robots.txt politeness, and handling duplicate or malicious domains."
tags: ["caching", "data-pipelines", "distributed-systems", "networking"]
categories: ["designs"]
draft: false
---

## Problem Statement & Constraints

Design a distributed web crawler (e.g., the ingestion agent for a search engine, or an LLM scraping bot). Unlike typical systems where you design the server and trust the client, a crawler must navigate millions of unknown, potentially hostile, and unpredictable third-party web servers.

### Functional Requirements

- Traverse the web starting from a set of seed URLs.
- Fetch HTML pages, extract metadata/text, and extract all outgoing links.
- Respect `robots.txt` and crawler "politeness" policies (don't DDoS a target site).
- Store HTML/text for downstream indexing/processing.

### Non-Functional Requirements

- **Scale:** Crawl 1 Billion pages per month (~380 pages/second).
- **Fault Tolerance:** Servers will abruptly close connections, timeout, or return malformed data. The crawler must never crash.
- **Network Efficiency:** DNS lookups are heavy. The system must cache DNS to avoid bottlenecking on network resolution.

## High-Level Architecture

{{< mermaid >}}
graph TD
    Seed[Seed URLs] --> Frontier[(URL Frontier Queue)]

    Frontier --> Workers[Fetcher Workers]

    Workers -.->|1. Resolve| DNS[Custom DNS Cache]
    Workers -.->|2. Check| Robots[Robots.txt Cache]
    Workers -->|3. GET| Web[The Internet]

    Workers --> Extractor[Link Extractor]
    Extractor --> URLFilter[URL Filter & Dedup]
    URLFilter --> Frontier

    Workers --> DocStore[(Document / Object Store)]
{{< /mermaid >}}

The architecture operates as a massive distributed Breadth-First Search (BFS). The **URL Frontier** manages the queue of known, unvisited URLs, ensuring fair distribution among target hosts. **Fetcher Workers** pull from the frontier, fetch the content, and push the HTML to storage. They pass the raw HTML to an **Extractor** which parses outbound links, deduplicates them against known URLs, and pushes novel links back into the Frontier.

## Data Design

### Storage Layers
- **Document Store (Blob/S3):** Stores the raw HTML payloads. This is extremely large (petabytes).
- **URL Checksum Database (Bloom Filter / Redis):** Quickly answers "Have we seen this exact URL before?" to prevent infinite loops.
- **Content Checksum Database:** Quickly answers "Have we seen this exact HTML payload before?" to deduplicate mirroring sites.

### State & Queue Management
- **URL Frontier:** A massive distributed priority queue. It must be larger than memory, so it is backed by disk (e.g., Kafka topics partitioned by domain name).

## Deep Dive & Trade-offs

### Deep Dive

- **The URL Frontier & Politeness:** We cannot just use a simple RabbitMQ queue. If `wikipedia.org` appears 10,000 times in the queue, a naive worker pool will fetch from Wikipedia 10,000 times concurrently, committing an accidental DDoS attack. The Frontier must be split into multiple sub-queues (one per domain). A worker only pulls from a domain's queue if *X* seconds have passed since the last fetch to that domain.
- **DNS Resolution Bottleneck:** A standard OS DNS resolver blocking on every HTTP request will cripple throughput. The crawler must maintain an enormous, distributed DNS cache to avoid standard UDP timeouts.
- **Bloom Filters for Deduplication:** Checking a SQL database if a URL exists 400 times a second is too slow and expensive. A Bloom Filter (a probabilistic data structure in memory) answers "Has this URL been crawled?" with extreme speed and minimal RAM. If it returns *yes*, it might be wrong (false positive), which is fine—we just skip crawling a page. If it returns *no*, it is mathematically guaranteed to be novel.
- **Spider Traps:** Malicious sites create infinite dynamic URLs (e.g., `site.com/a/b/c/d/...`). The crawler must strictly limit maximum depth from seed and maximum path lengths.
- **URL Normalization:** `example.com/page`, `example.com/page/`, and `example.com/page?` are often the same resource. Normalization (removing trailing slashes, sorting query parameters, removing fragments, lowercasing domain) is critical before deduplication. Otherwise the crawler wastes resources re-fetching the same content.
- **HTTP Semantics:** Respect status codes (200=cache, 301/302=redirect, 404=skip, 429=backoff, 5xx=retry) and cache headers (Cache-Control, ETag, Last-Modified). Ignoring these leads to wasted bandwidth and accidental DDoS on already-rate-limited sites.

### Trade-offs

- **BFS vs. DFS:** Breadth-First Search is strictly superior for standard crawling because Depth-First Search easily gets trapped on a single infinite sub-domain (a spider trap). However, BFS requires massively larger queue memory.
- **Freshness vs. Coverage:** Is it better to recrawl NYTimes.com every 5 minutes (Freshness) or crawl an obscure blog from 2004 once (Coverage)? The Priority Queue must score URLs heuristically (e.g., PageRank or historical change frequency) to balance these competing goals.

## Operational Excellence

- SLO: 99.9% of fetches complete or fail gracefully within 5 seconds.
- SLIs: `pages_downloaded_per_second`, `dns_resolution_latency`, `frontier_queue_depth`.
- **Hostile Monitoring:** Alert immediately on memory leaks in the Fetcher workers, as parsing malformed third-party HTML (via libraries like BeautifulSoup or lxml) is highly prone to catastrophic failure.
