# SPDX-License-Identifier: AGPL-3.0-or-later
"""doi.org: the global DOI handle system, the registration-agency lookup, and content negotiation.

This is the step that keeps real DOIs from being called unresolvable. Crossref holds only
Crossref DOIs. DataCite (arXiv, Zenodo, data archives), mEDRA, JaLC, KISTI, CNKI and the
other agencies register DOIs that Crossref has never seen. In the llm-in-astro-ph audit,
every one of the 123 DOIs missing from Crossref was real and resolved here.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

from ..models import Record
from .base import Lookup, Resolver

HANDLE_API = "https://doi.org/api/handles/"
RA_API = "https://doi.org/ra/"
CSL = "application/vnd.citationstyles.csl+json"
INTERVAL = 0.3


def parse_csl(d: dict, registry: str | None) -> Record:
    title = d.get("title")
    if isinstance(title, list):
        title = title[0] if title else None
    authors, fams = [], []
    for a in d.get("author") or []:
        if a.get("family"):
            authors.append(", ".join(x for x in (a.get("family"), a.get("given")) if x))
            fams.append(a["family"])
        elif a.get("literal") or a.get("name"):
            nm = a.get("literal") or a.get("name")
            authors.append(nm)
            fams.append(nm.split(",")[0] if "," in nm else nm.split()[-1])
    year = None
    for k in ("issued", "published-print", "published-online", "created"):
        dp = (d.get(k) or {}).get("date-parts") or [[None]]
        if dp and dp[0] and dp[0][0]:
            try:
                year = int(dp[0][0])
            except (TypeError, ValueError):
                year = None
            break
    container = d.get("container-title")
    if isinstance(container, list):
        container = container[0] if container else None
    page = d.get("page") or d.get("number")
    if page:
        page = re.split(r"[-–]", str(page))[0].strip()
    return Record(source="doi.org", ids={"doi": str(d.get("DOI", "")).lower()},
                  title=re.sub(r"\s+", " ", title).strip() if isinstance(title, str) else None,
                  authors=authors, family_names=fams, year=year,
                  container=container or d.get("publisher"), volume=str(d["volume"]) if d.get("volume") else None,
                  page=page, type=d.get("type"), registry=registry,
                  issue=str(d["issue"]) if d.get("issue") else None)


class DoiOrgResolver(Resolver):
    name = "doi.org"
    kinds = ("doi",)

    def handle_exists(self, doi: str) -> Lookup:
        def run() -> Lookup:
            resp = self.http.get(HANDLE_API + quote(doi, safe="/"), ns="doiorg", rate_key="doi.org", interval=INTERVAL)
            try:
                code = resp.json().get("responseCode")
            except ValueError:
                return Lookup("error", query=doi, note=f"HTTP {resp.status}")
            if code == 1:
                return Lookup("found", query=doi, note="DOI handle exists")
            if code == 100 or resp.status == 404:
                return Lookup("not_found", query=doi, note="no such DOI in the global handle system")
            return Lookup("error", query=doi, note=f"handle responseCode {code}")

        return self._guard(doi, run)

    def registry(self, doi: str) -> str | None:
        try:
            resp = self.http.get(RA_API + quote(doi, safe="/"), ns="doiorg", rate_key="doi.org", interval=INTERVAL)
            data = resp.json()
            if isinstance(data, list) and data and data[0].get("RA"):
                ra = data[0]["RA"]
                return None if ra.lower().startswith("doi does not exist") else ra
        except Exception:
            return None
        return None

    def lookup(self, kind: str, value: str) -> Lookup:
        doi = value.lower()
        h = self.handle_exists(doi)
        if h.status != "found":
            return h
        ra = self.registry(doi)

        def run() -> Lookup:
            resp = self.http.get(f"https://doi.org/{quote(doi, safe='/')}", headers={"Accept": CSL}, ns="doiorg_csl",
                                 rate_key="doi.org", interval=INTERVAL)
            if resp.status == 200 and "json" in resp.content_type:
                try:
                    rec = parse_csl(json.loads(resp.text), ra)
                except ValueError:
                    rec = None
                if rec is not None:
                    if not rec.ids.get("doi"):
                        rec.ids["doi"] = doi
                    return Lookup("found", [rec], query=doi, note=f"registered with {ra or 'an agency other than Crossref'}")
            bare = Record(source="doi.org", ids={"doi": doi}, registry=ra)
            return Lookup("found", [bare], query=doi,
                          note=f"DOI exists ({ra or 'agency unknown'}); no machine-readable metadata returned")

        return self._guard(doi, run)
