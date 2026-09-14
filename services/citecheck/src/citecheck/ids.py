# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifier extraction, normalization, and repair candidates (DOI, arXiv, ADS bibcode, PoS)."""

from __future__ import annotations

import datetime as _dt
import re
from urllib.parse import unquote

# ---------------------------------------------------------------- DOI

_DOI_CORE = re.compile(r"10\.\d{4,9}/[^\s\"<>{}\\]+")
_DOI_PREFIX = re.compile(r"^(?:https?://)?(?:dx\.|www\.)?doi\.org/|^doi\s*:\s*", re.I)


def _trim_doi(d: str) -> str:
    while d and d[-1] in ".,;:'\"]}>":
        d = d[:-1]
    while d.endswith(")") and d.count("(") < d.count(")"):
        d = d[:-1]
    return d


def normalize_doi(s: str | None) -> str | None:
    """Return a lowercased bare DOI, or None when the string holds no DOI."""
    if not s:
        return None
    s = s.strip().replace("\\_", "_").replace("{", "").replace("}", "")
    s = unquote(s)
    s = _DOI_PREFIX.sub("", s.strip())
    m = _DOI_CORE.search(s)
    if not m:
        return None
    d = _trim_doi(m.group(0))
    return d.lower() if len(d) > 8 else None


def extract_dois(latex: str) -> list[str]:
    """All DOIs in a LaTeX or plain-text fragment, in order of appearance, deduplicated."""
    text = latex.replace("\\_", "_").replace("{\\_}", "_")
    found: list[str] = []
    for m in re.finditer(r"(?:https?://)?(?:dx\.)?doi\.org/(10\.[^\s\"<>{}\\]+)", text, re.I):
        found.append(m.group(1))
    for m in re.finditer(r"\\(?:doi|dodoi)\s*\{([^{}]+)\}", text):
        found.append(m.group(1))
    for m in _DOI_CORE.finditer(text):
        found.append(m.group(0))
    out: list[str] = []
    for f in found:
        d = normalize_doi(f)
        if d and d not in out and not any(d != o and o.startswith(d) for o in out):
            out.append(d)
    return out


def arxiv_from_doi(doi: str | None) -> str | None:
    """10.48550/arXiv.2106.15656 -> 2106.15656 (arXiv's own DataCite DOIs)."""
    if not doi:
        return None
    m = re.match(r"10\.48550/arxiv\.(.+)$", doi, re.I)
    return normalize_arxiv(m.group(1)) if m else None


def pos_from_doi(doi: str | None) -> tuple[str, str] | None:
    """10.22323/1.444.0905 -> ('444', '905'). Proceedings of Science DOIs."""
    if not doi:
        return None
    m = re.match(r"10\.22323/1\.(\d+)\.0*(\d+)$", doi)
    if not m:
        return None
    return m.group(1), m.group(2).zfill(3)


def pos_from_url(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    m = re.search(r"pos\.sissa\.it/(?:archive/conferences/)?(\d+)/0*(\d+)", url)
    return (m.group(1), m.group(2).zfill(3)) if m else None


_DOI_TAIL_JUNK = re.compile(
    r"(/(?:abstract|full|pdf|epdf|meta|fulltext|html|suppl[\w.\-]*|references|figures|summary)"
    r"|\.pdf|[?#].*)$",
    re.I,
)


def doi_repairs(doi: str) -> list[tuple[str, str]]:
    """Cheap, conservative repair candidates for a DOI that does not resolve.

    Encodes failure classes seen in the llm-in-astro-ph citation audit: URL tails pasted
    into the DOI, and doubled letters in a journal slug ('mmnras' for 'mnras').
    Returns (candidate, description) pairs, at most four.
    """
    out: list[tuple[str, str]] = []
    if "/" not in doi:
        return out
    prefix, suffix = doi.split("/", 1)
    stripped = _DOI_TAIL_JUNK.sub("", suffix)
    if stripped != suffix and len(stripped) > 2:
        out.append((f"{prefix}/{stripped}", f"removed trailing URL fragment '{suffix[len(stripped):]}'"))
    m = re.match(r"([a-z]+)([./].*)?$", suffix)
    if m:
        word = m.group(1)
        rest = m.group(2) or ""
        for dm in re.finditer(r"([a-z])\1", word):
            fixed = word[: dm.start()] + word[dm.start() + 1:]
            if len(fixed) >= 2:
                out.append((f"{prefix}/{fixed}{rest}", f"collapsed doubled letter '{word}' -> '{fixed}'"))
    seen: set[str] = set()
    uniq = []
    for c, why in out:
        if c != doi and c not in seen:
            seen.add(c)
            uniq.append((c, why))
    return uniq[:4]


def doi_prefix(doi: str | None) -> str | None:
    return doi.split("/", 1)[0] if doi and "/" in doi else None


# ---------------------------------------------------------------- arXiv

_OLD_ARCHIVES = (
    "astro-ph|gr-qc|hep-ph|hep-th|hep-ex|hep-lat|nucl-th|nucl-ex|quant-ph|cond-mat|math-ph|"
    "physics|math|cs|nlin|q-bio|q-fin|stat|chao-dyn|solv-int|patt-sol|adap-org|comp-gas|"
    "alg-geom|dg-ga|funct-an|q-alg|chem-ph|atom-ph|plasm-ph|supr-con|mtrl-th|acc-phys|bayes-an"
)
ARXIV_NEW_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])")
ARXIV_OLD_RE = re.compile(r"((?:" + _OLD_ARCHIVES + r")(?:\.[A-Za-z]{2})?/\d{7})(v\d+)?", re.I)


