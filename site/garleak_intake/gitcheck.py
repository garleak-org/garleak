# SPDX-License-Identifier: AGPL-3.0-or-later
"""The check made at pull request time, just before a merge: does this branch still add
records that the base branch does not already have, and does it still merge cleanly?

Two intake runs can pick the same number if they run at the same moment, and two novelty
checks can edit the same scratch file. Both show up here, and the sync workflow then
processes the later issue again against the current main."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

BRANCH_RE = re.compile(r"^intake/issue-([0-9]+)(?:-[a-z]+)?$")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def repo_root(path: Path) -> Path:
    r = _git(Path(path), "rev-parse", "--show-toplevel")
    if r.returncode:
        raise RuntimeError(f"{path} is not inside a git repository")
    return Path(r.stdout.strip())


def collisions(repo: Path, base: str, head: str = "HEAD", paths: tuple[str, ...] = ("archive",)) -> list[str]:
    mb = _git(repo, "merge-base", base, head)
    if mb.returncode:
        return [f"{head} and {base} share no history"]
    merge_base = mb.stdout.strip()
    added = _git(repo, "diff", "--name-only", "--diff-filter=A", merge_base, head, "--", *paths)
    problems = []
    for f in added.stdout.splitlines():
        if f and _git(repo, "cat-file", "-e", f"{base}:{f}").returncode == 0:
            problems.append(f"{f} already exists on {base}, so its number or id was taken in the meantime")
    tree = _git(repo, "merge-tree", "--write-tree", "--no-messages", base, head)
    if tree.returncode == 1:
        problems.append(f"the branch no longer merges cleanly into {base}")
    return problems


def stale_issues(repo: Path, branches: list[str], base: str = "HEAD", remote: str = "origin") -> list[int]:
    """Issue numbers whose open intake branch collides with the base."""
    out = set()
    for b in branches:
        m = BRANCH_RE.match(b or "")
        if not m:
            continue
        head = f"{remote}/{b}"
        if _git(repo, "rev-parse", "--verify", "--quiet", head).returncode:
            continue
        if collisions(repo, base, head):
            out.add(int(m[1]))
    return sorted(out)
