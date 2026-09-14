# SPDX-License-Identifier: AGPL-3.0-or-later
"""Live tests. Skipped unless run with --network or CITECHECK_NETWORK_TESTS=1."""

import pytest

from citecheck.checker import Checker
from citecheck.http import Cache, Http
from citecheck.models import Verdict
from citecheck.parsers import load_arxiv, load_path
from citecheck.resolvers import build_resolvers

from .conftest import FIXTURES

pytestmark = pytest.mark.network


@pytest.fixture
def http(tmp_path):
    h = Http(Cache(tmp_path / "cache"))
    yield h
    h.close()


def test_live_crossref_and_handle(http):
    res = build_resolvers(http, {"crossref", "doi.org"})
    assert res["crossref"].lookup("doi", "10.3847/1538-4357/ac0e95").status == "found"
    assert res["crossref"].lookup("doi", "10.3847/1538-4357/ac082c").status == "not_found"
    assert res["doi.org"].lookup("doi", "10.5281/zenodo.4724125").status == "found"


def test_live_regression_subset(http):
    res = build_resolvers(http, {"arxiv", "crossref", "doi.org", "openalex", "pos"})
    loaded = load_path(FIXTURES / "arxiv_2509.09678_subset.bbl")
    results = {r.reference.key: r for r in Checker(res).check_all(loaded.refs)}
    r = results["Freedman:2021ahq"]
    assert r.verdict == Verdict.ID_MISMATCH_REAL_REF
    assert r.corrected_ids.get("doi") == "10.3847/1538-4357/ac0e95"


def test_live_arxiv_eprint_fetch(http):
    loaded = load_arxiv("2509.09678", http)
    assert loaded.kind.startswith("arxiv-latex")
    assert len(loaded.refs) > 50
