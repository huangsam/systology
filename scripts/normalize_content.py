#!/usr/bin/env python3
"""
Strip top-level Markdown code fences and add YAML title frontmatter
to Markdown files under `site/content/` when missing, using the
first H1 (`# Title`) as the title.

Usage:
    python3 scripts/normalize_content.py
"""

import re
from pathlib import Path


def has_frontmatter(lines: list[str]) -> bool:
    """Check if the first line is frontmatter."""
    if not lines:
        return False
    first: str = lines[0].strip()
    return first in ("---", "+++", "{")


def extract_first_h1(lines: list[str]) -> str | None:
    """Extract the first H1 from the lines."""
    for ln in lines:
        m = re.match(r"^#\s+(.*)", ln)
        if m:
            return m.group(1).strip()
    return None


def process_file(path: Path) -> bool:
    """Process a single file."""
    text: str = path.read_text(encoding="utf-8")
    lines: list[str] = text.splitlines()

    changed: bool = False

    # Remove surrounding top-level ``` fences if present
    if lines and lines[0].startswith("```"):
        # find closing fence
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].startswith("```"):
                inner = lines[1:i]
                lines = inner
                changed = True
                break

    # If there's already frontmatter, we won't add title
    if has_frontmatter(lines):
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return changed

    title = extract_first_h1(lines)
    if title:
        fm = ["---", f'title: "{title.replace('"', "''")}"', "---", ""]
        new = fm + lines
        path.write_text("\n".join(new) + "\n", encoding="utf-8")
        return True

    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    return False


def main() -> None:
    root: Path = Path(__file__).resolve().parents[1] / "site" / "content"
    if not root.exists():
        print("site/content not found")
        return

    updated = []
    for p in root.rglob("*.md"):
        if p.is_file():
            if process_file(p):
                updated.append(str(p.relative_to(root.parent)))

    print(f"Updated {len(updated)} files")
    for u in updated[:50]:
        print(" -", u)


if __name__ == "__main__":
    main()
