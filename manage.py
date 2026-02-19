#!/usr/bin/env python3
"""
(Note: This script consolidates functionality from multiple previous scripts.)
Project Management Script

Unified tool for managing systology content and build processes.
Replaces individual scripts in scripts/.

Usage:
    python3 scripts/manage.py <command> [options]

Commands:
    tidy      Run full tidy pipeline.
    index     Generate the Lunr.js search index.
    stats     Show tag frequency statistics.
    check     Validate content across site.
"""

import argparse
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

# --- Globals ---
MAX_DESC_LEN = 160
CSS_FILES = ["site/static/css/styles.css", "site/static/css/search.css"]


# --- Utilities ---


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1].strip()
    return s


# --- Logic: normalize_content ---


def has_frontmatter(lines: list[str]) -> bool:
    if not lines:
        return False
    first = lines[0].strip()
    return first in ("---", "+++", "{")


def extract_first_h1(lines: list[str]) -> str | None:
    for ln in lines:
        m = re.match(r"^#\s+(.*)", ln)
        if m:
            return m.group(1).strip()
    return None


def normalize_file(path: Path) -> bool:
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
        fm = ["---", f'title: "{title.replace('"', "''")}"', "---", ""]
        new = fm + lines
        path.write_text("\n".join(new) + "\n", encoding="utf-8")
        return True

    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    return False


def run_normalize(content_dir: Path) -> None:
    print("Running normalize_content...")
    count = 0
    for p in content_dir.rglob("*.md"):
        if p.is_file():
            if normalize_file(p):
                count += 1
    print(f"  Normalized {count} files")


# --- Logic: add_summary_description ---


def extract_fm_body(text: str) -> tuple[list[str] | None, list[str]]:
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        j = i + 1
        while j < len(lines) and lines[j].strip() != "---":
            j += 1
        if j >= len(lines):
            return None, lines[i:]
        return lines[i + 1 : j], lines[j + 1 :]
    return None, lines[i:]


def parse_fm(fm_lines: list[str]) -> dict[str, str]:
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


def first_paragraph(body_lines: list[str]) -> str:
    para = []
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


def make_description(text: str, max_len: int = MAX_DESC_LEN) -> str:
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


def insert_fm(fm_lines: list[str], key: str, value: str) -> list[str]:
    out = []
    inserted = False
    for ln in fm_lines:
        out.append(ln)
        if not inserted and re.match(r"^\s*title\s*:\s*", ln):
            out.append(f'{key}: "{value.replace('"', '\\"')}"')
            inserted = True
    if not inserted:
        out.append(f'{key}: "{value.replace('"', '\\"')}"')
    return out


def add_summary_desc_file(p: Path) -> bool:
    text = p.read_text(encoding="utf-8")
    fm_lines, body_lines = extract_fm_body(text)
    if fm_lines is None:
        return False
    fm = parse_fm(fm_lines)

    has_summary = "summary" in fm and fm["summary"].strip()
    has_desc = "description" in fm and fm["description"].strip()

    if has_summary and has_desc:
        return False

    candidate = None
    if has_summary:
        candidate = fm["summary"].strip()
    else:
        cand = first_paragraph(body_lines)
        if cand:
            candidate = cand

    if not candidate:
        return False

    new_fm = fm_lines.copy()
    if not has_summary:
        new_fm = insert_fm(new_fm, "summary", candidate)
    if not has_desc:
        desc = make_description(candidate)
        new_fm = insert_fm(new_fm, "description", desc)

    parsed_fm_content = "\n".join(new_fm)

    # Rebuild file
    new_text = (
        "---\n"
        + parsed_fm_content
        + "\n---\n\n"
        + "\n".join(body_lines).lstrip()
        + "\n"
    )
    p.write_text(new_text, encoding="utf-8")
    return True


def run_add_summary_desc(content_dir: Path) -> None:
    print("Running add_summary_description...")
    updated = 0
    for p in sorted(content_dir.rglob("*.md")):
        try:
            if add_summary_desc_file(p):
                updated += 1
        except Exception as e:
            print(f"Error processing {p}: {e}")
    print(f"  Updated {updated} files")


# --- Logic: update_internal_links ---


def update_links_file(p: Path, content_root: Path) -> bool:
    text = p.read_text(encoding="utf-8")
    original = text
    try:
        rel_path = p.relative_to(content_root)
    except ValueError:
        # File not under content_root
        return False
    parts = rel_path.parts

    def replace_link(match: re.Match) -> str:
        full = match.group(0)
        link = match.group(2)
        if link.endswith(".md"):
            link = link[:-3]
            if link.startswith("../"):
                up_count = link.count("../")
                new_link = "/" + link[3 * up_count :]
            elif link.startswith("./"):
                new_link = "/" + "/".join(parts[:-1]) + "/" + link[2:]
            elif "/" not in link:
                new_link = "/" + "/".join(parts[:-1]) + "/" + link
            else:
                new_link = "/" + link
            return f"[{match.group(1)}]({new_link})"
        return full

    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    new_text = re.sub(pattern, replace_link, text)

    if new_text != original:
        p.write_text(new_text, encoding="utf-8")
        return True
    return False


def run_update_links(content_dir: Path) -> None:
    print("Running update_internal_links...")
    count = 0
    for md in content_dir.rglob("*.md"):
        if update_links_file(md, content_dir):
            count += 1
    print(f"  Updated {count} files")


# --- Logic: sort_tags ---


def sort_tags_in_text(content: str) -> str:
    match = re.search(r"^tags:\s*\[(.*?)\]", content, re.MULTILINE)
    if not match:
        return content
    tags_str = match.group(1)
    tags = [t.strip().strip('"').strip("'") for t in tags_str.split(",") if t.strip()]
    tags.sort()
    new_tags_str = "tags: [" + ", ".join(f'"{t}"' for t in tags) + "]"
    return content.replace(match.group(0), new_tags_str)


def run_sort_tags(content_dir: Path) -> None:
    print("Running sort_tags...")
    count = 0
    for root, _, files in os.walk(content_dir):
        for file in files:
            if file.endswith(".md"):
                path = Path(root) / file
                content = path.read_text(encoding="utf-8")
                new_content = sort_tags_in_text(content)
                if new_content != content:
                    path.write_text(new_content, encoding="utf-8")
                    count += 1
    print(f"  Sorted tags in {count} files")


# --- Logic: format_project ---


def format_css(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        return
    try:
        subprocess.run(
            ["prettier", "--write", str(path)], check=True, capture_output=True
        )
        print(f"  Formatted {file_path}")
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass


def process_md_format(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        cleaned_lines = [line.rstrip() for line in lines]
        new_content = "\n".join(cleaned_lines) + "\n"
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            return True
    except Exception:
        pass
    return False


def run_format_project(content_dir: Path, archetypes_dir: Path) -> None:
    print("Running format_project...")
    # CSS
    for css in CSS_FILES:
        try:
            # handle relative paths from CWD if needed, but here we assume running from root
            if os.path.exists(css):
                format_css(css)
        except Exception:
            pass

    # Markdown
    for d in [content_dir, archetypes_dir]:
        if not d.exists():
            continue
        count = 0
        for p in d.rglob("*.md"):
            if process_md_format(p):
                count += 1
        if count > 0:
            print(f"  Formatted {count} files in {d}")


# --- Logic: generate_search_index ---


def extract_fm_search(content: str) -> tuple[dict, str]:
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return {}, content
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key == "tags":
                value = re.findall(r'"([^"]+)"', value)
            fm[key] = value
    body = content[match.end() :]
    return fm, body


def extract_preview(body: str, max_length: int = 150) -> str:
    body = re.sub(r"^#+\s+", "", body, flags=re.MULTILINE)
    body = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", body)
    body = re.sub(r"[*_`]", "", body)
    parts = body.split("\n\n")
    if not parts:
        return ""
    para = parts[0].strip()
    if len(para) > max_length:
        para = para[:max_length].rsplit(" ", 1)[0] + "..."
    return para


def run_generate_index(content_dir: Path) -> None:
    print("Generating search index...")
    documents = []
    doc_id = 0
    for md_file in sorted(content_dir.rglob("*.md")):
        if "_index.md" in md_file.name or md_file.name.startswith("."):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        fm, body = extract_fm_search(content)
        if "title" not in fm:
            continue

        try:
            category = md_file.relative_to(content_dir).parts[0]
        except IndexError:
            category = "unknown"

        title = fm.get("title", "")
        desc = fm.get("description", "")
        summary = fm.get("summary", "")
        tags = fm.get("tags", [])

        preview = desc if desc else extract_preview(body)
        searchable = f"{title} {desc} {summary} {' '.join(tags) if isinstance(tags, list) else tags}".lower()
        slug = md_file.stem
        url = f"/{category}/{slug}/"

        doc = {
            "id": str(doc_id),
            "title": title,
            "description": desc,
            "preview": preview,
            "tags": tags if isinstance(tags, list) else [tags],
            "category": category,
            "url": url,
            "content": searchable,
        }
        documents.append(doc)
        doc_id += 1

    index_data = {"documents": documents, "documentCount": len(documents)}
    # Assuming CWD is project root
    output_path = Path("site/static/search-index.json")
    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f)
    print(f"  Generated search index with {len(documents)} documents at {output_path}")


# --- Logic: tag_frequency ---


def parse_tags_from_text(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return []

    fm_text = "\n".join(lines[1:end_idx])

    # Inline list
    m = re.search(r"^\s*tags\s*:\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
    if m:
        return [_strip_quotes(p) for p in m.group(1).split(",") if p.strip()]

    # Single scalar
    m = re.search(
        r"^\s*tags\s*:\s*([\'\"]?[^\n\'\"]+[\'\"]?)\s*$", fm_text, re.MULTILINE
    )
    if m:
        return [_strip_quotes(m.group(1))]

    # Block list
    block_start = None
    lines_fm = fm_text.splitlines()
    for idx, line in enumerate(lines_fm):
        if re.match(r"^\s*tags\s*:\s*$", line):
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

    for md in content_dir.rglob("*.md"):
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


# --- Logic: check_content ---


def check_file(p: Path, content_root: Path) -> list[str]:
    errors = []
    text = p.read_text(encoding="utf-8")
    fm_lines, body_lines = extract_fm_body(text)

    # 1. Frontmatter Validation
    if fm_lines is None:
        errors.append("Missing frontmatter")
    else:
        fm = parse_fm(fm_lines)
        if "title" not in fm or not fm["title"].strip():
            errors.append("Missing 'title' in frontmatter")
        if "date" not in fm and "lastmod" not in fm:
            # Optional warning, but good to have
            pass

    # 2. Internal Link Validation
    # Matches [Label](link)
    # Ignore http/https/mailto
    base_dir = p.parent
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
    for _, link in links:
        link = link.strip()
        if link.startswith(("#", "http", "https", "mailto:", "tel:")):
            continue

        # Handle Hugo relref/ref (skip for now or implement logic)
        if "{{" in link or "}}" in link:
            continue

        # Resolve path
        # If absolute in Hugo (starts with /), it's relative to content/ or static/
        # Here we assume it's relative to content/ for MD files
        target = None
        if link.startswith("/"):
            # Check content first, then static check is harder without static_dir context here
            # We'll just check content for now
            target = content_root / link.lstrip("/")
            if not target.exists() and not target.with_suffix(".md").exists():
                 # Try static?
                 # simplistic check:
                 pass
        else:
            target = base_dir / link

        # If it's an MD link, maybe it dropped the extension?
        if target and not target.exists():
             if target.with_suffix(".md").exists():
                 target = target.with_suffix(".md")

        # If still not found
        if target and not target.exists():
            # Special case: anchors
            if "#" in link:
                # TODO: Check file existence ignoring anchor
                pass
            else:
                 errors.append(f"Broken link: {link}")

    # 3. Image Validation
    # Matches ![Alt](src)
    images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text)
    for _, src in images:
        src = src.strip()
        if src.startswith(("http", "https", "data:")):
            continue

        target = None
        if src.startswith("/"):
             # Absolute path in Hugo usually maps to static/
             # We need to find static dir relative to content_root
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
    for p in sorted(content_dir.rglob("*.md")):
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
        # exit(1) # Optional: fail build if issues found


# --- Main Entry Point ---


def main():
    parser = argparse.ArgumentParser(description="Systology Management Script")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Tidy
    subparsers.add_parser("tidy", help="Run full cleanup pipeline")

    # Index
    subparsers.add_parser("index", help="Generate search index")

    # Stats
    stats_parser = subparsers.add_parser("stats", help="Tag statistics")
    stats_parser.add_argument("--min-count", type=int, default=1, help="Min count")
    stats_parser.add_argument("--top", type=int, default=0, help="Top N tags")
    stats_parser.add_argument("--json", action="store_true", help="JSON output")
    stats_parser.add_argument("--show-files", action="store_true", help="Show files")

    # Check
    subparsers.add_parser("check", help="Validate content")

    args = parser.parse_args()

    # Path configuration - assuming we run from project root or scripts/
    # We want to find 'site' relative to where this script is, or CWD?
    # Original scripts used __file__ relative paths or CWD.
    # Let's use __file__ to locate site/ relative to scripts/

    script_path = Path(__file__).resolve()
    if script_path.parent.name == "scripts":
        base_dir = script_path.parents[1]
    else:
        base_dir = script_path.parent

    site_dir = base_dir / "site"
    content_dir = site_dir / "content"
    archetypes_dir = site_dir / "archetypes"

    if args.command == "tidy":
        run_normalize(content_dir)
        run_add_summary_desc(content_dir)
        run_update_links(content_dir)
        run_sort_tags(content_dir)
        run_format_project(content_dir, archetypes_dir)
    elif args.command == "index":
        run_generate_index(content_dir)
    elif args.command == "stats":
        run_tag_stats(content_dir, args.min_count, args.top, args.json, args.show_files)
    elif args.command == "check":
        run_check(content_dir)


if __name__ == "__main__":
    main()
