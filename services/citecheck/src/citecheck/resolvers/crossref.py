# SPDX-License-Identifier: AGPL-3.0-or-later
"""Crossref REST API: DOI lookup (batched through the doi filter) and bibliographic search.

The polite-pool contact address is taken only from the CITECHECK_MAILTO environment
variable and sent in the User-Agent header (see citecheck.http). No default exists.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from ..models import Record, Reference
from .base import Lookup, Resolver

API = "https://api.crossref.org/works"
SELECT = ("DOI,title,subtitle,author,issued,container-title,short-container-title,volume,issue,page,"
          "article-number,type,published-print,published-online")
INTERVAL = 0.25
BATCH = 20


def _clean_title(t: str | None) -> str | None:
    if not t:
        return None
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"[*†‡]+\s*$", "", t.strip())
    return re.sub(r"\s+", " ", t).strip() or None


def parse_item(m: dict) -> Record:
    title = _clean_title((m.get("title") or [None])[0])
    authors, fams = [], []
    for a in m.get("author") or []:
        if a.get("family"):
            authors.append(", ".join(x for x in (a.get("family"), a.get("given")) if x))
            fams.append(a["family"])
        elif a.get("name"):
            authors.append(a["name"])
            fams.append(a["name"])
    year = None
    for k in ("issued", "published-print", "published-online"):
        dp = (m.get(k) or {}).get("date-parts") or [[None]]
        if dp and dp[0] and dp[0][0]:
            year = int(dp[0][0])
            break
    container = (m.get("container-title") or m.get("short-container-title") or [None])[0]
    page = m.get("page") or m.get("article-number")
    if page:
        page = re.split(r"[-–]", str(page))[0].strip()
    return Record(source="crossref", ids={"doi": (m.get("DOI") or "").lower()}, title=title, authors=authors,
                  family_names=fams, year=year, container=container, volume=m.get("volume"), page=page,
                  type=m.get("type"), registry="Crossref", issue=m.get("issue"))


def compose_query(ref: Reference) -> str:
    if ref.source_format in ("bibtex", "biblatex-bbl"):
        parts = [" ".join(ref.authors[:3]) or (ref.collaboration or ""), str(ref.year or ""), ref.title or "",
                 ref.journal or "", ref.volume or "", ref.page or ""]
        q = " ".join(p for p in parts if p)
    else:
        q = ref.raw
        q = re.sub(r"https?://\S+", " ", q)
        q = re.sub(r"\bdoi\s*:?\s*10\.\S+|10\.\d{4,9}/\S+", " ", q, flags=re.I)
        q = re.sub(r"arxiv\S*\s*:?\s*\S*\d", " ", q, flags=re.I)
    q = re.sub(r"\s+", " ", q).strip()
    return q[:300]


class CrossrefResolver(Resolver):
    name = "crossref"
    kinds = ("doi",)
    searchable = True

    def __init__(self, http):
        super().__init__(http)
        self._memo: dict[str, Record] = {}

    def prefetch(self, kind: str, values: list[str]) -> None:
        dois = sorted({v for v in values if v and "," not in v and v not in self._memo})
        for i in range(0, len(dois), BATCH):
            chunk = dois[i:i + BATCH]
            flt = ",".join(f"doi:{d}" for d in chunk)
            try:
                resp = self.http.get(API, params={"filter": flt, "rows": len(chunk), "select": SELECT},
                                     ns="crossref", rate_key="api.crossref.org", interval=INTERVAL)
            except Exception:
                continue  # individual lookups will retry and report errors
            if resp.status != 200:
                continue
            for it in resp.json().get("message", {}).get("items", []):
                rec = parse_item(it)
                if rec.ids.get("doi"):
                    self._memo[rec.ids["doi"]] = rec

    def lookup(self, kind: str, value: str) -> Lookup:
        doi = value.lower()
        if doi in self._memo:
            return Lookup("found", [self._memo[doi]], query=doi)

        def run() -> Lookup:
            resp = self.http.get(f"{API}/{quote(doi, safe='')}", ns="crossref", rate_key="api.crossref.org",
                                 interval=INTERVAL)
            if resp.status == 404:
                return Lookup("not_found", query=doi, note="not registered with Crossref")
            if resp.status != 200:
                return Lookup("error", query=doi, note=f"HTTP {resp.status}")
            rec = parse_item(resp.json()["message"])
            self._memo[doi] = rec
            return Lookup("found", [rec], query=doi)

        return self._guard(doi, run)

    def search(self, ref: Reference) -> Lookup:
        q = compose_query(ref)
        if len(q) < 12:
            return Lookup("skipped", query=q, note="not enough text to search")

        def run() -> Lookup:
            resp = self.http.get(API, params={"query.bibliographic": q, "rows": 5, "select": SELECT + ",score"},
                                 ns="crossref", rate_key="api.crossref.org", interval=INTERVAL)
            if resp.status != 200:
                return Lookup("error", query=q, note=f"HTTP {resp.status}")
            items = resp.json().get("message", {}).get("items", [])
            recs = [parse_item(it) for it in items]
            return Lookup("found" if recs else "not_found", recs, query=q)

        return self._guard(q, run)
