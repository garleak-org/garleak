# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifier assignment, reservations held by open pull requests, and the collision
check made before a merge."""

import os
import shutil
import subprocess

import pytest

from garleak_intake.assign import next_number, next_seq
from garleak_intake.cli import main as cli_main
from garleak_intake.gitcheck import collisions, stale_issues

from .intake_support import Arch, answers, ctx, make_issue, open_pr, run


def test_next_number():
    assert next_number([], set(), 1) == 1
    assert next_number([1, 2], {"3"}, 1) == 4
    assert next_number([1], {"3"}, 1, prefer=["2"]) == 2      # an edit keeps its number
    assert next_number([1], {"2"}, 1, prefer=["2"]) == 3      # unless it was taken meanwhile
    assert next_number([], set(), 100) == 100


def test_next_seq():
    assert next_seq("12-", ["12-01", "12-02"], {"12-03"}, 2) == "12-04"
    assert next_seq("8-n", [], set(), 1) == "8-n1"
    assert next_seq("12-", ["12-01"], set(), 2, prefer=["12-05"]) == "12-05"


@pytest.fixture
def arch(tmp_path):
    a = Arch(tmp_path)
    for h in ("alice", "bob"):
        a.account(h)
    return a


def test_open_pull_requests_reserve_numbers(arch):
    other = open_pr(50, 7, {"kind": "scratch", "ids": ["scratch:1"], "account": "bob", "field": "phys",
                            "spend": "1.5", "date": "2026-09-13"})
    res = run(arch, make_issue("scratch", number=8), ctx(open_prs=[other]))
    assert res.ids == ["scratch:2"]


def test_an_edited_issue_keeps_its_number(arch):
    mine = open_pr(51, 8, {"kind": "scratch", "ids": ["scratch:5"], "account": "alice", "field": "phys",
                           "spend": "1.5", "date": "2026-09-14"})
    res = run(arch, make_issue("scratch", number=8), ctx(open_prs=[mine]))
    assert res.ids == ["scratch:5"]
    assert res.balance["before"] == "0.0"  # its own pending spend is not counted twice


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    root = tmp_path / "repo"
    root.mkdir()
    a = Arch(root)
    a.account("alice")
    a.account("bob")

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True)

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    return root, a, git


def test_check_pr_catches_a_number_taken_meanwhile(repo):
    root, a, git = repo
    git("switch", "-q", "-c", "intake/issue-8")
    run(a, make_issue("scratch", number=8))
    git("add", "-A")
    git("commit", "-q", "-m", "scratch 1 from issue 8")
    assert collisions(root, "main") == []
    git("switch", "-q", "main")
    run(a, make_issue("scratch", answers("scratch", statement="Another idea entirely, about comets and dust."),
                      number=9, author="bob"))
    git("add", "-A")
    git("commit", "-q", "-m", "scratch 1 from issue 9")
    git("switch", "-q", "intake/issue-8")
    problems = collisions(root, "main")
    assert any("scratches/1.yaml already exists on main" in p for p in problems)
    assert cli_main(["check-pr", "--archive", str(a.root), "--base", "main"]) == 1
    git("switch", "-q", "main")
    git("update-ref", "refs/remotes/origin/intake/issue-8", "intake/issue-8")
    assert stale_issues(root, ["intake/issue-8", "feature/x"], "HEAD") == [8]
