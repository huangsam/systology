---
title: "Real-Time Collaborative WebApp"
description: "Stateful synchronization for multiplayer web applications."
summary: "Design for a Google Docs or Figma style application using WebSockets, Operational Transformation (OT), or CRDTs to maintain consistent state among concurrent writers."
tags: ["concurrency", "distributed-systems", "real-time"]
categories: ["designs"]
draft: true
---

## Problem Statement & Constraints

Design a system to support real-time, multi-user collaboration on a shared document or canvas (e.g., Figma, Google Docs). Multiple users must see each other's cursor movements and edits with sub-second latency, and the system must gracefully handle concurrent, conflicting modifications without data corruption.

### Functional Requirements

- Real-time cursor presence and typing indicators.
- Synchronize document state across all active users.
- Resolve conflicting edits automatically and deterministically.
- Persist the document for offline reading/editing.

### Non-Functional Requirements

- **Latency:** End-to-end sync < 100ms for active typers.
- **Scale:** 100+ concurrent users per document; tens of thousands of active documents.
- **Consistency:** Eventual consistency is required—all users must converge on the exact same document state after all operations are applied.

## High-Level Architecture

{{< mermaid >}}
graph TD
    UserA[Client A] <-->|WebSocket| WS1[Collab Server 1]
    UserB[Client B] <-->|WebSocket| WS1
    UserC[Client C] <-->|WebSocket| WS2[Collab Server 2]

    WS1 <--> PubSub[(Redis Pub/Sub)]
    WS2 <--> PubSub

    WS1 -.-> Store[(Doc Store / DB)]
    WS2 -.-> Store
{{< /mermaid >}}

Clients maintain persistent, stateful WebSocket connections to Collaborative Servers. State synchronization is managed using an algorithmic approach—like Conflict-Free Replicated Data Types (CRDTs). Edits are broadcast via a publish/subscribe bus to alert other connected nodes. Periodically, the in-memory state is flushed to durable storage.

## Data Design

Unlike a stateless CRUD app, the core data model here revolves around a log of operations rather than the final state itself.

### The Operation Stream
Every action is modeled as an atomic operation.
- Example Operation: `{ type: "insert", pos: 142, char: "H", replicaId: "A", clock: 7 }`

### Storage Strategy
- **In-Memory:** Active documents are held in memory on the Collab Servers (or in Redis) for immediate broadcast.
- **Cold Storage:** A PostgreSQL or document database stores snapshots of the document to avoid replaying thousands of operations when a new client loads a large doc.

## Deep Dive & Trade-offs

### Deep Dive

- **CRDTs (Conflict-Free Replicated Data Types):** Rather than locking the document or forcing a central server to mediate every character (Operational Transformation), CRDT algorithms (like Yjs or Automerge) mathematically guarantee that if two clients apply the same set of operations—regardless of the order they arrive over the network—they will reach the same final state.
- **Session Affinity (Sticky Sessions):** To minimize latency, routing all users viewing "Document 123" to the same physical Collab Server node is highly efficient. This avoids the cost of going through the Redis Pub/Sub layer for users in the same room.
- **Presence (Ephemeral State):** Cursor positions and "User is typing..." indicators don't need to be durably saved. These are broadcast directly via WebSockets and dropped if a user disconnects.

### Trade-offs

- **CRDTs vs OT:** Operational Transformation (Google Docs) requires a central server to sequence operations, which is fundamentally harder to scale horizontally. CRDTs are decentralized and theoretically simpler, but their metadata (tombstones for deleted characters) can grow boundlessly, requiring sophisticated garbage collection algorithms.
- **WebSocket Connection Management:** WebSockets hold open file descriptors. A server might handle 10k connections. Load balancing becomes difficult because you can't easily drain connections without interrupting the user experience.
- **Snapshots vs Pure Event Sourcing:** Storing every single keystroke allows for infinite "Undo" and perfect history replay. However, the database size grows linearly with time. Taking periodic flattening snapshots is required to keep initial load times reasonable.

## Operational Excellence

- SLO: 99% of presence updates broadcast in < 50ms.
- SLIs: `websocket_connection_drops`, `document_load_time`, `memory_per_active_doc`.
- **Throttling:** Throttle high-frequency events (like mouse coordinates) at the client-side to e.g., 20 frames per second to avoid flooding the WebSocket buffers.
