"""
Logic for managing Systology site metadata (tags, etc.).
"""

import os
import re
import json
from pathlib import Path
from collections import Counter, defaultdict
from .constants import FM_DELIM, FM_TAGS, MD_EXT, TAG_ALIASES, TAG_REMOVALS
from .utils import _strip_quotes


def run_sort_tags(content_dir: Path) -> None:
    print("Running sort_tags...")
    count = 0
    for p in content_dir.rglob(f"*{MD_EXT}"):
        content = p.read_text(encoding="utf-8")
        # simplistic toggle for block vs inline
        # inline: tags: [a, b]
        m = re.search(r"^\s*" + FM_TAGS + r"\s*:\s*\[([^\]]*)\]", content, re.MULTILINE)
        if m:
            tags_str = m.group(1)
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            sorted_tags = sorted(list(set(tags)))
            if tags != sorted_tags:
                new_tags_str = ", ".join(sorted_tags)
                new_content = content.replace(f"[{tags_str}]", f"[{new_tags_str}]")
                p.write_text(new_content, encoding="utf-8")
                count += 1
    print(f"  Sorted tags in {count} files")


def parse_tags_from_text(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FM_DELIM:
        return []

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FM_DELIM:
            end_idx = i
            break
    if end_idx is None:
        return []

    fm_text = "\n".join(lines[1:end_idx])

    # Inline list
    m = re.search(r"^\s*" + FM_TAGS + r"\s*:\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
    if m:
        return [_strip_quotes(p) for p in m.group(1).split(",") if p.strip()]

    # Single scalar
    m = re.search(
        r"^\s*" + FM_TAGS + r"\s*:\s*([\'\"]?[^\n\'\"]+[\'\"]?)\s*$",
        fm_text,
        re.MULTILINE,
    )
    if m:
        return [_strip_quotes(m.group(1))]

    # Block list
    block_start = None
    lines_fm = fm_text.splitlines()
    for idx, line in enumerate(lines_fm):
        if re.match(r"^\s*" + FM_TAGS + r"\s*:\s*$", line):
            block_start = idx
            break
    if block_start is not None:
        tags = []
        for line in lines_fm[block_start + 1 :]:
            if re.match(r"^\s*-\s+(.+)", line):
                tags.append(_strip_quotes(re.sub(r"^\s*-\s+", "", line).strip()))
            elif line.strip() and not line[0].isspace():
                break
        return tags
    return []


def run_tag_stats(
    content_dir: Path, min_count: int, top: int, json_out: bool, show_files: bool
) -> None:
    counter = Counter()
    files_for_tag = defaultdict(list)

    for md in content_dir.rglob(f"*{MD_EXT}"):
        try:
            text = md.read_text(encoding="utf-8")
        except Exception:
            continue
        for t in parse_tags_from_text(text):
            counter[t] += 1
            files_for_tag[t].append(str(md))

    items = [(tag, cnt) for tag, cnt in counter.items() if cnt >= min_count]
    items.sort(key=lambda x: (-x[1], x[0]))
    if top > 0:
        items = items[:top]

    if json_out:
        print(json.dumps({tag: cnt for tag, cnt in items}, indent=2, sort_keys=True))
        return

    if not items:
        print("<no tags found>")
        return

    max_tag = max(len(r[0]) for r in items) if items else 0
    print(f"{'count':>5}  {'tag'.ljust(max_tag)}")
    print(f"{'-' * 5}  {'-' * max_tag}")
    for tag, cnt in items:
        print(f"{cnt:5d}  {tag.ljust(max_tag)}")

    if show_files:
        print("\nExample files per tag:")
        for tag, cnt in items:
            print(f"\n{tag} ({cnt})")
            for f in files_for_tag[tag][:5]:
                print(f"  - {f}")


def tagup_in_text(text: str, aliases: dict, removals: list) -> str:
    # Logic for tag replacement in frontmatter
    # This is a bit complex in manage.py, simplified here for modularity
    # Standard approach is to parse, modify, then dump.
    # But current manage.py seems to do it with regex to preserve comments/formatting.
    def replace_tag(match):
        tags_str = match.group(1)
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        new_tags = []
        for t in tags:
            clean_t = _strip_quotes(t).lower()
            if clean_t in removals:
                continue
            new_t = aliases.get(clean_t, clean_t)
            new_tags.append(new_t)
        # Unique and sorted
        final_tags = sorted(list(set(new_tags)))
        return f"tags: [{', '.join(final_tags)}]"

    return re.sub(r"tags\s*:\s*\[([^\]]*)\]", replace_tag, text)


def run_tagup(content_dir: Path) -> None:
    print("Running tagup...")
    count = 0
    for root, _, files in os.walk(content_dir):
        for file in files:
            if file.endswith(MD_EXT):
                path = Path(root) / file
                content = path.read_text(encoding="utf-8")
                new_content = tagup_in_text(content, TAG_ALIASES, TAG_REMOVALS)
                if new_content != content:
                    path.write_text(new_content, encoding="utf-8")
                    count += 1
    print(f"  Applied tags update in {count} files")
