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

    # Insights
    subparsers.add_parser(
        "insights", help="Analyze tag distribution, co-occurrence, and TF-IDF"
    )

    # Check
    subparsers.add_parser("check", help="Validate content")

    args = parser.parse_args()

    # Path configuration
    base_dir = Path(__file__).resolve().parent
    site_dir = base_dir / SITE_DIR
    content_dir = site_dir / CONTENT_DIR
    archetypes_dir = site_dir / ARCHETYPES_DIR

    if args.command == "tidy":
        run_normalize(content_dir)
        run_add_summary_desc(content_dir)
        run_sort_tags(content_dir)
        run_format_project(site_dir, content_dir, archetypes_dir)
    elif args.command == "stats":
        run_tag_stats(content_dir, args.min_count, args.top, args.json, args.show_files)
    elif args.command == "tagup":
        run_tagup(content_dir)
    elif args.command == "insights":
        from scripts.insights import generate_insights

        generate_insights(content_dir)
    elif args.command == "check":
        run_check(content_dir)


if __name__ == "__main__":
    main()
