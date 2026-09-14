# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenAlex: free, keyless DOI lookup plus metadata search by volume/page and by title.

Optional environment variables: CITECHECK_MAILTO (polite pool) and OPENALEX_API_KEY.
Both travel as query parameters that citecheck.http strips before caching or logging.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote

from ..models import Record, Reference
from ..textutil import content_tokens
from .base import Lookup, Resolver

API = "https://api.openalex.org/works"
SELECT = "id,doi,title,publication_year,authorships,biblio,primary_location,type,ids"
INTERVAL = 0.2


def parse_work(w: dict) -> Record:
    authors = []
    fams = []
    for a in w.get("authorships") or []:
        nm = (a.get("author") or {}).get("display_name") or a.get("raw_author_name") or ""
        if nm:
            authors.append(nm)
            fams.append(nm.split()[-1])
    doi = (w.get("doi") or "").lower().replace("https://doi.org/", "")
    ids = {"openalex": (w.get("id") or "").replace("https://openalex.org/", "")}
    if doi:
        ids["doi"] = doi
    b = w.get("biblio") or {}
    src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    return Record(source="openalex", ids=ids, title=w.get("title"), authors=authors, family_names=fams,
                  year=w.get("publication_year"), container=src, volume=b.get("volume"), page=b.get("first_page"),
                  type=w.get("type"), registry=None, issue=b.get("issue"))


def _clean_filter_value(s: str) -> str:
    return re.sub(r"[,|:&!<>()\"']", " ", s).strip()


class OpenAlexResolver(Resolver):
    name = "openalex"
    kinds = ("doi",)
    searchable = True

    def __init__(self, http):
        super().__init__(http)
        # OpenAlex throttles anonymous search under load (HTTP 429, Retry-After ~30 s).
        # After the first refusal, skip further searches this run instead of waiting.
        self._search_down: str | None = None

    def _params(self, extra: dict) -> dict:
        p = dict(extra)
        mailto = os.environ.get("CITECHECK_MAILTO", "").strip()
        if mailto:
            p["mailto"] = mailto
        key = os.environ.get("OPENALEX_API_KEY", "").strip()
        if key:
            p["api_key"] = key
        return p

    def lookup(self, kind: str, value: str) -> Lookup:
        doi = value.lower()

        def run() -> Lookup:
            resp = self.http.get(f"{API}/doi:{quote(doi, safe='/')}", params=self._params({"select": SELECT}),
                                 ns="openalex", rate_key="api.openalex.org", interval=INTERVAL, max_retries=1)
            if resp.status == 404:
                return Lookup("not_found", query=doi)
            if resp.status != 200:
                return Lookup("error", query=doi, note=f"HTTP {resp.status}")
            return Lookup("found", [parse_work(resp.json())], query=doi)

        return self._guard(doi, run)

    def search(self, ref: Reference) -> Lookup:
        recs: list[Record] = []
        queries = []
        notes = []
        yr = f"{ref.year - 1}-{ref.year + 1}" if ref.year else None
        if ref.volume and ref.page and re.fullmatch(r"[A-Za-z]?\d+", ref.page or "") and ref.year:
            page = re.sub(r"^[A-Za-z]", "", ref.page) if not ref.page[:1].isdigit() else ref.page
            flt = f"biblio.volume:{_clean_filter_value(ref.volume)},biblio.first_page:{ref.page},publication_year:{yr}"
            queries.append(flt)
            if page != ref.page:
                queries.append(f"biblio.volume:{_clean_filter_value(ref.volume)},biblio.first_page:{page},"
                               f"publication_year:{yr}")
        if ref.title:
            words = content_tokens(ref.title)
            if len(words) >= 3:
                flt = f"title.search:{_clean_filter_value(ref.title)[:200]}"
                if yr:
                    flt += f",publication_year:{yr}"
                queries.append(flt)
        if not queries:
            return Lookup("skipped", note="needs volume+page+year or a title")
        # The throttle applies to OpenAlex's full-text search cluster (title.search), not to
        # plain filters such as biblio.volume/biblio.first_page, so only those are skipped.
        if self._search_down and not self.http.offline:
            queries = [q for q in queries if ".search:" not in q]
            if not queries:
                return Lookup("skipped", note=self._search_down)
        status = "not_found"
        for flt in queries:
            lk = self._guard(flt, lambda flt=flt: self._run(flt))
            if lk.status == "error" and ".search:" in flt:
                self._search_down = "OpenAlex title search throttled earlier in this run"
            if lk.status == "found":
                recs.extend(lk.records)
                status = "found"
            elif lk.status in ("error", "offline_miss") and status != "found":
                status = lk.status
                notes.append(lk.note or lk.status)
        return Lookup(status, recs, query=" | ".join(queries), note="; ".join(notes) or None)

    def _run(self, flt: str) -> Lookup:
        resp = self.http.get(API, params=self._params({"filter": flt, "per-page": 8, "select": SELECT}), ns="openalex",
                             rate_key="api.openalex.org", interval=INTERVAL, max_retries=0, timeout=20.0)
        if resp.status != 200:
            return Lookup("error", query=flt, note=f"HTTP {resp.status}")
        recs = [parse_work(w) for w in resp.json().get("results", [])]
        return Lookup("found" if recs else "not_found", recs, query=flt)
