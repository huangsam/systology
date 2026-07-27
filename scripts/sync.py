"""
Logic for checking if deep-dive documentation is in sync with its referenced repositories.
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path


def run_cmd(args: list[str], cwd: Path | None = None) -> str | None:
    """Helper to run shell commands and return stdout, returning None on failure."""
    try:
        res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def get_git_timestamp(file_path: Path, repo_root: Path) -> str | None:
    """Get the last git commit ISO 8601 timestamp for a file, falling back to mtime."""
    rel_path = file_path.relative_to(repo_root)
    ts = run_cmd(["git", "log", "-1", "--format=%cI", "--", str(rel_path)], cwd=repo_root)
    if ts:
        return ts
    # Fallback to file mtime if file is untracked or git command failed
    try:
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).astimezone().isoformat()
    except OSError:
        return None


def find_local_repos(search_paths: list[Path]) -> dict[str, Path]:
    """Scan search paths for directories containing a .git folder."""
    local_repos = {}
    for search_path in search_paths:
        expanded = search_path.expanduser().resolve()
        if not expanded.is_dir():
            continue
        # Scan immediate subdirectories first
        try:
            for item in expanded.iterdir():
                if item.is_dir() and (item / ".git").is_dir():
                    local_repos[item.name.lower()] = item
                # Also support one layer deeper (e.g. ~/Playground/projects/repo)
                elif item.is_dir():
                    try:
                        for subitem in item.iterdir():
                            if subitem.is_dir() and (subitem / ".git").is_dir():
                                local_repos[subitem.name.lower()] = subitem
                    except PermissionError:
                        continue
        except PermissionError:
            continue
    return local_repos


def get_repo_last_commit(repo_name: str, local_path: Path | None) -> str | None:
    """Get the last commit timestamp for a repository (local git or remote gh),
    filtering out bot updates, dependency bumps, and lockfile-only churn.
    """
    if local_path:
        # First attempt: filtered commit search ignoring bot/dependency commits and lockfile churn
        ts = run_cmd(
            [
                "git",
                "log",
                "-1",
                "--no-merges",
                "-i",
                "--invert-grep",
                "--grep=dependabot",
                "--grep=bump",
                "--grep=dependency",
                "--grep=dependencies",
                "--format=%cI",
                "--",
                ".",
                ":(exclude)*.lock",
                ":(exclude)*lock.json",
                ":(exclude)go.mod",
                ":(exclude)go.sum",
                ":(exclude)Pipfile.lock",
                ":(exclude)poetry.lock",
                ":(exclude).github",
                ":(exclude)gradle/wrapper",
            ],
            cwd=local_path,
        )
        if ts:
            return ts
        # Fallback to standard git log if filtered search yields no commits
        ts_fallback = run_cmd(["git", "log", "-1", "--format=%cI"], cwd=local_path)
        if ts_fallback:
            return ts_fallback

    # Fallback to GitHub CLI if available and repo name is full (owner/repo)
    if "/" in repo_name:
        gh_data = run_cmd(["gh", "repo", "view", repo_name, "--json", "pushedAt"])
        if gh_data:
            try:
                # gh returns JSON like {"pushedAt": "2026-05-20T14:35:43Z"}
                parsed = json.loads(gh_data)
                return parsed.get("pushedAt")
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    return None


def compare_timestamps(ts1: str, ts2: str) -> int:
    """Compare two ISO 8601 timestamps. Returns:
    -1 if ts1 < ts2 (ts1 is older)
     0 if ts1 == ts2
     1 if ts1 > ts2 (ts1 is newer)
    """
    # Simple parse using datetime.fromisoformat, replacing 'Z' with UTC offset
    try:
        dt1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        if dt1 < dt2:
            return -1
        elif dt1 > dt2:
            return 1
        return 0
    except (ValueError, TypeError):
        # Fallback to string comparison if datetime parsing fails
        if ts1 < ts2:
            return -1
        elif ts1 > ts2:
            return 1
        return 0


def run_check_sync(content_dir: Path, search_paths: list[Path], print_json: bool = False) -> None:
    """Validate that deep-dive docs are in sync with referenced repositories."""
    repo_root = content_dir.parent.parent
    deep_dives_dir = content_dir / "deep-dives"

    # 1. Scan local directories for git clones
    local_repos = find_local_repos(search_paths)

    results = []

    # 2. Iterate through all deep-dive markdown files
    if deep_dives_dir.is_dir():
        for p in sorted(deep_dives_dir.glob("*.md")):
            if p.name.startswith("."):
                continue

            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue

            # Find all references to huangsam repositories
            # e.g., https://github.com/huangsam/mailprune
            referenced_repos = re.findall(r"https://github.com/(huangsam/[\w\-]+)", text)
            if not referenced_repos:
                continue

            doc_ts = get_git_timestamp(p, repo_root)
            if not doc_ts:
                continue

            # Keep unique repos
            unique_repos = sorted(set(referenced_repos))

            for repo in unique_repos:
                repo_basename = repo.split("/")[-1].lower()
                local_path = local_repos.get(repo_basename)

                repo_ts = get_repo_last_commit(repo, local_path)

                status = "unknown"
                if repo_ts:
                    # Compare doc timestamp vs repo timestamp
                    comp = compare_timestamps(doc_ts, repo_ts)
                    if comp < 0:
                        status = "out-of-date"
                    else:
                        status = "up-to-date"

                results.append(
                    {
                        "document": str(p.relative_to(repo_root)),
                        "repository": repo,
                        "doc_last_commit": doc_ts,
                        "repo_last_commit": repo_ts,
                        "status": status,
                        "cloned_locally": local_path is not None,
                        "local_path": str(local_path) if local_path else None,
                    }
                )

    # 3. Output results
    if print_json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("No referenced repositories found in deep-dives.")
        return

    # Sort results deterministically by document name then repository
    results.sort(key=lambda x: (x["document"].split("/")[-1], x["repository"]))

    # Prepare table headers and raw cell data
    headers = ["Document", "Repository", "Doc Commit", "Repo Commit", "Status"]
    table_rows = []
    for r in results:
        doc_display = r["document"].split("/")[-1]
        repo_display = r["repository"]
        doc_commit = r["doc_last_commit"][:19].replace("T", " ") if r["doc_last_commit"] else "None"
        repo_commit = r["repo_last_commit"][:19].replace("T", " ") if r["repo_last_commit"] else "Unknown"
        status = r["status"].upper()
        table_rows.append((doc_display, repo_display, doc_commit, repo_commit, status))

    # Calculate dynamic column widths (max content length)
    col_widths = []
    for i, h in enumerate(headers):
        max_len = max(len(h), max((len(row[i]) for row in table_rows), default=0))
        col_widths.append(max_len)

    # Construct exact separator line matching total table width
    total_table_width = sum(col_widths) + 3 * (len(headers) - 1)
    sep_line = "-" * total_table_width

    # Print human-readable table
    print("\nDeep-Dive Repository Sync Status:")
    print(sep_line)
    header_str = " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    print(header_str)
    print(sep_line)

    for row in table_rows:
        status = row[4]
        if status == "OUT-OF-DATE":
            color = "\033[91m"  # Red
        elif status == "UP-TO-DATE":
            color = "\033[92m"  # Green
        else:
            color = "\033[93m"  # Yellow

        cells = [
            f"{row[0]:<{col_widths[0]}}",
            f"{row[1]:<{col_widths[1]}}",
            f"{row[2]:<{col_widths[2]}}",
            f"{row[3]:<{col_widths[3]}}",
            f"{color}{status:<{col_widths[4]}}\033[0m",
        ]
        print(" | ".join(cells))

    print(sep_line)
    print(f"Total checked: {len(results)} references.")
