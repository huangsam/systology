---
title: "Short title"
description: "Short description"
summary: "One-line summary used on index pages"
tags: []
categories: ["principles"]
draft: true
---

## Principle Name

Narrative explanation of why this principle matters, when to apply it, and what benefits or tradeoffs it introduces. Explain the reasoning—not just the tactic—so readers understand when this principle applies and when it might not.

Include language-specific or framework-specific guidance where helpful:

- In Rust/Go: concrete examples (traits, interfaces, design patterns)
- In Python/JavaScript: common idioms or libraries that support this principle
- Cross-language: the concept should transcend the implementation language

**Anti-pattern — Name and describe a common pitfall** that violates this principle. Use memorable examples (e.g., "Leaky Abstraction Avalanche," "Hot Key Blindness") so readers can spot similar issues in their own code. Explain why the anti-pattern seems attractive and what goes wrong when it's used.

## Decision Framework

Use this section to provide a clear heuristic or trade-off matrix for the principle. This should help the reader make a choice based on their specific constraints.

| If you need... | ...choose this | because... |
| :--- | :--- | :--- |
| **Constraint A** | Option 1 | Benefit/Trade-off |
| **Constraint B** | Option 2 | Benefit/Trade-off |

**Decision Heuristic:** "Choose **[Tactic]** when **[Context]** is more important than **[Alternative]**."

## Cross-principle Notes

Optionally, relate multiple principles to each other or reference other pages in the site that go deeper for a production example of this principle in practice.
