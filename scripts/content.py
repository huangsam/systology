"""
Logic for content normalization and updating Systology site pages.
"""

import re
from pathlib import Path
from .constants import FM_DELIM, FM_TITLE, FM_SUMMARY, FM_DESC, MD_EXT, MAX_DESC_LEN
from .utils import extract_fm_body, parse_fm


def has_frontmatter(lines: list[str]) -> bool:
    """Check if a list of lines begins with frontmatter delimiters."""
    if not lines:
        return False
    first = lines[0].strip()
    return first in (FM_DELIM, "+++", "{")


def extract_first_h1(lines: list[str]) -> str | None:
    """Extract the first top-level Markdown heading from a list of lines."""
    for ln in lines:
        m = re.match(r"^#\s+(.*)", ln)
        if m:
            return m.group(1).strip()
    return None


def normalize_file(path: Path) -> bool:
    """Normalize the formatting and frontmatter of a single Markdown file."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False

    # Remove surrounding top-level ``` fences
    if lines and lines[0].startswith("```"):
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].startswith("```"):
                lines = lines[1:i]
                changed = True
                break

    if has_frontmatter(lines):
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return changed

    title = extract_first_h1(lines)
    if title:
        fm = [FM_DELIM, f'{FM_TITLE}: "{title.replace('"', "''")}"', FM_DELIM, ""]
        new = fm + lines
        path.write_text("\n".join(new) + "\n", encoding="utf-8")
        return True

    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    return False


def run_normalize(content_dir: Path) -> None:
    """Run normalization across all Markdown files in the content directory."""
    print("Running normalize_content...")
    count = 0
    for p in content_dir.rglob(f"*{MD_EXT}"):
        if p.is_file():
            if normalize_file(p):
                count += 1
    print(f"  Normalized {count} files")


def run_add_summary_desc(content_dir: Path) -> None:
    """Ensure all Markdown files have summary and description frontmatter fields."""
    print("Running add_summary_description...")
    count = 0
    for p in content_dir.rglob(f"*{MD_EXT}"):
        text = p.read_text(encoding="utf-8")
        fm_lines, body_lines = extract_fm_body(text)
        if fm_lines is None:
            continue

        fm = parse_fm(fm_lines)
        changed = False

        # If missing summary or description, extract from body
        if FM_SUMMARY not in fm or FM_DESC not in fm:
            body_text = " ".join([line.strip() for line in body_lines if line.strip()])
            body_text = re.sub(r"\{\{.*?\}\}", "", body_text)  # remove shortcodes
            body_text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", body_text)  # remove links
            snippet = body_text[:MAX_DESC_LEN].strip()
            if snippet:
                if FM_SUMMARY not in fm:
                    fm_lines.append(f'{FM_SUMMARY}: "{snippet}..."')
                    changed = True
                if FM_DESC not in fm:
                    fm_lines.append(f'{FM_DESC}: "{snippet}..."')
                    changed = True

        if changed:
            new_text = (
                FM_DELIM
                + "\n"
                + "\n".join(fm_lines)
                + "\n"
                + FM_DELIM
                + "\n"
                + "\n".join(body_lines)
                + "\n"
            )
            p.write_text(new_text, encoding="utf-8")
            count += 1
    print(f"  Updated {count} files")
