# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compare a parsed reference with a registry record.

Each component (title, authors, year, venue) is scored separately and reported, so a
reader can see why a match was accepted or rejected. The rules are deliberately
tolerant of the ordinary noise in real bibliographies: journal year vs arXiv posting
year, collaboration names, accents, and styles that print no title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .journals import journals_agree
from .models import Record, Reference
from .textutil import content_tokens, fold, norm_title, tokens

W_TITLE, W_AUTHOR, W_YEAR, W_VENUE = 0.4, 0.25, 0.15, 0.2


@dataclass
class MatchScores:
    title: float | None = None
    title_mode: str | None = None  # "field" (reference printed a title) or "containment" (free text)
    author: float | None = None
    first_author_match: bool | None = None
    year_delta: int | None = None
    year: float | None = None
    venue: float | None = None
    journal_agrees: bool | None = None
    overall: float = 0.0
    coverage: float = 0.0
    agrees: bool = False
    contradicts: bool = False
    strength: str = "none"  # strong | moderate | weak | none

    def to_dict(self) -> dict:
        return {
            "title": None if self.title is None else round(self.title, 3),
            "title_mode": self.title_mode,
            "author": None if self.author is None else round(self.author, 3),
            "first_author_match": self.first_author_match,
            "year": None if self.year is None else round(self.year, 3),
            "year_delta": self.year_delta,
            "venue": None if self.venue is None else round(self.venue, 3),
            "journal_agrees": self.journal_agrees,
            "overall": round(self.overall, 3),
            "coverage": round(self.coverage, 3),
            "agrees": self.agrees,
            "contradicts": self.contradicts,
            "strength": self.strength,
        }


def title_similarity(a: str, b: str) -> float:
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(content_tokens(a)), set(content_tokens(b))
    if not ta or not tb:
        return seq
    jac = len(ta & tb) / len(ta | tb)
    small = min(len(ta), len(tb))
    cont = len(ta & tb) / small if small >= 4 else 0.0
    return max(seq, jac, 0.95 * cont)


def title_containment(record_title: str, raw: str) -> float | None:
    rt = set(content_tokens(record_title))
    if len(rt) < 3:
        return None
    raw_t = set(tokens(raw))
    return len(rt & raw_t) / len(rt)


def _surname_key(s: str) -> str:
    return re.sub(r"[^a-z]", "", fold(s))


def surnames_match(a: str, b: str) -> bool:
    ka, kb = _surname_key(a), _surname_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    la, lb = fold(a).split(), fold(b).split()
    if la and lb and _surname_key(la[-1]) == _surname_key(lb[-1]) and len(_surname_key(la[-1])) > 2:
        return True
    if min(len(ka), len(kb)) >= 4 and (ka.endswith(kb) or kb.endswith(ka)):
        return True
    # index metadata extracted from PDFs sometimes drops ligatures: 'Hoffman' becomes 'Homan'
    la_, lb_ = re.sub(r"ff[il]?|f[il]", "", ka), re.sub(r"ff[il]?|f[il]", "", kb)
    if la_ != ka or lb_ != kb:
        if len(la_) >= 3 and la_ == lb_:
            return True
    if min(len(ka), len(kb)) >= 6:
        return SequenceMatcher(None, ka, kb).ratio() >= 0.88
    return False


def record_family_names(rec: Record) -> list[str]:
    if rec.family_names:
        return rec.family_names
    out = []
    for a in rec.authors:
        a = a.strip()
        if "," in a:
            out.append(a.split(",")[0].strip())
        elif a:
            out.append(a.split()[-1])
    return out


def _page_norm(p: str) -> str:
    p = p.strip().upper()
    m = re.match(r"([A-Z]*)0*(\d+)", p)
    return (m.group(1) + m.group(2)) if m else p


def _vol_norm(v: str) -> str:
    return re.sub(r"^0+", "", re.sub(r"[^0-9A-Za-z]", "", v)).upper()


