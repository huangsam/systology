#!/usr/bin/env python3
"""
Count front-matter `tags` across markdown files under a content directory.

Usage:
    python3 scripts/tag_frequency.py -p site/content
    python3 scripts/tag_frequency.py -p site/content --min-count 2 --json
    python3/scripts/tag_frequency.py -p site/content --show-files
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1].strip()
    return s


def parse_tags_from_text(text: str) -> list[str]:
    """Extract `tags` from YAML front-matter in `text`.

    Returns a list of tag strings (maybe empty).
    """
    lines = text.splitlines()
    if not lines:
        return []
    # find YAML front-matter block
    if lines[0].strip() != "---":
        return []
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return []
    fm_lines = lines[1:end_idx]
    fm_text = "\n".join(fm_lines)

    # 1) inline list: tags: [a, b, 'c']
    m = re.search(r"^\s*tags\s*:\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
    if m:
        raw = m.group(1)
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return [_strip_quotes(p) for p in parts]

    # 2) single-line scalar: tags: "foo"
    m = re.search(
        r"^\s*tags\s*:\s*([\'\"]?[^\n\'\"]+[\'\"]?)\s*$", fm_text, re.MULTILINE
    )
    if m:
        val = _strip_quotes(m.group(1))
        return [val]

    # 3) block list:
    #    tags:
    #      - a
    #      - b
    block_start = None
    fm_lines_list = fm_text.splitlines()
    for idx, line in enumerate(fm_lines_list):
        if re.match(r"^\s*tags\s*:\s*$", line):
            block_start = idx
            break
    if block_start is not None:
        tags = []
        for line in fm_lines_list[block_start + 1 :]:
            if re.match(r"^\s*-\s+(.+)", line):
                v = re.sub(r"^\s*-\s+", "", line).strip()
                tags.append(_strip_quotes(v))
            else:
                # stop when indentation/list ends
                if line.strip() == "":
                    continue
                if not line.startswith(" ") and not line.startswith("\t"):
                    break
                # indented non-list line -> stop
                if line.lstrip().startswith(
                    ("#", "title:", "description:", "summary:")
                ):
                    break
        return tags

    return []


def find_markdown_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.md"):
        yield p


def count_tags(root: Path) -> tuple[Counter, defaultdict[str, list[str]]]:
    counter = Counter()
    files_for_tag: defaultdict[str, list[str]] = defaultdict(list)
    for md in find_markdown_files(root):
        try:
            text = md.read_text(encoding="utf8")
        except Exception:
            continue
        tags = parse_tags_from_text(text)
        for t in tags:
            counter[t] += 1
            files_for_tag[t].append(str(md))
    return counter, files_for_tag


def fmt_table(counter: Counter) -> str:
    rows = [(tag, count) for tag, count in counter.most_common()]
    if not rows:
        return "<no tags found>"
    max_tag = max(len(r[0]) for r in rows)
    lines = [f"{'count':>5}  {'tag'.ljust(max_tag)}", f"{'-' * 5}  {'-' * max_tag}"]
    for tag, cnt in rows:
        lines.append(f"{cnt:5d}  {tag.ljust(max_tag)}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Count front-matter tags in a Hugo content tree"
    )
    p.add_argument(
        "-p",
        "--path",
        default="site/content",
        help="content root (default: site/content)",
    )
    p.add_argument(
        "--min-count", type=int, default=1, help="only show tags with count >= N"
    )
    p.add_argument("--top", type=int, default=0, help="show only top N tags")
    p.add_argument("--json", action="store_true", help="output JSON (tag->count)")
    p.add_argument(
        "--show-files", action="store_true", help="also show example files per tag"
    )
    args = p.parse_args(argv)

    root = Path(args.path)
    if not root.exists():
        print(f"Path not found: {root}")
        return 2

    counter, files_for_tag = count_tags(root)

    # apply min-count filter
    items = [(tag, cnt) for tag, cnt in counter.items() if cnt >= args.min_count]
    items.sort(key=lambda x: (-x[1], x[0]))
    if args.top > 0:
        items = items[: args.top]

    if args.json:
        out = {tag: cnt for tag, cnt in items}
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0

    # print table
    c = Counter(dict(items))
    print(fmt_table(c))

    if args.show_files:
        print("\nExample files per tag:")
        for tag, cnt in items:
            files = files_for_tag.get(tag, [])
            sample = files[:5]
            print(f"\n{tag} ({cnt})")
            for f in sample:
                print(f"  - {f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
