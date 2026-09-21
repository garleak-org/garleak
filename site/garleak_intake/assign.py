# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifier assignment.

Paper and sketch numbers are separate sequences of positive integers, never reused
(SPEC §2.3.1). A number proposed in an open pull request is reserved, so two open requests
never propose the same number. If one still collides at merge time (two runs at once), the
collision check in `gitcheck` stops the merge and the sync workflow reprocesses the later
issue with a fresh number. In Phase 1 a number is issued when its pull request merges; a
number proposed in a closed pull request was never issued."""

from __future__ import annotations

import re
from typing import Iterable

from .context import OpenPR


def reserved(open_prs: list[OpenPR], exclude_issue: int | None) -> dict[str, set[str]]:
    """Identifiers proposed by other open intake pull requests, by kind."""
    out: dict[str, set[str]] = {}
    for pr in open_prs:
        if not pr.meta or pr.meta.get("issue") == exclude_issue:
            continue
        for ident in pr.meta.get("ids") or []:
            kind, _, value = str(ident).partition(":")
            out.setdefault(kind, set()).add(value)
    return out


def own(open_prs: list[OpenPR], issue: int) -> dict[str, set[str]]:
    """Identifiers this issue's own open pull request already proposes. They are reused
    when the issue is edited, so an edit does not move a submission to a new number."""
    out: dict[str, set[str]] = {}
    for pr in open_prs:
        if pr.meta and pr.meta.get("issue") == issue:
            for ident in pr.meta.get("ids") or []:
                kind, _, value = str(ident).partition(":")
                out.setdefault(kind, set()).add(value)
    return out


def next_number(existing: Iterable[int], taken: Iterable[str], first: int, prefer: Iterable[str] = ()) -> int:
    used = set(existing) | {int(x) for x in taken if str(x).isdigit()}
    for p in prefer:
        if str(p).isdigit() and int(p) not in used and int(p) >= first:
            return int(p)
    return max(used | {first - 1}) + 1


def next_seq(prefix: str, existing: Iterable[str], taken: Iterable[str], width: int = 1,
             prefer: Iterable[str] = ()) -> str:
    """The next id of the form <prefix><n>, for example 12-03 or 8-n2."""
    ex = set(existing) | set(taken)
    for p in prefer:
        if p.startswith(prefix) and p not in ex:
            return p
    rx = re.compile(re.escape(prefix) + r"(\d+)$")
    seqs = [int(m[1]) for s in ex if (m := rx.match(s))]
    return f"{prefix}{max(seqs, default=0) + 1:0{width}d}"
