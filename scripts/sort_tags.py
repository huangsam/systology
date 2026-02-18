#!/usr/bin/env python3
"""
Sort tags in markdown files alphabetically. This helps with consistency and
makes it easier to find and manage tags.

Usage:
    python3 scripts/sort_tags.py
"""

import os
import re


def sort_tags(content: str) -> str:
    # Match tags: ["tag1", "tag2"] or tags: [tag1, tag2]
    match = re.search(r"^tags:\s*\[(.*?)\]", content, re.MULTILINE)
    if not match:
        return content

    tags_str = match.group(1)
    # Split by comma, strip whitespace and quotes
    tags = [t.strip().strip('"').strip("'") for t in tags_str.split(",") if t.strip()]

    # Sort tags alphabetically
    tags.sort()

    # Reconstruct the tags line
    new_tags_str = "tags: [" + ", ".join(f'"{t}"' for t in tags) + "]"

    # Replace the old tags line with the new one
    return content.replace(match.group(0), new_tags_str)


def process_directory(directory: str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".md"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    content = f.read()

                new_content = sort_tags(content)

                if new_content != content:
                    with open(path, "w") as f:
                        f.write(new_content)
                    print(f"Updated: {path}")


if __name__ == "__main__":
    content_dir = "site/content"
    process_directory(content_dir)
