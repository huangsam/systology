# Agentic guidelines

## Purpose

This document captures practical guidance for building, testing, and operating "agents" used or referenced by the Systology project.

## Project layout

- `site/content/` — Markdown content (`deep-dives`, `designs`, `principles`)
- `site/layouts/` — Hugo templates
- `site/static/` — Static assets
- `scripts/` — Content maintenance utilities

## Tools and practices

Some things to keep in mind when working with the site content and related agents:

- Preview changes locally (`make serve` / `hugo server -D`) and visually inspect affected pages.
- Run content helpers and formatters: `make tidy`.
- Use `make build` and inspect `site/public/` (or PR preview site) to smoke-check output.

Do not run `make server` if it's already running. You can verify this with `lsof -i :1313`.

### Adding a new page

How to add a new page:

1. Run `hugo new -s site designs/foo.md` to create a new design page
2. Run `hugo new -s site deep-dives/bar.md` to create a new deep dive page
3. Run `hugo new -s site principles/baz.md` to create a new principle page
