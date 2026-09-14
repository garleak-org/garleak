# SPDX-License-Identifier: AGPL-3.0-or-later
"""Blog posts and statements: Markdown files with a YAML front matter block under blog/.

A file is named YYYY-MM-DD-slug.md and starts with

    ---
    title: Why Garleak exists
    date: 2026-09-14          # optional, defaults to the date in the file name
    author: Serat Saad        # optional, defaults to "Garleak"
    kind: post                # post or statement
    summary: One line for the index and the feed.   # optional
    draft: true               # optional, a draft is never built
    ---

followed by the Markdown body.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

KINDS = {"post": "Post", "statement": "Statement"}
NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
FRONT = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


class BlogError(ValueError):
    pass


@dataclass
class Post:
    slug: str
    title: str
    date: dt.date
    author: str
    kind: str
    summary: str
    body: str

    @property
    def url(self) -> str:
        return f"/blog/{self.slug}/"

    @property
    def kind_label(self) -> str:
        return KINDS[self.kind]


def load_posts(folder: Path | str | None) -> list[Post]:
    """Every non-draft post, newest first. Raises BlogError on a malformed file."""
    if not folder or not Path(folder).is_dir():
        return []
    posts: list[Post] = []
    for f in sorted(Path(folder).glob("*.md")):
        if f.name.lower() == "readme.md":
            continue
        m = NAME.match(f.name)
        if not m:
            raise BlogError(f"blog/{f.name}: name blog files YYYY-MM-DD-slug.md, in lower case")
        fm = FRONT.match(f.read_text(encoding="utf-8").replace("\r\n", "\n"))
        if not fm:
            raise BlogError(f"blog/{f.name}: the file must start with a --- front matter block")
        meta = yaml.safe_load(fm[1]) or {}
        if not isinstance(meta, dict):
            raise BlogError(f"blog/{f.name}: the front matter must be a YAML mapping")
        if meta.get("draft"):
            continue
        if not str(meta.get("title") or "").strip():
            raise BlogError(f"blog/{f.name}: needs a title")
        kind = meta.get("kind", "post")
        if kind not in KINDS:
            raise BlogError(f"blog/{f.name}: kind must be post or statement, not {kind!r}")
        date = meta.get("date") or m[1]
        if isinstance(date, dt.datetime):
            date = date.date()
        elif isinstance(date, str):
            date = dt.date.fromisoformat(date)
        posts.append(Post(
            slug=m[2], title=str(meta["title"]).strip(), date=date,
            author=str(meta.get("author") or "Garleak").strip(), kind=kind,
            summary=str(meta.get("summary") or "").strip(), body=fm[2],
        ))
    slugs = [p.slug for p in posts]
    dup = sorted({s for s in slugs if slugs.count(s) > 1})
    if dup:
        raise BlogError(f"blog: two posts share the slug {', '.join(dup)}")
    return sorted(posts, key=lambda p: (p.date, p.slug), reverse=True)