def compare(ref: Reference, rec: Record) -> MatchScores:
    s = MatchScores()

    # title
    if ref.title and rec.title:
        s.title = title_similarity(ref.title, rec.title)
        s.title_mode = "field"
        if s.title < 0.85 and ref.raw:
            c = title_containment(rec.title, ref.raw)
            if c is not None and c >= 0.9:
                s.title, s.title_mode = max(s.title, 0.9 * c), "containment"
    elif rec.title and ref.raw:
        c = title_containment(rec.title, ref.raw)
        if c is not None:
            s.title, s.title_mode = c, "containment"

    # authors
    rec_fams = record_family_names(rec)
    if ref.authors and rec_fams:
        first = ref.authors[0]
        if surnames_match(first, rec_fams[0]):
            s.author, s.first_author_match = 1.0, True
        elif any(surnames_match(first, r) for r in rec_fams[:5]):
            s.author, s.first_author_match = 0.7, False
        elif any(surnames_match(a, r) for a in ref.authors[1:6] for r in rec_fams[:30]):
            s.author, s.first_author_match = 0.4, False
        else:
            s.author, s.first_author_match = 0.0, False
    elif ref.collaboration and (rec_fams or rec.title):
        words = [w for w in tokens(ref.collaboration) if w not in ("collaboration", "the", "team", "consortium",
                                                                    "survey", "project", "group", "collab")]
        hay = set(tokens(" ".join(rec.authors) + " " + (rec.title or "")))
        if words and all(w in hay for w in words):
            s.author, s.first_author_match = 1.0, True
        # otherwise unknown: large collaborations are listed many ways

    # year
    if ref.year and rec.year:
        s.year_delta = abs(ref.year - rec.year)
        s.year = {0: 1.0, 1: 0.8, 2: 0.3}.get(s.year_delta, 0.0)

    # venue: volume and first page
    checks = []
    if ref.volume and rec.volume:
        rv = _vol_norm(ref.volume)
        ok = rv == _vol_norm(rec.volume)
        # JCAP and JHEP use the year as the volume, and references print the issue in its place
        if not ok and rec.issue:
            ok = rv == _vol_norm(rec.issue)
        if not ok and rec.year and rv == str(rec.year):
            ok = True
        checks.append(ok)
    if ref.page and rec.page:
        checks.append(_page_norm(ref.page) == _page_norm(rec.page))
    if checks:
        s.venue = sum(checks) / len(checks)
    s.journal_agrees = journals_agree(ref.journal, rec.container)

    # combine. A low containment score is neutral: many styles print no title at all.
    title_for_overall = s.title
    if s.title_mode == "containment" and s.title is not None and s.title < 0.5:
        title_for_overall = None
    num = den = 0.0
    for val, w in ((title_for_overall, W_TITLE), (s.author, W_AUTHOR), (s.year, W_YEAR), (s.venue, W_VENUE)):
        if val is not None:
            num += w * val
            den += w
    s.overall = num / den if den else 0.0
    s.coverage = den

    field_title = s.title_mode == "field"
    T = s.title is not None and s.title >= (0.85 if field_title else 0.8)
    T_weak = field_title and s.title is not None and 0.6 <= s.title < 0.85
    T_bad = field_title and ref.title_reliable and s.title is not None and s.title < 0.5
    A = s.author is not None and s.author >= 0.7
    A_bad = s.author is not None and s.author == 0.0
    Y = s.year_delta is not None and s.year_delta <= 1
    Y_bad = s.year_delta is not None and s.year_delta >= 3
    V = s.venue is not None and s.venue == 1.0
    V_bad = s.venue is not None and s.venue == 0.0 and len(checks) == 2

    if T and (A or V) and Y:
        s.strength = "strong"
    elif T and (A or Y or V):
        s.strength = "strong" if (A and s.title >= 0.95) else "moderate"
    elif A and Y and V:
        s.strength = "strong"
    elif (A or (s.author is not None and s.author >= 0.4 and Y)) and V and not T_bad:
        # first author plus volume and page identify an article even when an index dates it
        # differently (OpenAlex often carries the arXiv posting year of a merged record)
        s.strength = "moderate"
    elif T_weak and A and Y and not V_bad:
        s.strength = "moderate"
    elif A and Y and (s.title is None or not field_title) and not V_bad:
        s.strength = "weak"
    elif T and not A_bad and not Y_bad:
        s.strength = "weak"
    s.agrees = s.strength in ("strong", "moderate", "weak") and not (A_bad and Y_bad)

    s.contradicts = bool(
        T_bad
        or (A_bad and (Y_bad or V_bad))
        or (V_bad and Y_bad)
        or (A_bad and not T and not V)
        or (V_bad and not T and not A)
        or (Y_bad and not T and not V)
    )
    if s.contradicts and s.strength != "strong":
        s.agrees = False
    return s
