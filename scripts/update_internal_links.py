#!/usr/bin/env python3
"""
Update internal Markdown links in `site/content/` to remove .md extensions and
convert to absolute paths. For example, `[Link](./other.md)` becomes `[Link](/current/dir/other)`.

Usage: python3 scripts/update_internal_links.py
"""

import re
from pathlib import Path


def update_links_in_file(p: Path) -> bool:
    text: str = p.read_text(encoding="utf-8")
    original: str = text

    # Get the relative path from content/
    rel_path = p.relative_to(Path("site/content"))
    parts = rel_path.parts

    def replace_link(match: re.Match) -> str:
        full: str = match.group(0)
        link: str = match.group(2)
        if link.endswith(".md"):
            # Remove .md
            link = link[:-3]
            if link.startswith("../"):
                # Go up to root level
                up_count: int = link.count("../")
                new_link = "/" + link[3 * up_count :]
            elif link.startswith("./"):
                new_link = "/" + "/".join(parts[:-1]) + "/" + link[2:]
            elif "/" not in link:
                # same dir
                new_link = "/" + "/".join(parts[:-1]) + "/" + link
            else:
                new_link = "/" + link
            return f"[{match.group(1)}]({new_link})"
        return full

    # Regex for [text](link)
    pattern: str = r"\[([^\]]+)\]\(([^)]+)\)"
    new_text: str = re.sub(pattern, replace_link, text)

    if new_text != original:
        p.write_text(new_text)
        return True
    return False


if __name__ == "__main__":
    root: Path = Path("site/content")
    count: int = 0
    for md in root.rglob("*.md"):
        if update_links_in_file(md):
            count += 1
    print(f"Updated {count} files")
