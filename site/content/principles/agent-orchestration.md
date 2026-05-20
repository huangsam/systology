---
title: "Agent Orchestration"
description: "Coordinating multi-agent systems and long-running workflows."
summary: "Principles for architecting autonomous multi-agent systems; focusing on stateful orchestration, unified memory across agents, hand-off protocols, and human-in-the-loop governance for long-running workflows."
tags: [dispatch, machine-learning, orchestration, synchronization]
categories: ["principles"]
draft: false
date: "2026-03-17T09:54:30-07:00"
---

## Multi-Agent Coordination

Decompose complex tasks into specialized agents governed by structured state-machine graphs. Designing deterministic execution flows with explicit state transitions ensures predictable agent behavior. A single "God Agent" suffers from context dilution and high error rates, whereas structured, specialized agents provide modularity and better control.

Implement a state-machine or coordinator-worker pattern where transitions are handled by code routing or schema-constrained decisions rather than open-ended dialogue. The coordinator manages high-level planning, state transitions, and task decomposition, while specialized workers execute restricted, domain-specific tasks (e.g., "Research Agent," "Coding Agent," "Verification Agent"). Enforce schema-guided decoding or native structured outputs (like JSON schema constraint parameters in modern model APIs) at all boundaries to guarantee type-safety and eliminate downstream format parser errors.

{{< mermaid >}}
graph TD
    User --> Coordinator[Coordinator Agent<br>Planning & Routing]
    Coordinator --> Worker1[Research Agent<br>Search & Retrieval]
    Coordinator --> Worker2[Execution Agent<br>Code & Tool Use]
    Coordinator --> Worker3[Review Agent<br>Verification & QA]
    Worker1 --> Coordinator
    Worker2 --> Coordinator
    Worker3 --> Coordinator
    Coordinator --> Output[Final Result]
{{< /mermaid >}}

**Anti-pattern — Unconstrained Peer-to-Peer Chat:** Allowing agents to communicate autonomously with each other in an open-ended loop without strict code-level state constraints. This pattern leads to conversational infinite loops, rapid context-window saturation, high latency, and compounding errors.

**Anti-pattern — Parsing-based JSON Extraction:** Relying on natural-language instructions to output JSON and building custom parser retry loops to handle syntax errors. This is highly fragile. Modern APIs support native schema-guided output constraints (Structured Outputs) which guarantee schema adherence at the token generation level.

**Anti-pattern — The Monolithic Agent:** Forcing a single model instance to handle research, planning, execution, and self-correction in a single long prompt. This increases the chance of hallucinations and makes it impossible to swap specialized models for specific sub-tasks (e.g., using a cheaper model for research and a stronger one for coding).

## Stateful Workflow Persistence

Treat agentic workflows as long-running state machines that can be paused, resumed, and audited. Agents should not rely on ephemeral in-memory state for multi-day tasks.

Store the "Agent State" (history, goals, variables, tool outputs) in a persistent database (PostgreSQL, Redis). This enables resilience against process crashes and allows for long-running "human-in-the-loop" pauses where the agent waits for approval. Use a versioned state schema so that agents can migrate state across updates.

**Anti-pattern — Ephemeral Action Loops:** Running an agent in a simple `while` loop without persisting state to disk. If the process dies or the connection drops after 4 hours of work, the agent loses everything and must restart from scratch.

## Unified Memory & Context Management

Maintain a shared "blackboard" or memory layer that agents can read from and write to. Context should be managed as a first-class resource, pruned and summarized to avoid context window overflow.

Differentiate between:
1. **Short-term Memory**: The immediate conversation/action history.
2. **Medium-term Memory**: A persistent "scratchpad" for the current task.
3. **Long-term Memory**: Vector-indexed historical knowledge and user preferences.

Use a "Memory Manager" to summarize old context and inject relevant snippets into the agent's prompt based on the current sub-goal.

## Human-in-the-loop (HITL) Orchestration

Design for "meaningful human control" by inserting checkpoints for high-risk actions. Automation is most effective when it augments human decision-making rather than replacing it blindly.

Define "Action Risk Levels":
- **Low Risk**: Read-only actions, internal thoughts (Auto-approve).
- **Medium Risk**: File modifications, draft emails (Notify-on-success).
- **High Risk**: Deleting data, sending payments, merging code (Require explicit approval).

Build UIs that surface the agent's *reasoning* alongside the proposed action, not just the result.

## Decision Framework

Choose your orchestration pattern based on task complexity and reliability needs:

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **High Accuracy** | Decomposed Workers | Specialized prompts and tools per domain reduce noise. |
| **Resilience** | Stateful State Machines | Enables recovery from failures and long-running pauses. |
| **Transparency** | Reasoning Traces | Allows humans to audit *why* an action was proposed. |
| **Safety** | Explicit Approval Gates | Prevents autonomous agents from causing irreversible damage. |

**Decision Heuristic:** "Choose **Multi-Agent Decomposition** when the task requires more than 3 distinct logical steps. Use **explicit approval gates** for any action that affects user data or financial state."