def normalize_arxiv(s: str | None) -> str | None:
    """'arXiv:2106.15656v2' -> '2106.15656'; 'astro-ph/0601001' kept. None if no ID shape."""
    if not s:
        return None
    s = s.strip()
    s = re.sub(r"^(?:https?://)?(?:export\.)?arxiv\.org/(?:abs|pdf)/", "", s, flags=re.I)
    s = re.sub(r"^arxiv\s*:\s*", "", s, flags=re.I)
    s = re.sub(r"\.pdf$", "", s)
    m = ARXIV_OLD_RE.search(s)
    if m:
        return m.group(1).lower()
    m = ARXIV_NEW_RE.search(s)
    if m:
        return m.group(1)
    return None


def arxiv_well_formed(aid: str) -> bool:
    """Check the YYMM.NNNNN shape against arXiv's numbering rules."""
    if "/" in aid:
        m = re.match(r".+/(\d{2})(\d{2})\d{3}$", aid)
        if not m:
            return False
        yy, mm = int(m.group(1)), int(m.group(2))
        return 1 <= mm <= 12 and (yy >= 91 or yy <= 7)
    m = re.match(r"(\d{2})(\d{2})\.(\d{4,5})$", aid)
    if not m:
        return False
    yy, mm, num = int(m.group(1)), int(m.group(2)), m.group(3)
    this_year = _dt.date.today().year % 100
    if not (1 <= mm <= 12) or yy < 7 or yy > this_year + 1:
        return False
    if (yy, mm) >= (15, 1):
        return len(num) == 5
    return len(num) == 4


def arxiv_year(aid: str) -> int | None:
    m = re.match(r"(\d{2})\d{2}\.", aid) or re.match(r".+/(\d{2})\d{5}$", aid)
    if not m:
        return None
    yy = int(m.group(1))
    return 2000 + yy if yy < 90 else 1900 + yy


def extract_arxiv(latex: str) -> list[str]:
    """arXiv IDs that appear in an arXiv context (URL, 'arXiv:' prefix, \\eprint, [ID])."""
    found: list[str] = []
    pats = [
        r"arxiv\.org/(?:abs|pdf)/([\w.\-/]+?\d)(?:v\d+)?(?:\.pdf)?(?=[\s}\]\)\"'#?,;]|$)",
        r"\\(?:doarXiv|eprint|arxiv)\s*\{([^{}]+)\}",
        r"10\.48550/arxiv\.([\w.\-/]+\d)",
        r"arxiv(?:\s*e-?prints?)?[\s,:.]*(?:p\.\s*)?(?:arxiv\s*:\s*)?(?:\[[\w\-.]+\]\s*)?"
        r"(\d{4}\.\d{4,5}|(?:" + _OLD_ARCHIVES + r")(?:\.[A-Za-z]{2})?/\d{7})",
        r"\[\s*(?:\\ttfamily\s*)?\{?\s*(\d{4}\.\d{4,5})(?:v\d+)?\s*\}?\s*\]",
        r"(?<![\w/.])((?:" + _OLD_ARCHIVES + r")(?:\.[A-Za-z]{2})?/\d{7})",
    ]
    for p in pats:
        for m in re.finditer(p, latex, re.I):
            a = normalize_arxiv(m.group(1))
            if a:
                found.append(a)
    out: list[str] = []
    for a in found:
        if a not in out:
            out.append(a)
    return out


# ---------------------------------------------------------------- ADS bibcode

BIBCODE_RE = re.compile(r"^(\d{4})([A-Za-z&.]{5})([\w.]{4})([A-Za-z.\d])([\w.]{4})([A-Z.:])$")


def parse_bibcode(code: str | None) -> dict | None:
    """Split a 19-character ADS bibcode into year, bibstem, volume, page, initial."""
    if not code or len(code) != 19:
        return None
    m = BIBCODE_RE.match(code)
    if not m:
        return None
    year = int(m.group(1))
    if not (1800 <= year <= _dt.date.today().year + 1):
        return None
    bibstem = m.group(2).strip(".")
    volume = m.group(3).strip(".")
    qual = m.group(4)
    page = m.group(5).strip(".")
    if bibstem.lower() == "arxiv":
        return {"year": year, "bibstem": "arXiv", "volume": None, "page": None,
                "arxiv": f"{volume}.{qual}{page}" if qual.isdigit() else None,
                "initial": m.group(6)}
    if qual.islower() and qual.isalpha():
        page = str(ord(qual) - 96) + page.zfill(4)
    elif qual.isalpha() and qual not in ".":
        page = qual + page
    if not bibstem or not any(ch.isalpha() for ch in bibstem):
        return None
    return {"year": year, "bibstem": bibstem, "volume": volume or None, "page": page or None,
            "initial": m.group(6)}


def looks_like_bibcode(code: str | None) -> bool:
    return parse_bibcode(code) is not None
