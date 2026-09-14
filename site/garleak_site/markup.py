# SPDX-License-Identifier: AGPL-3.0-or-later
"""Markdown rendering.

Record bodies come from submitters, so raw HTML in them is shown as text, never passed
through, and links keep only http, https, mailto and in-page targets. Relative image and
link targets point into the version's source directory, where the build copies its files.
"""

from __future__ import annotations

import re

import markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

_ALLOWED = ("http://", "https://", "mailto:", "#")


class _SafeLinks(Treeprocessor):
    def __init__(self, md, src_base: str):
        super().__init__(md)
        self.src_base = src_base

    def run(self, root):
        for el in root.iter():
            for attr in ("href", "src"):
                value = el.get(attr)
                if value is None or value.startswith(_ALLOWED):
                    continue
                head = value.split("/", 1)[0]
                if value.startswith(("/", "\\")) or ":" in head:
                    del el.attrib[attr]  # site-absolute paths and other schemes
                else:
                    el.set(attr, self.src_base + value)


class SafeRecords(Extension):
    def __init__(self, src_base: str):
        super().__init__()
        self.src_base = src_base

    def extendMarkdown(self, md):
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")
        md.treeprocessors.register(_SafeLinks(md, self.src_base), "garleak_safe_links", 0)


def render_body(text: str, src_base: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", SafeRecords(src_base)],
        output_format="html",
    )
    return md.convert(text or "")


def render_spec(text: str) -> tuple[str, str, str]:
    """SPEC.md as (title, HTML body without its h1, table of contents), with ids on headings."""
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
        output_format="html",
    )
    html = md.convert(text)
    title = "Specification"
    m = re.match(r"\s*<h1[^>]*>(.*?)</h1>\s*", html, flags=re.S)
    if m:
        title = re.sub(r"<[^>]+>", "", m[1]).strip()
        html = html[m.end():]
    return title, html, md.toc
