# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pluggable resolvers. Each has its own rate limit (keyed by host) and cache namespace."""

from __future__ import annotations

from ..http import Http
from .ads import AdsResolver, load_token
from .arxiv import ArxivResolver
from .base import Lookup, Resolver
from .crossref import CrossrefResolver
from .doiorg import DoiOrgResolver
from .openalex import OpenAlexResolver
from .pos import PosResolver

ALL = ("arxiv", "crossref", "doi.org", "openalex", "ads", "pos")


def build_resolvers(http: Http, enabled: set[str] | None = None, ads_token: str | None = None) -> dict[str, Resolver]:
    """Instantiate resolvers. ADS is included only when a token is found."""
    enabled = set(ALL) if enabled is None else set(enabled)
    out: dict[str, Resolver] = {}
    if "arxiv" in enabled:
        out["arxiv"] = ArxivResolver(http)
    if "crossref" in enabled:
        out["crossref"] = CrossrefResolver(http)
    if "doi.org" in enabled:
        out["doi.org"] = DoiOrgResolver(http)
    if "openalex" in enabled:
        out["openalex"] = OpenAlexResolver(http)
    if "ads" in enabled:
        ads = AdsResolver(http, token=ads_token)
        if ads.available():
            out["ads"] = ads
    if "pos" in enabled:
        out["pos"] = PosResolver(http)
    return out


__all__ = ["ALL", "Lookup", "Resolver", "build_resolvers", "load_token", "AdsResolver", "ArxivResolver",
           "CrossrefResolver", "DoiOrgResolver", "OpenAlexResolver", "PosResolver"]
