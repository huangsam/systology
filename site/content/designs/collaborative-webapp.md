---
title: "Real-Time Collaborative WebApp"
description: "Synchronization patterns for multiplayer web applications."
summary: "A real-time synchronization design for collaborative applications (e.g., Google Docs, Figma); utilizing WebSockets and Operational Transformation (OT) or CRDTs for consistent state resolution."
tags: [concurrency, distributed-systems, networking]
categories: ["designs"]
draft: false
date: "2026-02-24T22:34:51-08:00"
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

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | Enum | E.g., `insert`, `delete`, `retain`. |
| `pos` | Integer | The absolute position in the document text array. |
| `char` | String | The character being inserted (or omitted if delete). |
| `replicaId` | String | Unique ID of the client originating this operation. |
| `clock` | Integer | Logical timestamp (Lamport clock) to enforce causal ordering. |

### Storage Strategy
- **In-Memory:** Active documents are held in memory on the Collab Servers (or in Redis) for immediate broadcast.
- **Cold Storage:** A PostgreSQL or document database stores snapshots of the document to avoid replaying thousands of operations when a new client loads a large doc.

## Deep Dive & Trade-offs

{{< pseudocode id="crdt-merge" title="Basic LWW (Last-Write-Wins) Map Merge" >}}
```javascript
class LWWMap {
  constructor(replicaId) {
    this.replicaId = replicaId;
    this.data = new Map();      // Key -> Value
    this.timestamps = new Map(); // Key -> Logical Clock (timestamp)
  }

  set(key, value, timestamp, incomingReplicaId) {
    const currentTimestamp = this.timestamps.get(key) || 0;

    // Only apply the update if the incoming timestamp is strictly greater,
    // or if timestamps tie but the incoming replica ID is lexicographically larger.
    if (timestamp > currentTimestamp ||
       (timestamp === currentTimestamp && incomingReplicaId > this.replicaId)) {
      this.data.set(key, value);
      this.timestamps.set(key, timestamp);
    }
  }

  merge(remoteMap) {
    for (const [key, remoteTimestamp] of remoteMap.timestamps) {
      const remoteValue = remoteMap.data.get(key);
      this.set(key, remoteValue, remoteTimestamp, remoteMap.replicaId);
    }
  }
}
```
{{< /pseudocode >}}

### Deep Dive

- **CRDTs (Conflict-Free Replicated Data Types):** Rather than locking the document or forcing a central server to mediate every character (Operational Transformation), CRDT algorithms (like Yjs or Automerge) mathematically guarantee that if two clients apply the same set of operations—regardless of the order they arrive over the network—they will reach the same final state.
- **Session Affinity (Sticky Sessions):** To minimize latency, routing all users viewing "Document 123" to the same physical Collab Server node is highly efficient. This avoids the cost of going through the Redis Pub/Sub layer for users in the same room.
- **Presence (Ephemeral State):** Cursor positions and "User is typing..." indicators don't need to be durably saved. These are broadcast directly via WebSockets and dropped if a user disconnects.

### Trade-offs

- **CRDTs vs OT:** Operational Transformation (Google Docs) requires per-document operation sequencing through a coordination point, which adds a step that CRDTs avoid (though OT scales well in practice by sharding on document ID). CRDTs are decentralized and theoretically simpler, but their metadata (tombstones for deleted characters) can grow boundlessly, requiring sophisticated garbage collection algorithms.
- **WebSocket Connection Management:** WebSockets hold open file descriptors. A server might handle 10k connections. Load balancing becomes difficult because you can't easily drain connections without interrupting the user experience.
- **Snapshots vs Pure Event Sourcing:** Storing every single keystroke allows for infinite "Undo" and perfect history replay. However, the database size grows linearly with time. Taking periodic flattening snapshots is required to keep initial load times reasonable.

## Operational Excellence

- SLO: 99% of presence updates broadcast in < 50ms.
- SLIs: `websocket_connection_drops`, `document_load_time`, `memory_per_active_doc`.
- **Throttling:** Throttle high-frequency events (like mouse coordinates) at the client-side to e.g., 20 frames per second to avoid flooding the WebSocket buffers.
