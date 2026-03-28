"""
Logic for formatting Systology site assets and content.
"""

import subprocess
from pathlib import Path
from .constants import ASSETS_DIR, MD_EXT


def process_md_format(file_path: Path) -> bool:
    """Clean up trailing whitespace in a Markdown file."""
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


def format_prettier(file_path: str) -> None:
    """Run Prettier formatting on a given file or directory path."""
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


def run_format_project(site_dir: Path, content_dir: Path, archetypes_dir: Path) -> None:
    """Format project assets and Markdown content using Prettier, Ruff, and custom logic."""
    print("Running format_project...")
    # CSS & JS in assets (respects .prettierignore)
    assets_dir = site_dir / ASSETS_DIR
    if assets_dir.exists():
        format_prettier(str(assets_dir))

    # Markdown (Using custom process_md_format for lighter touch)
    for d in [content_dir, archetypes_dir]:
        if not d.exists():
            continue
        count = 0
        for p in d.rglob(f"*{MD_EXT}"):
            if process_md_format(p):
                count += 1
        if count > 0:
            print(f"  Formatted {count} files in {d}")

    # Python (maintenance scripts)
    try:
        subprocess.run(["ruff", "check", "--fix", "."], check=True, capture_output=True)
        subprocess.run(["ruff", "format", "."], check=True, capture_output=True)
        print("  Formatted Python scripts via Ruff")
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
