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

- Run `hugo new -s site designs/foo.md` to create a new design page
- Run `hugo new -s site deep-dives/bar.md` to create a new deep dive page
- Run `hugo new -s site principles/baz.md` to create a new principle page

When determining what tags to put on the new page:

- Refer to the existing tags in the `site/content/` directory for consistency
- Run `make tags` to see a list of all existing tags and their usage counts
- Choose tags that are relevant to the content, but avoid over-tagging (3-5 is good)
- If a tag is used once, consider whether it should be merged with an existing tag
- If a new tag is needed, ensure other pages are updated to use it where relevant

#### Mermaid diagrams

When adding a Mermaid diagram:

- Use the `{{< mermaid >}}` shortcode to embed Mermaid diagrams in your Markdown content
- Ensure that your Mermaid syntax is correct and renders properly in the local preview

When deciding between top-down (TD) and left-right (LR) graph orientations:

- Use `TD` for system topologies, where the flow is naturally hierarchical
- Use `LR` for data/processing pipelines, where the flow is more linear and left-to-right
