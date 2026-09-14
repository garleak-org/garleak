# SPDX-License-Identifier: AGPL-3.0-or-later
"""arXiv identifiers: the arXiv API (batched, 1 request per 3 s), with DataCite as a fallback.

arXiv registers a DataCite DOI (10.48550/arXiv.<id>) for every paper, so DataCite is an
independent second source. An ID counts as missing only when both sources lack it.
DataCite records also carry the journal DOI of the published version when the
authors reported one, which helps correct a wrong journal DOI.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..http import FetchError, OfflineMiss
from ..ids import arxiv_well_formed, normalize_arxiv
from ..models import Record, Reference
from ..textutil import content_tokens
from .base import Lookup, Resolver

ARXIV_API = "https://export.arxiv.org/api/query"
DATACITE_API = "https://api.datacite.org/dois"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom",
      "os": "http://a9.com/-/spec/opensearch/1.1/"}
BATCH = 40


def _family(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    if ":" in name:  # "Planck Collaboration: N. Aghanim"
        name = name.split(":", 1)[1].strip() or name
    return name.split()[-1] if name else name


def parse_atom(xml_text: str) -> dict[str, Record]:
    out: dict[str, Record] = {}
    root = ET.fromstring(xml_text)
    for e in root.findall("a:entry", NS):
        id_url = (e.findtext("a:id", default="", namespaces=NS) or "").strip()
        if "api/errors" in id_url or not id_url:
            continue
        aid = normalize_arxiv(id_url)
        title = re.sub(r"\s+", " ", e.findtext("a:title", default="", namespaces=NS) or "").strip()
        if not aid or title.lower() == "error":
            continue
        authors = [re.sub(r"\s+", " ", a.findtext("a:name", default="", namespaces=NS)).strip()
                   for a in e.findall("a:author", NS)]
        published = e.findtext("a:published", default="", namespaces=NS) or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        rec = Record(source="arxiv", ids={"arxiv": aid}, title=title, authors=authors,
                     family_names=[_family(a) for a in authors if a], year=year, container="arXiv",
                     type="preprint", registry="arXiv")
        doi = e.findtext("arxiv:doi", default="", namespaces=NS)
        if doi:
            rec.related_ids["doi"] = doi.strip().lower()
        jref = e.findtext("arxiv:journal_ref", default="", namespaces=NS)
        if jref:
            rec.related_ids["journal_ref"] = re.sub(r"\s+", " ", jref).strip()
        out[aid] = rec
    return out


def parse_datacite(item: dict) -> Record | None:
    a = item.get("attributes", {})
    doi = (a.get("doi") or item.get("id") or "").lower()
    m = re.match(r"10\.48550/arxiv\.(.+)$", doi)
    aid = normalize_arxiv(m.group(1)) if m else None
    titles = a.get("titles") or []
    title = titles[0].get("title") if titles else None
    creators = a.get("creators") or []
    authors, fams = [], []
    for c in creators:
        nm = c.get("name") or " ".join(x for x in (c.get("givenName"), c.get("familyName")) if x)
        authors.append(nm)
        fams.append(c.get("familyName") or (nm.split(",")[0] if "," in nm else (nm.split() or [""])[-1]))
    year = a.get("publicationYear")
    rec = Record(source="datacite", ids={"doi": doi} | ({"arxiv": aid} if aid else {}), title=title,
                 authors=authors, family_names=fams, year=int(year) if year else None,
                 container="arXiv" if aid else a.get("publisher"), type="preprint" if aid else None,
                 registry="DataCite")
    for rel in a.get("relatedIdentifiers") or []:
        if rel.get("relationType") == "IsVersionOf" and rel.get("relatedIdentifierType") == "DOI":
            rec.related_ids["doi"] = rel.get("relatedIdentifier", "").lower()
    return rec


class ArxivResolver(Resolver):
    name = "arxiv"
    kinds = ("arxiv",)
    searchable = True

    def __init__(self, http, datacite_fallback: bool = True):
        super().__init__(http)
        self.datacite_fallback = datacite_fallback
        self._memo: dict[str, Lookup] = {}
        # Circuit breaker: once export.arxiv.org rate-limits us, stop asking it for this run
        # and use DataCite instead. Hammering a throttled API is impolite and slow.
        self._api_down: str | None = None

    # ---- batching
    def prefetch(self, kind: str, values: list[str]) -> None:
        ids = sorted({v for v in values if v and arxiv_well_formed(v)} - set(self._memo))
        for i in range(0, len(ids), BATCH):
            self._batch(ids[i:i + BATCH])

    def _batch(self, ids: list[str]) -> None:
        query = ",".join(ids)
        found: dict[str, Record] = {}
        arxiv_status = "ok"
        if self._api_down and not self.http.offline:
            arxiv_status = f"skipped ({self._api_down})"
        else:
            try:
                resp = self.http.get(ARXIV_API, params={"id_list": query, "max_results": len(ids)}, ns="arxiv",
                                     rate_key="arxiv", interval=3.0, max_retries=0, timeout=15.0)
                if resp.status == 200:
                    found = parse_atom(resp.text)
                else:
                    arxiv_status = f"HTTP {resp.status}"
            except OfflineMiss:
                arxiv_status = "offline_miss"
            except (FetchError, ET.ParseError) as e:
                arxiv_status = f"error ({str(e).split(' after')[0].split(':')[0]})"
                if isinstance(e, FetchError):
                    self._api_down = "arXiv API rate-limited or unreachable earlier in this run"
        missing = [a for a in ids if a not in found]
        dc: dict[str, Record] = {}
        dc_status = "skipped"
        if missing and self.datacite_fallback:
            dc, dc_status = self._datacite_batch(missing)
        for aid in ids:
            if aid in found:
                self._memo[aid] = Lookup("found", [found[aid]], query=aid)
            elif aid in dc:
                self._memo[aid] = Lookup("found", [dc[aid]], query=aid,
                                         note=f"arXiv API: {arxiv_status}; found in DataCite")
            elif arxiv_status == "ok" and dc_status in ("ok", "skipped"):
                self._memo[aid] = Lookup("not_found", query=aid,
                                         note="absent from the arXiv API" + (" and DataCite" if dc_status == "ok" else ""))
            elif dc_status == "ok" and arxiv_status != "ok":
                self._memo[aid] = Lookup("not_found", query=aid,
                                         note=f"absent from DataCite; arXiv API unavailable ({arxiv_status})")
            else:
                st = "offline_miss" if "offline" in (arxiv_status + dc_status) else "error"
                self._memo[aid] = Lookup(st, query=aid, note=f"arXiv API: {arxiv_status}; DataCite: {dc_status}")

    def _datacite_batch(self, ids: list[str]) -> tuple[dict[str, Record], str]:
        q = " OR ".join(f'"10.48550/arxiv.{a}"' for a in ids)
        try:
            resp = self.http.get(DATACITE_API, params={"query": f"id:({q})", "page[size]": 100,
                                                       "fields[dois]": "doi,titles,creators,publicationYear,"
                                                                       "relatedIdentifiers,publisher"},
                                 ns="datacite", rate_key="api.datacite.org", interval=0.5)
        except OfflineMiss:
            return {}, "offline_miss"
        except FetchError as e:
            return {}, f"error ({str(e).split(' after')[0].split(':')[0]})"
        if resp.status != 200:
            return {}, f"HTTP {resp.status}"
        out = {}
        for item in resp.json().get("data", []):
            rec = parse_datacite(item)
            if rec and rec.ids.get("arxiv"):
                out[rec.ids["arxiv"]] = rec
        return out, "ok"

    def lookup(self, kind: str, value: str) -> Lookup:
        aid = normalize_arxiv(value) or value
        if not arxiv_well_formed(aid):
            return Lookup("not_found", query=value, note="malformed arXiv identifier (does not follow arXiv numbering)")
        if aid not in self._memo:
            self._batch([aid])
        return self._memo[aid]

    # ---- metadata search (used as a last resort; each call costs 3 s)
    def search(self, ref: Reference) -> Lookup:
        if not ref.title:
            return Lookup("skipped", note="arXiv search needs a title")
        words = [w for w in content_tokens(ref.title) if not w.isdigit()][:8]
        if len(words) < 3:
            return Lookup("skipped", note="title too short to search")
        q = " AND ".join(f"ti:{w}" for w in words)
        if ref.authors:
            fam = re.sub(r"[^A-Za-z\-]", "", ref.authors[0])
            if fam:
                q += f" AND au:{fam}"

        if self._api_down and not self.http.offline:
            return Lookup("skipped", query=q, note=self._api_down)

        def run() -> Lookup:
            resp = self.http.get(ARXIV_API, params={"search_query": q, "max_results": 5}, ns="arxiv",
                                 rate_key="arxiv", interval=3.0, max_retries=0, timeout=15.0)
            if resp.status != 200:
                return Lookup("error", query=q, note=f"HTTP {resp.status}")
            recs = list(parse_atom(resp.text).values())
            return Lookup("found" if recs else "not_found", recs, query=q)

        lk = self._guard(q, run)
        if lk.status == "error":
            self._api_down = "arXiv API rate-limited or unreachable earlier in this run"
        return lk
