---
title: "SQL vs. NoSQL"
description: "Choosing the right database paradigm for your system."
summary: "A framework for deciding between SQL (relational, ACID) and NoSQL (distributed, flexible schema) databases based on data structure, scalability needs, and consistency requirements."
tags: ["data-design", "storage"]
categories: ["principles"]
draft: true
---

## The Core Philosophy

Centralized/Structured (SQL) vs. Distributed/Flexible (NoSQL).

SQL databases (PostgreSQL, MySQL) are built on the relational model. Data is stored in tables with rigid schemas, and relationships are enforced via foreign keys. They prioritize ACID transactions and consistency. NoSQL databases (Cassandra, MongoDB, DynamoDB) emerged to handle massive scale. They prioritize horizontal scalability, schema flexibility, and often trade strict consistency for availability and partition tolerance (CAP theorem).

## When to Use SQL

Use SQL when you need strict ACID compliance, data is highly structured with complex relationships, and read/write load can be handled by a single massive master node or read replicas.

**Ideal Use Cases:** Financial systems, billing platforms, inventory management, or any application where data integrity is the absolute highest priority and relationships between entities are complex.

**Anti-pattern — Premature NoSQL:** Choosing MongoDB for a typical CRUD application with clear, unchanging relationships (like Users, Posts, Comments) just because it "scales." You will end up writing application-level code to enforce relationships and perform joins, essentially poorly reinventing a relational database in your application layer.

## When to Use NoSQL

Use NoSQL when you need massive horizontal write scalability, schema flexibility, rapid iteration, and can tolerate eventual consistency (BASE semantics).

**Ideal Use Cases:** High-velocity logging, document catalogs, real-time leaderboards, social network graphs, or massive key-value stores.

**Anti-pattern — Forcing Relationships:** Trying to maintain complex, multi-entity transactions or heavy relational queries in a NoSQL database. If your queries constantly require you to fetch a document, extract keys, and fetch related documents (application-side joins), you probably need a relational database.

## Types of NoSQL

"NoSQL" is not a single technology. It's an umbrella term for non-relational databases.

*   **Key-Value (Redis, DynamoDB):** The simplest model. Highly performant for simple lookups. Best for caching, session management, or simple configurations.
*   **Document (MongoDB, Couchbase):** Stores data as JSON-like documents. Great for un-normalized data with varying structures (e.g., user profiles, product catalogs).
*   **Wide-Column (Cassandra, HBase):** Optimized for heavy write throughput and querying by row/column keys. Best for time-series data or massive event logging.
*   **Graph (Neo4j):** Optimized for storing and traverses relationships (nodes and edges). Best for recommendation engines or social networks.

## The CAP Theorem Context

Understand how your choice maps to the CAP theorem (Consistency, Availability, Partition Tolerance).

In a distributed system, you must tolerate partitions (P). This leaves a choice between Consistency (C) and Availability (A) during a network partition.
*   **SQL (typically CP):** Prioritizes consistency. If a node goes down or a partition occurs, the system might refuse writes to prevent inconsistent states.
*   **NoSQL (often AP):** Prioritizes availability. During a partition, nodes might accept writes independently, resolving conflicts later (eventual consistency).

## Decision Framework

Choose your database based on data structure and scale:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **ACID Guarantees** | SQL (PostgreSQL, MySQL) | It enforces strict consistency and handles complex multi-table transactions natively. |
| **Schema Flexibility** | Document (MongoDB) | It allows rapid iteration on data models without expensive schema migrations. |
| **Massive Write Scale** | Wide-Column (Cassandra) | It scales horizontally seamlessly and handles high-velocity ingestion without locking. |
| **Relationship Traversal** | Graph (Neo4j) | It traverses complex networks efficiently, rather than expensive SQL `JOIN`s. |

**Decision Heuristic:** "Start with **PostgreSQL** (SQL). Only move to **NoSQL** when you have a specific, overriding requirement (like massive horizontal write scaling or a highly unstructured dataset) that relational databases cannot solve efficiently."
