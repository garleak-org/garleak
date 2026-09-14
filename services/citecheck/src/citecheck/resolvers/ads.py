# SPDX-License-Identifier: AGPL-3.0-or-later
"""NASA ADS (optional). Used only when a token is available.

The token is read from the ADS_TOKEN environment variable or from ~/.ads/dev_key. It is
sent only in the Authorization header. It is never printed, logged, cached, or written
into a report: cache keys and cache files are built from the URL alone.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from ..journals import BIBSTEMS, journal_key
from ..models import Record, Reference
from ..textutil import content_tokens
from .base import Lookup, Resolver

API = "https://api.adsabs.harvard.edu/v1/search/query"
FL = "bibcode,title,author,year,pub,volume,issue,page,doi,identifier,doctype"
INTERVAL = 0.4


def load_token() -> str | None:
    tok = os.environ.get("ADS_TOKEN", "").strip()
    if tok:
        return tok
    p = Path.home() / ".ads" / "dev_key"
    try:
        if p.is_file():
            tok = p.read_text().strip()
            return tok or None
    except OSError:
        return None
    return None


def parse_doc(d: dict) -> Record:
    authors = d.get("author") or []
    fams = [a.split(",")[0].strip() for a in authors]
    ids = {"bibcode": d.get("bibcode", "")}
    if d.get("doi"):
        ids["doi"] = d["doi"][0].lower()
    for ident in d.get("identifier") or []:
        m = re.match(r"arxiv:(.+)$", ident, re.I)
        if m:
            ids["arxiv"] = m.group(1)
            break
    year = d.get("year")
    page = (d.get("page") or [None])[0]
    return Record(source="ads", ids=ids, title=(d.get("title") or [None])[0], authors=authors, family_names=fams,
                  year=int(year) if year and str(year).isdigit() else None, container=d.get("pub"),
                  volume=d.get("volume"), page=page, type=d.get("doctype"), registry=None, issue=d.get("issue"))


def _q(s: str) -> str:
    return s.replace('"', " ").replace("\\", " ")


class AdsResolver(Resolver):
    name = "ads"
    kinds = ("doi", "arxiv", "bibcode")
    searchable = True

    def __init__(self, http, token: str | None = None):
        super().__init__(http)
        self._token = token if token is not None else load_token()

    def available(self) -> bool:
        return bool(self._token)

    def _query(self, q: str, rows: int = 5) -> Lookup:
        def run() -> Lookup:
            resp = self.http.get(API, params={"q": q, "fl": FL, "rows": rows},
                                 headers={"Authorization": f"Bearer {self._token}"}, ns="ads", rate_key="ads",
                                 interval=INTERVAL)
            if resp.status == 401:
                return Lookup("error", query=q, note="ADS rejected the token (HTTP 401)")
            if resp.status != 200:
                return Lookup("error", query=q, note=f"HTTP {resp.status}")
            docs = resp.json().get("response", {}).get("docs", [])
            recs = [parse_doc(d) for d in docs]
            return Lookup("found" if recs else "not_found", recs, query=q)

        if not self._token:
            return Lookup("skipped", query=q, note="no ADS token")
        return self._guard(q, run)

    def lookup(self, kind: str, value: str) -> Lookup:
        if kind == "doi":
            return self._query(f'doi:"{_q(value)}"', rows=3)
        if kind == "arxiv":
            return self._query(f'identifier:"arXiv:{_q(value)}"', rows=3)
        if kind == "bibcode":
            # identifier: also matches alternate bibcodes (an arXiv bibcode merged into the
            # journal record keeps working this way; bibcode: would miss it)
            return self._query(f'identifier:"{_q(value)}"', rows=1)
        return Lookup("skipped", query=value)

    def search(self, ref: Reference) -> Lookup:
        queries = []
        first = re.sub(r"[^\w\-' ]", "", ref.authors[0]) if ref.authors else None
        if ref.volume and ref.page:
            key, _ = journal_key(ref.journal)
            stem = BIBSTEMS.get(key) if key else None
            page = _q(ref.page)
            if stem:
                queries.append(f'bibstem:"{stem}" volume:"{_q(ref.volume)}" page:"{page}"')
            yr = f" year:{ref.year - 1}-{ref.year + 1}" if ref.year else ""
            au = f' author:"^{first}"' if first else ""
            if yr or au:
                queries.append(f'volume:"{_q(ref.volume)}" page:"{page}"{yr}{au}')
        if ref.title:
            words = [w for w in content_tokens(ref.title) if not w.isdigit()][:10]
            if len(words) >= 3:
                q = "title:(" + " ".join(words) + ")"
                if first:
                    q += f' author:"{first}"'
                if ref.year:
                    q += f" year:{ref.year - 1}-{ref.year + 1}"
                queries.append(q)
        if not queries and first and ref.year and ref.journal:
            key, _ = journal_key(ref.journal)
            stem = BIBSTEMS.get(key) if key else None
            if stem:
                queries.append(f'author:"^{first}" year:{ref.year} bibstem:"{stem}"')
        if not queries:
            return Lookup("skipped", note="not enough metadata for an ADS query")
        recs: list[Record] = []
        status = "not_found"
        notes = []
        # Queries run from most to least specific; stop at the first one that returns anything.
        # ADS allows 5000 queries a day, so the checker (not this loop) decides whether to look
        # further, in other resolvers, when these candidates do not match.
        for q in queries:
            lk = self._query(q)
            if lk.status == "found":
                recs.extend(lk.records)
                status = "found"
                break
            elif lk.status in ("error", "offline_miss", "skipped") and status != "found":
                status = lk.status if lk.status != "skipped" else status
                if lk.note:
                    notes.append(lk.note)
        return Lookup(status, recs, query=" | ".join(queries), note="; ".join(notes) or None)
