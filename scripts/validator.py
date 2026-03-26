"""
Logic for validating Systology site content.
"""

import re
from pathlib import Path
from .constants import MD_EXT, FM_TITLE
from .utils import extract_fm_body, parse_fm


def check_file(p: Path, content_root: Path) -> list[str]:
    errors = []
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Could not read file: {e}"]

    fm_lines, body_lines = extract_fm_body(text)

    # 1. Frontmatter Validation
    if fm_lines is None:
        errors.append("Missing frontmatter")
    else:
        fm = parse_fm(fm_lines)
        if FM_TITLE not in fm or not fm[FM_TITLE].strip():
            errors.append(f"Missing '{FM_TITLE}' in frontmatter")

    # 2. Internal Link Validation
    base_dir = p.parent
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
    for _, link in links:
        link = link.strip()
        if link.startswith(("#", "http", "https", "mailto:", "tel:")):
            continue
        if "{{" in link or "}}" in link:
            continue

        target = None
        if link.startswith("/"):
            target = content_root / link.lstrip("/")
        else:
            target = base_dir / link

        if target and not target.exists():
            if target.with_suffix(MD_EXT).exists():
                target = target.with_suffix(MD_EXT)

        if target and not target.exists():
            errors.append(f"Broken link: {link}")

    # 3. Image Validation
    images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text)
    for _, src in images:
        src = src.strip()
        if src.startswith(("http", "https", "data:")):
            continue

        target = None
        if src.startswith("/"):
            static_dir = content_root.parent / "static"
            target = static_dir / src.lstrip("/")
        else:
            target = base_dir / src

        if target and not target.exists():
            errors.append(f"Missing image: {src}")

    return errors


def run_check(content_dir: Path) -> None:
    print("Running check...")
    error_count = 0
    for p in sorted(content_dir.rglob(f"*{MD_EXT}")):
        if p.name.startswith("."):
            continue
        file_errors = check_file(p, content_dir)
        if file_errors:
            print(f"\n{p.relative_to(content_dir.parent)}:")
            for err in file_errors:
                print(f"  - {err}")
                error_count += 1

    if error_count == 0:
        print("  No issues found.")
    else:
        print(f"\n  Found {error_count} issues.")
