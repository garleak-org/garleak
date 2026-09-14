# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proceedings of Science (pos.sissa.it).

Some PoS DOIs (10.22323/1.<volume>.<number>) are not registered with doi.org even though
the contribution is online at pos.sissa.it/<volume>/<number>/. A PoS reference whose DOI
fails must therefore be checked on the PoS site before anything is concluded.
"""

from __future__ import annotations

import html
import re

from ..models import Record
from .base import Lookup, Resolver

INTERVAL = 1.0


def _meta(page: str, name: str) -> list[str]:
    pat = re.compile(r'<meta\s+name="' + re.escape(name) + r'"\s+content="([^"]*)"', re.I)
    return [html.unescape(m) for m in pat.findall(page)]


class PosResolver(Resolver):
    name = "pos"
    kinds = ("pos",)

    def lookup(self, kind: str, value: str) -> Lookup:
        """value is '<volume>/<number>', e.g. '444/001'."""
        vol, num = value.split("/", 1)
        url = f"https://pos.sissa.it/{vol}/{num.zfill(3)}/"

        def run() -> Lookup:
            resp = self.http.get(url, ns="pos", rate_key="pos.sissa.it", interval=INTERVAL)
            if resp.status == 404:
                return Lookup("not_found", query=url)
            if resp.status != 200:
                return Lookup("error", query=url, note=f"HTTP {resp.status}")
            page = resp.text
            titles = _meta(page, "citation_title")
            if not titles or "Contribution not available" in page:
                return Lookup("not_found", query=url, note="PoS page says the contribution is not available")
            authors = _meta(page, "citation_author") or _meta(page, "dcterms.creator")
            fams = [a.split(",")[0].strip() for a in authors]
            date = (_meta(page, "citation_publication_date") or _meta(page, "citation_date")
                    or _meta(page, "dcterms.date") or [""])[0]
            ym = re.search(r"(19|20)\d\d", date)
            conf = (_meta(page, "citation_conference_title") or [None])[0]
            rec = Record(source="pos", ids={"pos": f"{vol}/{num.zfill(3)}", "url": url}, title=titles[0],
                         authors=authors, family_names=fams, year=int(ym.group(0)) if ym else None,
                         container=conf, volume=vol, page=num.zfill(3), type="proceedings-article",
                         registry="PoS")
            return Lookup("found", [rec], query=url)

        return self._guard(url, run)
