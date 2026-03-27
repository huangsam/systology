# Agentic guidelines

## Purpose

This document captures practical guidance for building, testing, and operating "agents" used or referenced by the Systology project.

## Project layout

- `site/content/` — Markdown content (`deep-dives`, `designs`, `principles`)
- `site/layouts/` — Hugo templates
- `site/static/` — Static assets
- `scripts/` — Content maintenance utilities

## Tools and practices

When working with the site content and related agents:

- Preview changes locally (`make serve` / `hugo server -D`) and visually inspect affected pages.
- Run content helpers and formatters: `make tidy`.
- Run content validation: `make check`.
- Use `make build` and inspect `site/public/` (or PR preview site) to smoke-check output.

When running a subagent or curl statements:

- Ensure that you run `make serve` first to start the local server on port 1313
- Use `lsof -i :1313` to check if the server is already running before starting it again

### Adding a new page

When adding a new page, follow these steps:

- Run `hugo new -s site -k designs designs/foo.md` to create a new design page
- Run `hugo new -s site -k deep-dives deep-dives/bar.md` to create a new deep dive page
- Run `hugo new -s site -k deep-dives-comparative deep-dives/bar.md` to create a new deep dive page
- Run `hugo new -s site -k principles principles/baz.md` to create a new principle page

When determining what tags to put on the new page:

- Run `make insights` to get recommendations based on existing taxonomy (LLM feedback loop).
- Refer to `make tags` to see a list of all existing tags and their usage counts.
- Choose tags that are relevant to the content, but avoid over-tagging (3-5 is good).
- Prioritize "Established" tags (in brackets from `make insights`) to maintain consistency.
- If a new tag is needed, ensure other pages are updated to use it where relevant.

### Tagging Feedback Loop

To reduce token spend and maintain a consistent taxonomy, agents should rely on the local `make insights` tool rather than asking the LLM to "invent" categories. This provides a deterministic bridge between the current content and the repository's established site-wide categories.

#### Mermaid diagrams

When adding a Mermaid diagram:

- Use the `{{< mermaid >}}` shortcode to embed Mermaid diagrams in your Markdown content
- Ensure that your Mermaid syntax is correct and renders properly in the local preview

When deciding between top-down (TD) and left-right (LR) graph orientations:

- Use `TD` for system topologies, where flow is hierarchical or has high branch factor
- Use `LR` for data pipelines, where flow is linear or has left-to-right tendencies
