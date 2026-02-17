# AGENTS

## Purpose

This document captures practical guidance for building, testing, and operating "agents" (automation components, RAG/assistant integrations, and similar workflows) used or referenced by the Systology projects.

## Project layout (where to edit)

- `site/content/` — markdown content (sections: `deep-dives`, `designs`, `principles`)
- `site/layouts/` — Hugo templates
- `site/static/` — static assets (CSS, images)
- `scripts/` — content maintenance utilities (normalize, tag frequency, internal links)

## Tools and practices

Some things to keep in mind when working with the site content and related agents:

- Preview changes locally (`make serve` / `hugo server -D`) and visually inspect affected pages.
- Run content helpers and formatters: `make tidy`.
- Use `make build` and inspect `site/public/` (or PR preview site) to smoke-check output.

Do not run `make server` if it's already running. You can verify this with `lsof -i :1313`.

### Adding a new page

How to add a new page:

1. Create `site/content/<section>/my-note.md` using kebab-case filename.
2. Add front matter (title, description, summary, tags, categories).
    ```yaml
    ---
    title: "My Note"
    description: "Short description"
    summary: "One-line summary used on index pages"
    tags: ["tag1", "tag2"]
    categories: ["designs"]
    ---
    ```
