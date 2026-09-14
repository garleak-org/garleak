# SPDX-License-Identifier: AGPL-3.0-or-later
"""Word-level diff of two Markdown sources, rendered to HTML with <ins> and <del>.

Paragraph and heading boundaries are kept as sentinel tokens, so the rendered diff keeps
the block structure of the newer text. The diff is over the source, not a rendering, so
it shows exactly what a person changed.
"""

from __future__ import annotations

import difflib
import html
import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+")
_SENTINEL = "\x00"


def _blocks(text: str) -> list[tuple[str, str]]:
    """Split Markdown into (kind, text) blocks: kind is 'p' or 'h1'..'h6'."""
    out: list[tuple[str, str]] = []
    for chunk in re.split(r"\n\s*\n", (text or "").strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _HEADING.match(chunk)
        if m and "\n" not in chunk:
            out.append((f"h{len(m[1])}", chunk[m.end():]))
        else:
            out.append(("p", " ".join(chunk.split())))
    return out


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for kind, block in _blocks(text):
        out.append(_SENTINEL + kind)
        out.extend(block.split())
    return out


@dataclass(frozen=True)
class DiffResult:
    ops: list[tuple[str, list[str]]]  # ("=", words) | ("+", words) | ("-", words)
    added: int
    removed: int

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed)


def word_diff(a: str, b: str) -> DiffResult:
    ta, tb = tokens(a), tokens(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    ops: list[tuple[str, list[str]]] = []
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            ops.append(("=", ta[i1:i2]))
            continue
        if tag in ("delete", "replace"):
            ops.append(("-", ta[i1:i2]))
            removed += sum(1 for t in ta[i1:i2] if not t.startswith(_SENTINEL))
        if tag in ("insert", "replace"):
            ops.append(("+", tb[j1:j2]))
            added += sum(1 for t in tb[j1:j2] if not t.startswith(_SENTINEL))
    return DiffResult(ops, added, removed)


def render_html(result: DiffResult) -> str:
    """Render a DiffResult as a sequence of <p> / <hN> blocks."""
    blocks: list[tuple[str, list[str]]] = []

    def current() -> list[str]:
        if not blocks:
            blocks.append(("p", []))
        return blocks[-1][1]

    for tag, words in result.ops:
        run: list[str] = []

        def flush() -> None:
            if not run:
                return
            text = html.escape(" ".join(run))
            if tag == "+":
                current().append(f"<ins>{text}</ins>")
            elif tag == "-":
                current().append(f"<del>{text}</del>")
            else:
                current().append(text)
            run.clear()

        for w in words:
            if w.startswith(_SENTINEL):
                flush()
                kind = w[1:]
                if tag == "-":
                    current().append('<del class="pb" title="block break removed">&#182;</del>')
                else:
                    blocks.append((kind, []))
            else:
                run.append(w)
        flush()

    out = []
    for kind, parts in blocks:
        if not parts:
            continue
        tagname = "p" if kind == "p" else f"h{min(6, int(kind[1:]) + 2)}"
        out.append(f"<{tagname}>{' '.join(parts)}</{tagname}>")
    return "\n".join(out)


def inline_diff_html(a: str, b: str) -> str:
    """Diff of short one-block texts such as titles, rendered without block tags."""
    res = word_diff(a, b)
    parts: list[str] = []
    for tag, words in res.ops:
        text = html.escape(" ".join(w for w in words if not w.startswith(_SENTINEL)))
        if not text:
            continue
        parts.append(f"<ins>{text}</ins>" if tag == "+" else f"<del>{text}</del>" if tag == "-" else text)
    return " ".join(parts)
