# SPDX-License-Identifier: AGPL-3.0-or-later
"""HTTP secret handling and decision logic with stub resolvers. No network."""

import httpx
import pytest

from citecheck.checker import Checker
from citecheck.http import Cache, Http, OfflineMiss, strip_secrets
from citecheck.models import Record, Reference, Verdict
from citecheck.resolvers.ads import AdsResolver
from citecheck.resolvers.base import Lookup, Resolver

# ------------------------------------------------------------------ HTTP / secrets


def test_strip_secrets_and_cache_key():
    u1 = "https://api.openalex.org/works?filter=x&mailto=someone%40example.org&api_key=SECRET"
    u2 = "https://api.openalex.org/works?filter=x"
    assert strip_secrets(u1) == u2
    assert Cache.make_key(u1, None) == Cache.make_key(u2, None)


def test_token_never_written_to_cache(tmp_path):
    token = "tok-SHOULD-NOT-LEAK-12345"
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"response": {"docs": []}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = Http(Cache(tmp_path), client=client)
    ads = AdsResolver(http, token=token)
    lk = ads.lookup("doi", "10.1000/xyz")
    assert lk.status == "not_found"
    assert seen["auth"] == f"Bearer {token}"
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert token not in f.read_text(errors="replace")


def test_offline_mode_raises_on_miss(tmp_path):
    http = Http(Cache(tmp_path), offline=True)
    with pytest.raises(OfflineMiss):
        http.get("https://api.crossref.org/works/10.1000/none", ns="crossref")


def test_mailto_only_from_env(monkeypatch):
    http = Http(None)
    assert "mailto" not in http.client.headers["User-Agent"]
    monkeypatch.setenv("CITECHECK_MAILTO", "me@example.org")
    http2 = Http(None)
    assert "mailto:me@example.org" in http2.client.headers["User-Agent"]


# ------------------------------------------------------------------ stub resolvers


class Stub(Resolver):
    def __init__(self, name, lookups=None, searches=None, kinds=("doi",), searchable=False):
        super().__init__(http=None)
        self.name = name
        self.kinds = kinds
        self.searchable = searchable
        self._lookups = lookups or {}
        self._searches = searches or []
        self.calls = []

    def lookup(self, kind, value):
        self.calls.append((kind, value))
        return self._lookups.get(value, Lookup("not_found", query=value))

    def search(self, ref):
        self.calls.append(("search", ref.index))
        return Lookup("found" if self._searches else "not_found", list(self._searches), query="q")


ZENODO = Record(source="doi.org", ids={"doi": "10.5281/zenodo.4724125"}, title="TensorFlow",
                authors=["TensorFlow Developers"], family_names=["TensorFlow Developers"], year=2021,
                registry="DataCite", type="software")


def test_datacite_only_doi_is_verified_not_unresolved():
    """A DOI missing from Crossref but present in another registry must not be flagged."""
    ref = Reference(index=1, raw="TensorFlow Developers, 2021, TensorFlow, Zenodo", source_format="text",
                    title="TensorFlow", authors=["TensorFlow Developers"], year=2021, doi="10.5281/zenodo.4724125")
    res = {"crossref": Stub("crossref"),
           "doi.org": Stub("doi.org", {"10.5281/zenodo.4724125": Lookup("found", [ZENODO], query="z")})}
    r = Checker(res).check(ref)
    assert r.verdict == Verdict.VERIFIED
    assert r.matched_record.registry == "DataCite"


def test_resolver_errors_give_incomplete_not_fabricated():
    ref = Reference(index=1, raw="Someone A., 2020, ApJ, 900, 1", source_format="text", authors=["Someone"],
                    year=2020, journal="ApJ", volume="900", page="1", doi="10.3847/1538-4357/abc123")
    err = Lookup("error", query="x", note="HTTP 503")
    res = {"crossref": Stub("crossref", {"10.3847/1538-4357/abc123": err}),
           "doi.org": Stub("doi.org", {"10.3847/1538-4357/abc123": err})}
    r = Checker(res).check(ref)
    assert r.verdict == Verdict.UNRESOLVED
    assert r.incomplete
    assert r.confidence < 0.5


def test_private_communication_not_checkable():
    ref = Reference(index=1, raw="J. Smith, private communication (2021)", source_format="text", authors=["Smith"],
                    year=2021, flags=["private_communication"])
    r = Checker({}).check(ref)
    assert r.verdict == Verdict.NOT_CHECKABLE


def test_id_points_elsewhere_but_real_work_found_by_search():
    wrong = Record(source="crossref", ids={"doi": "10.1000/other"}, title="An unrelated paper on soil chemistry",
                   authors=["Nguyen, T."], family_names=["Nguyen"], year=2011, volume="3", page="99")
    right = Record(source="crossref", ids={"doi": "10.1000/right"},
                   title="Measurements of the Hubble Constant: Tensions in Perspective",
                   authors=["Freedman, W."], family_names=["Freedman"], year=2021, volume="919", page="16")
    ref = Reference(index=1, raw="x", source_format="bibtex", title="Measurements of the Hubble Constant: "
                    "Tensions in Perspective", title_reliable=True, authors=["Freedman"], year=2021,
                    volume="919", page="16", doi="10.1000/other")
    res = {"crossref": Stub("crossref", {"10.1000/other": Lookup("found", [wrong])}, [right], searchable=True)}
    r = Checker(res, arxiv_search=False).check(ref)
    assert r.verdict == Verdict.ID_MISMATCH_REAL_REF
    assert r.corrected_ids == {"doi": "10.1000/right"}


def test_stale_ads_bibcode_is_not_held_against_a_good_arxiv_id():
    """mnras .bbl files link every entry to ADS; preprint bibcodes go stale once merged."""
    rec = Record(source="datacite", ids={"arxiv": "2308.08540"}, title="Most of the photons that reionized",
                 authors=["Atek, Hakim"], family_names=["Atek"], year=2023)
    ref = Reference(index=1, raw="Atek H., et al., 2023, arXiv e-prints, p. arXiv:2308.08540", source_format="bbl",
                    authors=["Atek"], year=2023, arxiv="2308.08540", bibcode="2023arXiv230808540A")
    ads = Stub("ads", {}, kinds=("bibcode",))
    res = {"arxiv": Stub("arxiv", {"2308.08540": Lookup("found", [rec])}, kinds=("arxiv",)), "ads": ads}
    r = Checker(res, arxiv_search=False).check(ref)
    assert r.verdict == Verdict.VERIFIED
    assert ("bibcode", "2023arXiv230808540A") not in ads.calls


def test_metadata_mismatch_when_no_alternative():
    wrong = Record(source="crossref", ids={"doi": "10.1000/other"}, title="An unrelated paper on soil chemistry",
                   authors=["Nguyen, T."], family_names=["Nguyen"], year=2011, volume="3", page="99")
    ref = Reference(index=1, raw="x", source_format="bibtex", title="Dark halo triaxiality from tidal streams",
                    title_reliable=True, authors=["Hartwell"], year=2023, volume="948", page="112",
                    doi="10.1000/other")
    res = {"crossref": Stub("crossref", {"10.1000/other": Lookup("found", [wrong])}, [], searchable=True)}
    r = Checker(res, arxiv_search=False).check(ref)
    assert r.verdict == Verdict.METADATA_MISMATCH
