#!/usr/bin/env python3
"""
Generate a Lunr.js-compatible search index from markdown content.
This helps support full-text search on the website.

Usage:
    python3 scripts/generate_search_index.py
"""

import json
from pathlib import Path
import re


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown."""
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return {}, content

    frontmatter = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key == "tags":
                # Parse tags from YAML list
                value = re.findall(r'"([^"]+)"', value)
            frontmatter[key] = value

    body = content[match.end() :]
    return frontmatter, body


def extract_preview(body: str, max_length: int = 150) -> str:
    """Extract first paragraph as preview."""
    # Remove markdown formatting
    body = re.sub(r"^#+\s+", "", body, flags=re.MULTILINE)
    body = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", body)  # Remove links
    body = re.sub(r"[*_`]", "", body)  # Remove formatting

    # Get first paragraph
    para = body.split("\n\n")[0].strip()
    if len(para) > max_length:
        para = para[:max_length].rsplit(" ", 1)[0] + "..."
    return para


def main() -> None:
    content_dir = Path("site/content")
    documents = []
    doc_id = 0

    # Scan all markdown files
    for md_file in sorted(content_dir.rglob("*.md")):
        if "_index.md" in md_file.name or md_file.name.startswith("."):
            continue

        with open(md_file, "r") as f:
            content = f.read()

        frontmatter, body = extract_frontmatter(content)

        # Skip if no title (malformed)
        if "title" not in frontmatter:
            continue

        # Determine category from path
        try:
            # Get the top-level directory relative to content_dir
            # e.g. site/content/deep-dives/foo.md -> deep-dives
            category = md_file.relative_to(content_dir).parts[0]
        except IndexError:
            category = "unknown"

        # Build document
        title = frontmatter.get("title", "")
        description = frontmatter.get("description", "")
        summary = frontmatter.get("summary", "")
        tags = frontmatter.get("tags", [])

        if description:
            preview = description
        else:
            preview = extract_preview(body)

        # Build searchable content (concatenate all text fields)
        searchable_content = f"{title} {description} {summary} {' '.join(tags) if isinstance(tags, list) else tags}".lower()

        # Extract URL-friendly slug
        slug = md_file.stem
        url = f"/{category}/{slug}/"

        doc = {
            "id": str(doc_id),
            "title": title,
            "description": description,
            "preview": preview,
            "tags": tags if isinstance(tags, list) else [tags],
            "category": category,
            "url": url,
            "content": searchable_content,
        }

        documents.append(doc)
        doc_id += 1

    # Generate Lunr index JSON
    index_data = {
        "documents": documents,
        "documentCount": len(documents),
    }

    # Write index
    output_path = Path("site/static/search-index.json")
    with open(output_path, "w") as f:
        json.dump(index_data, f)

    print(f"Generated search index with {len(documents)} documents")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
