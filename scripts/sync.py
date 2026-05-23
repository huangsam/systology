"""
Logic for checking if deep-dive documentation is in sync with its referenced repositories.
"""

import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


def run_cmd(args: List[str], cwd: Optional[Path] = None) -> Optional[str]:
    """Helper to run shell commands and return stdout, returning None on failure."""
    try:
        res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return None


def get_git_timestamp(file_path: Path, repo_root: Path) -> Optional[str]:
    """Get the last git commit ISO 8601 timestamp for a file, falling back to mtime."""
    rel_path = file_path.relative_to(repo_root)
    ts = run_cmd(["git", "log", "-1", "--format=%cI", "--", str(rel_path)], cwd=repo_root)
    if ts:
        return ts
    # Fallback to file mtime if file is untracked or git command failed
    try:
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).astimezone().isoformat()
    except Exception:
        return None


def find_local_repos(search_paths: List[Path]) -> Dict[str, Path]:
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


def get_repo_last_commit(repo_name: str, local_path: Optional[Path]) -> Optional[str]:
    """Get the last commit timestamp for a repository (local git or remote gh)."""
    if local_path:
        ts = run_cmd(["git", "log", "-1", "--format=%cI"], cwd=local_path)
        if ts:
            return ts

    # Fallback to GitHub CLI if available and repo name is full (owner/repo)
    if "/" in repo_name:
        gh_data = run_cmd(["gh", "repo", "view", repo_name, "--json", "pushedAt"])
        if gh_data:
            try:
                # gh returns JSON like {"pushedAt": "2026-05-20T14:35:43Z"}
                parsed = json.loads(gh_data)
                return parsed.get("pushedAt")
            except Exception:
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
    except Exception:
        # Fallback to string comparison if datetime parsing fails
        if ts1 < ts2:
            return -1
        elif ts1 > ts2:
            return 1
        return 0


def run_check_sync(content_dir: Path, search_paths: List[Path], print_json: bool = False) -> None:
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
            except Exception:
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
            unique_repos = sorted(list(set(referenced_repos)))

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

    # Print human-readable table
    print("\nDeep-Dive Repository Sync Status:")
    print("-" * 110)
    print(f"{'Document':<35} | {'Repository':<25} | {'Doc Commit':<25} | {'Repo Commit':<25} | {'Status':<12}")
    print("-" * 110)
    for r in results:
        doc_display = r["document"].split("/")[-1]
        repo_display = r["repository"]
        doc_commit = r["doc_last_commit"][:19] if r["doc_last_commit"] else "None"
        repo_commit = r["repo_last_commit"][:19] if r["repo_last_commit"] else "Unknown"

        status = r["status"].upper()
        if status == "OUT-OF-DATE":
            status_str = f"\033[91m{status}\033[0m"  # Red
        elif status == "UP-TO-DATE":
            status_str = f"\033[92m{status}\033[0m"  # Green
        else:
            status_str = f"\033[93m{status}\033[0m"  # Yellow

        print(f"{doc_display:<35} | {repo_display:<25} | {doc_commit:<25} | {repo_commit:<25} | {status_str:<12}")
    print("-" * 110)
    print(f"Total checked: {len(results)} references.")
