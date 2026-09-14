# SPDX-License-Identifier: AGPL-3.0-or-later
"""Parse compiled bibliographies: natbib/thebibliography .bbl files and biblatex .bbl files."""

from __future__ import annotations

import re

from ..ids import arxiv_from_doi, normalize_arxiv, normalize_doi, parse_bibcode
from ..journals import expand_macros, journal_key
from ..models import Reference
from ..textutil import latex_to_text
from .bibtex import TYPE_FLAGS, _display
from .freetext import _balanced_arg, detect_flags, parse_reference


def is_biblatex(text: str) -> bool:
    return "\\entry{" in text and ("\\field{" in text or "\\name{" in text)


def split_bibitems(text: str) -> list[tuple[str | None, str | None, str]]:
    """Return (label, key, body) for each \\bibitem in a thebibliography environment."""
    m = re.search(r"\\begin\{thebibliography\}", text)
    start = m.end() if m else 0
    end_m = re.search(r"\\end\{thebibliography\}", text[start:])
    region = text[start:start + end_m.start()] if end_m else text[start:]
    # drop the {widest-label} argument after \begin{thebibliography}
    if m:
        wm = re.match(r"\s*\{", region)
        if wm:
            r = _balanced_arg(region, wm.end() - 1)
            if r:
                region = region[r[1]:]
    items = []
    for part in re.split(r"\\bibitem(?![a-zA-Z])", region)[1:]:
        p = part.lstrip()
        label = None
        if p.startswith("["):
            depth = 0
            for i, ch in enumerate(p):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        label = p[1:i]
                        p = p[i + 1:].lstrip()
                        break
        key = None
        if p.startswith("{"):
            r = _balanced_arg(p, 0)
            if r:
                key = r[0].strip()
                p = p[r[1]:]
        body = re.sub(r"%\s*\n", "", p)
        body = re.sub(r"(?m)^\s*%.*$", "", body)
        body = body.replace("\\newblock", " ").strip()
        items.append((label, key, body))
    return items


def parse_thebibliography(text: str, source_format: str = "bbl") -> list[Reference]:
    refs = []
    for label, key, body in split_bibitems(text):
        if not body.strip():
            continue
        refs.append(parse_reference(body, index=len(refs) + 1, source_format=source_format, key=key, label=label))
    return refs


# ----------------------------------------------------------------- biblatex


def _bl_fields(entry: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in re.finditer(r"\\field\{(\w+)\}(?=\{)", entry):
        r = _balanced_arg(entry, m.end())
        if r:
            fields.setdefault(m.group(1), r[0])
    for m in re.finditer(r"\\verb\{(\w+)\}\s*\n?\s*\\verb\s?(.*?)\n\s*\\endverb", entry, re.S):
        fields.setdefault(m.group(1), m.group(2).strip())
    for m in re.finditer(r"\\list\{(\w+)\}\{\d+\}(?=\{)", entry):
        r = _balanced_arg(entry, m.end())
        if r:
            items = re.findall(r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", r[0])
            fields.setdefault(m.group(1), "; ".join(items))
    return fields


def _bl_names(entry: str, role: str = "author") -> list[str]:
    m = re.search(r"\\name\{" + role + r"\}\{\d+\}\{[^{}]*\}(?=\{)", entry)
    if not m:
        return []
    r = _balanced_arg(entry, m.end())
    if not r:
        return []
    fams = []
    for fm in re.finditer(r"family=(\{(?:[^{}]|\{[^{}]*\})*\}|[^,}]+)", r[0]):
        v = fm.group(1)
        if v.startswith("{"):
            v = v[1:-1]
        fams.append(latex_to_text(v))
    return [f for f in fams if f]


def parse_biblatex_bbl(text: str) -> list[Reference]:
    refs = []
    for m in re.finditer(r"\\entry\{([^}]*)\}\{(\w+)\}\{[^}]*\}(.*?)\\endentry", text, re.S):
        key, etype, body = m.group(1), m.group(2).lower(), m.group(3)
        f = _bl_fields(body)
        authors = _bl_names(body, "author") or _bl_names(body, "editor")
        collab = None
        if authors and re.search(r"collaboration|consortium|team", authors[0], re.I):
            collab = authors.pop(0)
        title = latex_to_text(f.get("title")) or None
        year = None
        ym = re.search(r"(1[89]\d\d|20\d\d)", f.get("year", "") or f.get("date", "") or f.get("origyear", ""))
        if ym:
            year = int(ym.group(1))
        jr = f.get("journaltitle") or f.get("journal") or f.get("booktitle")
        journal = latex_to_text(expand_macros(jr)) if jr else None
        pages = latex_to_text(f.get("pages", "")) or None
        page = re.split(r"[-\u2013]+", pages)[0].strip() if pages else None
        doi = normalize_doi(f.get("doi"))
        arxiv = None
        if f.get("eprint") and f.get("eprinttype", "arxiv").lower() in ("arxiv", ""):
            arxiv = normalize_arxiv(f["eprint"])
        if doi and arxiv_from_doi(doi):
            arxiv = arxiv or arxiv_from_doi(doi)
            doi = None
        url = f.get("url")
        volume = latex_to_text(f.get("volume", "")) or None
        ref = Reference(
            index=len(refs) + 1, raw=_display(authors, collab, year, title, journal, volume, page, doi, arxiv),
            source_format="biblatex-bbl", key=key, entry_type=etype, title=title, title_reliable=bool(title),
            authors=authors, collaboration=collab, year=year, journal=journal, volume=volume, page=page,
            doi=doi, arxiv=arxiv, url=url, bibcode_hint=key if parse_bibcode(key) else None,
        )
        flags = [TYPE_FLAGS[etype]] if etype in TYPE_FLAGS else []
        flags += [fl for fl in detect_flags(latex_to_text(f.get("note", "") + " " + f.get("howpublished", "")))
                  if fl in ("private_communication", "in_preparation", "submitted", "unpublished")]
        if journal and journal_key(journal)[1]:
            flags.append("journal_string_typo")
        ref.flags = list(dict.fromkeys(flags))
        refs.append(ref)
    return refs


def load_bbl(text: str) -> list[Reference]:
    if is_biblatex(text):
        return parse_biblatex_bbl(text)
    return parse_thebibliography(text, "bbl")
