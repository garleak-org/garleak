# SPDX-License-Identifier: AGPL-3.0-or-later
"""A small dependency-free BibTeX parser (entries, @string macros, # concatenation)."""

from __future__ import annotations

import re

from ..ids import arxiv_from_doi, normalize_arxiv, normalize_doi, parse_bibcode, pos_from_url
from ..journals import expand_macros, journal_key
from ..models import Reference
from ..textutil import latex_to_text
from .freetext import detect_flags, family_names

_MONTHS = {m: m for m in "jan feb mar apr may jun jul aug sep oct nov dec".split()}

TYPE_FLAGS = {
    "book": "book", "inbook": "book", "incollection": "book", "booklet": "book",
    "phdthesis": "thesis", "mastersthesis": "thesis", "thesis": "thesis",
    "techreport": "report", "report": "report", "manual": "software", "software": "software",
    "online": "website", "electronic": "website", "unpublished": "unpublished",
    "inproceedings": "proceedings", "proceedings": "proceedings", "conference": "proceedings",
    "dataset": "catalog",
}


class BibTexError(ValueError):
    pass


def _read_braced(s: str, i: int) -> tuple[str, int]:
    depth = 0
    start = i
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
        i += 1
    raise BibTexError("unbalanced braces")


def _read_quoted(s: str, i: int) -> tuple[str, int]:
    depth = 0
    j = i + 1
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == '"' and depth == 0:
            return s[i + 1:j], j + 1
        j += 1
    raise BibTexError("unterminated quoted value")


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and (s[i].isspace() or s[i] == "%"):
        if s[i] == "%":
            while i < len(s) and s[i] != "\n":
                i += 1
        else:
            i += 1
    return i


def _read_value(s: str, i: int, strings: dict[str, str]) -> tuple[str, int]:
    parts = []
    while True:
        i = _skip_ws(s, i)
        if i >= len(s):
            break
        c = s[i]
        if c == "{":
            v, i = _read_braced(s, i)
        elif c == '"':
            v, i = _read_quoted(s, i)
        else:
            m = re.match(r"[^\s,#})]+", s[i:])
            if not m:
                break
            tok = m.group(0)
            i += len(tok)
            v = strings.get(tok.lower(), _MONTHS.get(tok.lower(), tok))
        parts.append(v)
        i = _skip_ws(s, i)
        if i < len(s) and s[i] == "#":
            i += 1
            continue
        break
    return "".join(parts), i


def parse_bibtex(text: str) -> list[dict]:
    """Return a list of {'type', 'key', 'fields'} dicts. Field names are lowercased."""
    entries: list[dict] = []
    strings: dict[str, str] = {}
    i = 0
    n = len(text)
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        m = re.match(r"@\s*([A-Za-z]+)\s*([{(])", text[at:])
        if not m:
            i = at + 1
            continue
        etype = m.group(1).lower()
        opener = m.group(2)
        closer = "}" if opener == "{" else ")"
        j = at + m.end()
        try:
            if etype == "comment":
                if opener == "{":
                    _, j = _read_braced(text, j - 1)
                i = j
                continue
            if etype == "preamble":
                _, j = _read_value(text, j, strings)
                i = j + 1
                continue
            if etype == "string":
                j = _skip_ws(text, j)
                km = re.match(r"([^\s=]+)\s*=", text[j:])
                if km:
                    v, j = _read_value(text, j + km.end(), strings)
                    strings[km.group(1).lower()] = v
                i = j + 1
                continue
            j = _skip_ws(text, j)
            km = re.match(r"([^,\s}]*)\s*,", text[j:])
            if not km:
                i = j
                continue
            key = km.group(1)
            j += km.end()
            fields: dict[str, str] = {}
            while j < n:
                j = _skip_ws(text, j)
                if j < n and text[j] == closer:
                    j += 1
                    break
                fm = re.match(r"([A-Za-z0-9_\-:.+]+)\s*=\s*", text[j:])
                if not fm:
                    # tolerate junk: skip to next comma or closer
                    nxt = min([p for p in (text.find(",", j), text.find(closer, j)) if p >= 0] or [n])
                    if nxt < n and text[nxt] == closer:
                        j = nxt + 1
                        break
                    j = nxt + 1
                    continue
                name = fm.group(1).lower()
                v, j = _read_value(text, j + fm.end(), strings)
                fields[name] = v.strip()
                j = _skip_ws(text, j)
                if j < n and text[j] == ",":
                    j += 1
            entries.append({"type": etype, "key": key, "fields": fields})
            i = j
        except BibTexError:
            i = at + 1
    return entries


