#!/usr/bin/env python3
"""
Project Formatting Script

1. Beautifies specific CSS files using `prettier` if available.
2. Formats all Markdown content (`site/content`, `site/archetypes`) to:
   - Remove trailing whitespace per line.
   - Ensure exactly one final newline at the end of file.

Usage:
    python3 scripts/format_project.py
"""

import subprocess
import argparse
from pathlib import Path

# CSS files to target
CSS_FILES = ["site/static/css/styles.css", "site/static/css/search.css"]


# Formatting function
def format_css_file(file_path: str) -> None:
    """
    Attempts to run `prettier --write` on the given CSS file.
    """
    path = Path(file_path)
    if not path.exists():
        print(f"Skipping CSS (not found): {file_path}")
        return

    print(f"Formatting CSS: {file_path}")
    try:
        # Check if prettier is installed
        result = subprocess.run(
            ["prettier", "--version"], capture_output=True, text=True
        )
        if result.returncode != 0:
            print(
                "Warning: `prettier` command not found or failed. Skipping CSS beautification."
            )
            return

        # Run prettier
        subprocess.run(["prettier", "--write", str(path)], check=True)
    except FileNotFoundError:
        print("Error: `prettier` executable not found in PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error formatting {file_path}: {e}")


def format_markdown_files(start_dir: str) -> None:
    """
    Recursively scans directory for .md files.
    Trims trailing whitespace from lines and ensures EOF newline.
    """
    root_path = Path(start_dir)
    if not root_path.exists():
        print(f"Skipping directory (not found): {start_dir}")
        return

    print(f"Scanning Markdown in: {start_dir}")
    count = 0
    for file_path in root_path.rglob("*.md"):
        processed = process_markdown_file(file_path)
        if processed:
            count += 1

    if count > 0:
        print(f"Updated {count} files in {start_dir}")
    else:
        print(f"No changes needed in {start_dir}")


def process_markdown_file(file_path: str) -> bool:
    """
    Reads file, cleans whitespace, writes back if changed.
    Returns True if file changed, False otherwise.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()
        # Trim trailing logic
        # 1. Rstrip each line.
        cleaned_lines = [line.rstrip() for line in lines]

        # Reconstruct content
        # Ensure single final newline
        new_content = "\n".join(cleaned_lines) + "\n"

        # If original content already ends with newline(s), splitlines() logic might
        # alter it. Let's compare strictly.
        # Actually, splitlines() eats the trailing newline of the last line if present.
        # So "\n".join(...) puts them back between lines. + "\n" adds one at end.
        # This standardizes to exactly one trailing newline.

        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  Fixed: {file_path}")
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Format project styles and content.")
    parser.parse_args()

    # 1. CSS
    for css in CSS_FILES:
        format_css_file(css)

    # 2. Markdown Content
    format_markdown_files("site/content")
    format_markdown_files("site/archetypes")


if __name__ == "__main__":
    main()
