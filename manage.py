#!/usr/bin/env python3
"""
Systology Management Script - Unifying modular components.
"""

import argparse
from pathlib import Path

from scripts.constants import SITE_DIR, CONTENT_DIR, ARCHETYPES_DIR
from scripts.validator import run_check
from scripts.formatter import run_format_project
from scripts.metadata import run_sort_tags, run_tag_stats, run_tagup
from scripts.content import run_normalize, run_add_summary_desc
from scripts.sync import run_check_sync


def main():
    parser = argparse.ArgumentParser(description="Systology Management Script")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Tidy
    subparsers.add_parser("tidy", help="Run full cleanup pipeline")

    # Stats
    stats_parser = subparsers.add_parser("stats", help="Tag statistics")
    stats_parser.add_argument("--min-count", type=int, default=1, help="Min count")
    stats_parser.add_argument("--top", type=int, default=0, help="Top N tags")
    stats_parser.add_argument("--json", action="store_true", help="JSON output")
    stats_parser.add_argument("--show-files", action="store_true", help="Show files")

    # Tagup
    subparsers.add_parser("tagup", help="Standardize tags")

    insights_parser = subparsers.add_parser("insights", help="Analyze tag distribution, co-occurrence, and TF-IDF")
    insights_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON manifest instead of human-readable output",
    )
    insights_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full cross-reference list in human-readable output",
    )

    # Check
    subparsers.add_parser("check", help="Validate content")

    # Check Sync
    check_sync_parser = subparsers.add_parser("check-sync", help="Validate that deep-dive docs are in sync with repos")
    check_sync_parser.add_argument(
        "--search-path",
        "-p",
        action="append",
        help="Paths to search for local repository clones (repeatable). Defaults to ~/Playground and ~/JetBrains.",
    )
    check_sync_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of a formatted table",
    )

    args = parser.parse_args()

    # Path configuration
    base_dir = Path(__file__).resolve().parent
    site_dir = base_dir / SITE_DIR
    content_dir = site_dir / CONTENT_DIR
    archetypes_dir = site_dir / ARCHETYPES_DIR

    if args.command == "tidy":
        run_normalize(content_dir)
        run_add_summary_desc(content_dir)
        run_tagup(content_dir)
        run_sort_tags(content_dir)
        run_format_project(site_dir, content_dir, archetypes_dir)
    elif args.command == "stats":
        run_tag_stats(content_dir, args.min_count, args.top, args.json, args.show_files)
    elif args.command == "tagup":
        run_tagup(content_dir)
    elif args.command == "insights":
        from scripts.insights import generate_insights

        generate_insights(content_dir, json_out=args.json, verbose=args.verbose)
    elif args.command == "check":
        run_check(content_dir)
    elif args.command == "check-sync":
        import sys

        search_paths = []

        if args.search_path:
            search_paths = [Path(p) for p in args.search_path]
        else:
            config_file = base_dir / ".sync_paths.json"
            if config_file.is_file():
                try:
                    import json

                    with open(config_file, "r") as f:
                        config = json.load(f)
                    if isinstance(config, dict) and "search_paths" in config:
                        search_paths = [Path(p) for p in config["search_paths"]]
                    elif isinstance(config, list):
                        search_paths = [Path(p) for p in config]
                except Exception as e:
                    print(f"Error: Failed to parse {config_file.name}: {e}")
                    sys.exit(1)

        if not search_paths:
            print("Error: No search paths resolved.")
            print("Please either pass --search-path/-p via the CLI, or create .sync_paths.json in the project root:")
            print('{\n  "search_paths": [\n    "~/Playground",\n    "~/JetBrains"\n  ]\n}')
            sys.exit(1)

        run_check_sync(content_dir, search_paths, args.json)


if __name__ == "__main__":
    main()