def split_authors(value: str) -> list[str]:
    """Split a BibTeX author field on ' and ' at brace depth zero."""
    out, depth, cur, i = [], 0, [], 0
    while i < len(value):
        c = value[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0 and re.match(r"\s+and\s+", value[i:], re.I):
            out.append("".join(cur).strip())
            cur = []
            i += re.match(r"\s+and\s+", value[i:], re.I).end()
            continue
        cur.append(c)
        i += 1
    if cur:
        out.append("".join(cur).strip())
    return [a for a in out if a]


def _balanced_whole(s: str) -> bool:
    """True when the outer braces of s enclose the whole string ('{A B}', not '{A} {B}')."""
    depth = 0
    for i, c in enumerate(s):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and i != len(s) - 1:
                return False
    return depth == 0


def _family(name: str) -> tuple[str | None, bool]:
    """(family name, is_collaboration) for one BibTeX name."""
    raw = name.strip()
    if raw.lower() in ("others", "et al", "et al."):
        return None, False
    if raw.startswith("{") and raw.endswith("}") and "," not in raw[1:-1] and _balanced_whole(raw):
        inner = latex_to_text(raw[1:-1])
        if re.search(r"collaboration|consortium|team|survey|project|group", inner, re.I) or len(inner.split()) > 2:
            return inner, True
        return inner, False  # a corporate author such as {TensorFlow Developers}
    t = latex_to_text(raw)
    if not t:
        return None, False
    if re.search(r"collaboration|consortium|\bteam\b", t, re.I):
        return t, True
    if "," in t:
        return t.split(",")[0].strip(), False
    parts = t.split()
    return parts[-1] if parts else None, False


def entry_to_reference(e: dict, index: int) -> Reference:
    f = e["fields"]
    etype = e["type"]
    title = latex_to_text(f.get("title")) or None
    authors: list[str] = []
    collab = None
    names = split_authors(f.get("author", "")) or split_authors(f.get("editor", ""))
    for nm in names:
        fam, is_col = _family(nm)
        if not fam:
            continue
        if is_col and not authors and collab is None:
            collab = fam
            continue
        authors.append(fam)
    year = None
    ym = re.search(r"(1[89]\d\d|20\d\d)", f.get("year", "") or f.get("date", ""))
    if ym:
        year = int(ym.group(1))
    journal_raw = f.get("journal") or f.get("journaltitle") or f.get("booktitle") or f.get("series")
    journal = latex_to_text(expand_macros(journal_raw)) if journal_raw else None
    pages = latex_to_text(f.get("pages", "")) or None
    page = re.split(r"[-–]+", pages)[0].strip() if pages else None
    doi = normalize_doi(f.get("doi"))
    arxiv = None
    eprint = f.get("eprint", "")
    archive = (f.get("archiveprefix") or f.get("eprinttype") or "").lower()
    if eprint and (archive in ("", "arxiv") or re.search(r"\d{4}\.\d{4,5}|/\d{7}", eprint)):
        arxiv = normalize_arxiv(eprint)
    if doi and arxiv_from_doi(doi):
        arxiv = arxiv or arxiv_from_doi(doi)
        doi = None
    url = f.get("url") or f.get("howpublished") or None
    if url:
        url = latex_to_text(url.replace("\\url", "")) or None
        if url and not doi and "doi.org/" in url:
            doi = normalize_doi(url)
        if url and not arxiv and "arxiv.org/" in url:
            arxiv = normalize_arxiv(url)
    if not doi:
        for fld in ("note", "howpublished"):
            if f.get(fld) and "10." in f[fld]:
                doi = normalize_doi(f[fld]) or doi
    if not arxiv:
        for fld in ("journal", "note", "howpublished"):
            v = f.get(fld, "")
            m = re.search(r"arxiv[:\s]*([\w./\-]+\d)", v, re.I)
            if m:
                arxiv = normalize_arxiv(m.group(1))
                break
    bibcode = None
    adsurl = f.get("adsurl", "")
    m = re.search(r"/abs/([0-9]{4}[\w.&%]{15})", adsurl)
    if m:
        from urllib.parse import unquote
        bc = unquote(m.group(1))
        if parse_bibcode(bc):
            bibcode = bc
    volume = latex_to_text(f.get("volume", "")) or None
    display = _display(authors, collab, year, title, journal, volume, page, doi, arxiv)
    ref = Reference(
        index=index, raw=display, source_format="bibtex", key=e["key"], entry_type=etype,
        title=title, title_reliable=bool(title), authors=authors, collaboration=collab, year=year,
        journal=journal, volume=volume, page=page, doi=doi, arxiv=arxiv, bibcode=bibcode,
        bibcode_hint=e["key"] if parse_bibcode(e["key"]) else None, url=url,
    )
    flags = []
    if etype in TYPE_FLAGS:
        flags.append(TYPE_FLAGS[etype])
    text_for_flags = " ".join(latex_to_text(f.get(k, "")) for k in ("note", "howpublished", "journal", "publisher",
                                                                    "title", "booktitle"))
    for fl in detect_flags(text_for_flags):
        if fl in ("private_communication", "in_preparation", "submitted", "unpublished", "in_press"):
            flags.append(fl)
    if journal and journal_key(journal)[1]:
        flags.append("journal_string_typo")
    if pos_from_url(url):
        flags.append("pos")
    ref.flags = list(dict.fromkeys(flags))
    return ref


def _display(authors, collab, year, title, journal, volume, page, doi, arxiv) -> str:
    who = collab or ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    parts = [who.strip() or "(no author)"]
    if year:
        parts.append(f"({year})")
    if title:
        parts.append(title + ".")
    venue = " ".join(x for x in (journal, volume) if x)
    if page:
        venue = f"{venue}, {page}" if venue else page
    if venue:
        parts.append(venue + ".")
    if doi:
        parts.append(f"doi:{doi}")
    if arxiv:
        parts.append(f"arXiv:{arxiv}")
    return " ".join(parts)


def load_bibtex(text: str, cited_keys: set[str] | None = None) -> list[Reference]:
    refs = []
    for e in parse_bibtex(text):
        if cited_keys is not None and e["key"] not in cited_keys:
            continue
        if e["type"] in ("comment", "preamble", "string", "xdata", "set"):
            continue
        refs.append(entry_to_reference(e, len(refs) + 1))
    return refs
