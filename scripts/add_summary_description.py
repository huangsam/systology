#!/usr/bin/env python3
"""
Add `summary` and `description` frontmatter to markdown files under site/content
when missing. Uses `summary` (if present) or the first paragraph as a candidate
for `description` when needed.

Usage: python3 scripts/add_summary_description.py
"""

from pathlib import Path
import re

MAX_DESC = 160


def extract_frontmatter_and_body(text: str):
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        j = i + 1
        while j < len(lines) and lines[j].strip() != "---":
            j += 1
        if j >= len(lines):
            return None, text
        fm_lines = lines[i + 1 : j]
        body_lines = lines[j + 1 :]
        return fm_lines, body_lines
    return None, lines[i:]


def parse_fm_lines(fm_lines: list[str]) -> dict:
    fm: dict = {}
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


def first_paragraph(body_lines: list[str]) -> str:
    para: list[str] = []
    for ln in body_lines:
        if ln.strip() == "" and para:
            break
        if ln.strip().startswith("#"):
            continue
        para.append(ln)
    text = "\n".join(para).strip()
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_]{1,3}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_description(text: str, max_len: int = MAX_DESC) -> str:
    if not text:
        return text
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rfind(" ")
    if cut == -1:
        out = text[:max_len]
    else:
        out = text[:cut]
    out = out.rstrip(" ,;:.") + "…"
    return out


def insert_into_fm(fm_lines: list[str], key: str, value: str) -> list[str]:
    # Insert after title if present, else append at end of fm_lines
    out: list[str] = []
    inserted = False
    for ln in fm_lines:
        out.append(ln)
        if not inserted and re.match(r"^\s*title\s*:\s*", ln):
            out.append(f'{key}: "{value.replace('"', '\\"')}"')
            inserted = True
    if not inserted:
        out.append(f'{key}: "{value.replace('"', '\\"')}"')
    return out


def process_file(p: Path) -> bool:
    text = p.read_text(encoding="utf-8")
    fm_lines, body_lines = extract_frontmatter_and_body(text)
    if fm_lines is None:
        return False
    fm = parse_fm_lines(fm_lines)
    has_summary = "summary" in fm and fm["summary"].strip()
    has_description = "description" in fm and fm["description"].strip()
    if has_summary and has_description:
        return False

    # derive candidate
    candidate = None
    if "summary" in fm and fm["summary"].strip():
        candidate = fm["summary"].strip()
    else:
        cand = first_paragraph(body_lines)
        if cand:
            candidate = cand
    if not candidate:
        return False

    new_fm = fm_lines.copy()
    if not has_summary:
        new_fm = insert_into_fm(new_fm, "summary", candidate)
    if not has_description:
        desc = make_description(candidate, MAX_DESC)
        new_fm = insert_into_fm(new_fm, "description", desc)

    # Rebuild file
    new_text = (
        "---\n"
        + "\n".join(new_fm)
        + "\n---\n\n"
        + "\n".join(body_lines).lstrip()
        + "\n"
    )
    p.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "site" / "content"
    updated: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        try:
            if process_file(p):
                updated.append(p.relative_to(root))
        except Exception as e:
            print("ERROR", p, e)
    print(f"Updated {len(updated)} files")
    for u in updated:
        print(" -", u)


if __name__ == "__main__":
    main()
