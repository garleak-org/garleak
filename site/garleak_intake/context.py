# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the workflow gathers from GitHub before the intake runs, read from files.

The workflow writes these into one directory with the `gh` CLI (see intake.yml). The
intake step itself holds no token and makes no GitHub API call.

    comments.jsonl     every comment on the issue: {id, body, user, author_association, created_at}
    permissions.jsonl  repository permission of the author and of every commenter who wrote a
                       slash command: {login, permission}
    open-prs.json      open pull requests: [{number, headRefName, body}]
    votes.json         the author's earlier reader-vote issues: [{number, body, labels, createdAt}]
    orcid.json         the ORCID lookup made by `garleak-intake orcid-lookup`
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

META_RE = re.compile(r"<!--\s*garleak-intake\s+(\{.*?\})\s*-->", re.S)
BRANCH_RE = re.compile(r"^intake/issue-([0-9]+)$")
COMMAND_RE = re.compile(r"^/([a-z][a-z-]*)\b[ \t]*(.*)$")
COMMANDS = ("recheck", "approve-email", "confirm-operator", "conflict-check", "reject", "remove")
MODERATOR_ONLY = ("approve-email", "conflict-check", "reject", "remove")
BOT_MARKER = "<!-- garleak-intake -->"


def parse_ts(value) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


@dataclass
class Comment:
    id: int
    body: str
    user: str
    created_at: dt.datetime
    author_association: str = ""
    user_type: str = "User"

    @classmethod
    def from_dict(cls, d: dict) -> Comment:
        user = d.get("user")
        login = user.get("login") if isinstance(user, dict) else user
        utype = (user.get("type") if isinstance(user, dict) else None) or d.get("user_type") or "User"
        return cls(int(d.get("id") or 0), d.get("body") or "", login or "", parse_ts(d["created_at"]),
                   d.get("author_association") or "", utype)


@dataclass
class OpenPR:
    number: int
    branch: str
    issue: int | None
    meta: dict | None


@dataclass
class Command:
    name: str
    args: list[str]
    user: str
    at: dt.datetime
    moderator: bool
    author: bool
    comment_id: int = 0


@dataclass
class Context:
    comments: list[Comment] = field(default_factory=list)
    permissions: dict[str, str] = field(default_factory=dict)
    open_prs: list[OpenPR] = field(default_factory=list)
    votes: list[dict] = field(default_factory=list)
    orcid: dict | None = None

    @classmethod
    def load(cls, directory: Path | None) -> Context:
        ctx = cls()
        if directory is None:
            return ctx
        d = Path(directory)
        for row in _rows(d / "comments.jsonl") + _rows(d / "comments.json"):
            ctx.comments.append(Comment.from_dict(row))
        ctx.comments.sort(key=lambda c: (c.created_at, c.id))
        for row in _rows(d / "permissions.jsonl") + _rows(d / "permissions.json"):
            if row.get("login"):
                ctx.permissions[row["login"].lower()] = str(row.get("permission") or "none")
        for row in _rows(d / "open-prs.json"):
            branch = row.get("headRefName") or ""
            m = BRANCH_RE.match(branch)
            meta = None
            mm = META_RE.search(row.get("body") or "")
            if mm:
                try:
                    meta = json.loads(mm[1])
                except ValueError:
                    meta = None
            ctx.open_prs.append(OpenPR(int(row["number"]), branch, int(m[1]) if m else None, meta))
        ctx.votes = _rows(d / "votes.json")
        if (d / "orcid.json").is_file():
            ctx.orcid = json.loads((d / "orcid.json").read_text(encoding="utf-8"))
        return ctx

    def permission(self, login: str) -> str:
        return self.permissions.get((login or "").lower(), "none")


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return [x for x in data if isinstance(x, dict)]
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def parse_command(body: str) -> tuple[str, list[str]] | None:
    first = (body or "").strip().splitlines()[0] if (body or "").strip() else ""
    m = COMMAND_RE.match(first.strip())
    if not m or m[1] not in COMMANDS:
        return None
    return m[1], m[2].split()


def commands(ctx: Context, issue_author: str, moderator_permissions: list[str]) -> list[Command]:
    out = []
    for c in ctx.comments:
        if c.user_type == "Bot" or c.user.endswith("[bot]"):
            continue
        parsed = parse_command(c.body)
        if not parsed:
            continue
        name, args = parsed
        mod = ctx.permission(c.user) in moderator_permissions
        out.append(Command(name, args, c.user, c.created_at, mod, c.user.lower() == issue_author.lower(), c.id))
    return out


def last_bot_comment(ctx: Context) -> str | None:
    for c in reversed(ctx.comments):
        if BOT_MARKER in c.body:
            return c.body
    return None
