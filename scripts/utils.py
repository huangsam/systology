"""
Shared utility functions for Systology management scripts.
"""

import re
from .constants import FM_DELIM


def strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1].strip()
    return s


def extract_fm_body(text: str) -> tuple[list[str] | None, list[str]]:
    """Split Markdown text into frontmatter lines and body lines."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].strip() == FM_DELIM:
        j = i + 1
        while j < len(lines) and lines[j].strip() != FM_DELIM:
            j += 1
        if j >= len(lines):
            return None, lines[i:]
        return lines[i + 1 : j], lines[j + 1 :]
    return None, lines[i:]


def parse_fm(fm_lines: list[str]) -> dict[str, str]:
    """Parse frontmatter lines into a key-value dictionary."""
    fm = {}
    pattern = re.compile(
        r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(?:\"([^\"]*)\"|'([^']*)'|([^#].*))?"
    )
    for ln in fm_lines:
        m = pattern.match(ln)
        if m:
            key = m.group(1)
            val = m.group(2) or m.group(3) or (m.group(4).strip() if m.group(4) else "")
            fm[key] = val
    return fm
