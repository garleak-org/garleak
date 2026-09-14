# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end checks replayed from recorded HTTP fixtures (tests/fixtures/cache). No network.

Re-record with `python tests/record_fixtures.py` if resolver queries change.
"""

import datetime as dt
import json

import jsonschema
import pytest

from citecheck.checker import Checker
from citecheck.cli import main as cli_main
from citecheck.http import Cache, Http, Response
from citecheck.models import Verdict
from citecheck.parsers import load_arxiv, load_path
from citecheck.report import build_report
from citecheck.resolvers import ALL, build_resolvers

from .conftest import FIXTURE_CACHE, FIXTURES, SCHEMA

pytestmark = pytest.mark.skipif(not FIXTURE_CACHE.exists(), reason="fixture cache not recorded")

FLAGGED = {Verdict.UNRESOLVED, Verdict.METADATA_MISMATCH}


def run_offline(name: str, ads: bool = True):
    http = Http(Cache(FIXTURE_CACHE), offline=True)
    enabled = set(ALL) if ads else set(ALL) - {"ads"}
    # A dummy token makes the ADS resolver available; offline mode never sends it.
    res = build_resolvers(http, enabled, ads_token="offline-dummy-token" if ads else None)
    loaded = load_path(FIXTURES / name)
    results = Checker(res).check_all(loaded.refs)
    now = dt.datetime.now(dt.timezone.utc)
    report = build_report(results, loaded.info(), {"offline": True, "resolvers": sorted(res)}, http.stats, now, now)
    return results, report


def by_key(results):
    return {r.reference.key: r for r in results}


@pytest.mark.parametrize("ads", [True, False])
def test_regression_2509_09678_wrong_suffix_dois(ads):
    """arXiv:2509.09678 prints wrong DOI suffixes on real references. Real refs, wrong IDs."""
    results, report = run_offline("arxiv_2509.09678_subset.bbl", ads=ads)
    k = by_key(results)
    expect = {
        "Freedman:2021ahq": "10.3847/1538-4357/ac0e95",  # printed: ac082c
        "Scolnic:2023pga": "10.3847/2041-8213/ace978",   # printed: ace280
        "Riess:2021jrx": "10.3847/2041-8213/ac5c5b",     # printed: ac361f
    }
    for key, true_doi in expect.items():
        r = k[key]
        assert r.verdict == Verdict.ID_MISMATCH_REAL_REF, (key, r.verdict, r.reason)
        assert r.corrected_ids.get("doi") == true_doi, (key, r.corrected_ids)
        assert not r.incomplete
    for r in results:
        assert r.verdict not in FLAGGED, (r.reference.key, r.verdict, r.reason)
    assert report["summary"]["prescreen"]["status"] == "pass"


@pytest.mark.parametrize("ads", [True, False])
def test_fabricated_references_are_never_verified(ads):
    results, _ = run_offline("fabricated.bib", ads=ads)
    for r in results:
        assert r.verdict in FLAGGED, (r.reference.key, r.verdict, r.reason)
        assert not r.incomplete, (r.reference.key, r.reason)


@pytest.mark.parametrize("ads", [True, False])
def test_real_refs_audit_failure_classes(ads):
    results, _ = run_offline("real_refs.bib", ads=ads)
    k = by_key(results)
    r = k["GarrisonKimmel2013"]
    assert r.verdict == Verdict.ID_MISMATCH_REAL_REF and r.corrected_ids["doi"] == "10.1093/mnras/stt984"
    r = k["tensorflow"]
    assert r.verdict == Verdict.VERIFIED and r.matched_record.registry == "DataCite"
    r = k["Zou2026"]
    assert r.verdict == Verdict.ID_MISMATCH_REAL_REF, r.reason
    assert r.corrected_ids.get("url", "").startswith("https://pos.sissa.it/544/001")
    assert k["Freedman2021noid"].verdict == Verdict.VERIFIED
    assert k["Rubin2023"].verdict == Verdict.VERIFIED
    assert k["Smith_pc"].verdict == Verdict.NOT_CHECKABLE
    for r in results:
        assert r.verdict not in FLAGGED, (r.reference.key, r.verdict, r.reason)


def test_plaintext_mnras_style_list():
    results, _ = run_offline("refs_mnras_style.txt", ads=True)
    verdicts = [r.verdict for r in results]
    assert verdicts[:4] == [Verdict.VERIFIED] * 4, [(r.reference.raw, r.verdict, r.reason) for r in results]
    assert verdicts[4] in FLAGGED  # invented authors at a real volume/page


@pytest.mark.parametrize("name", ["arxiv_2509.09678_subset.bbl", "fabricated.bib", "real_refs.bib"])
def test_reports_validate_against_schema(name):
    _, report = run_offline(name)
    schema = json.loads(SCHEMA.read_text())
    jsonschema.validate(json.loads(json.dumps(report)), schema)
    assert report["summary"]["prescreen"]["claim_support_checked"] is False
    assert "does not check whether a cited work supports" in report["disclaimer"]


def test_cli_offline_json_and_exit_codes(tmp_path, capsys):
    out = tmp_path / "r.json"
    code = cli_main([str(FIXTURES / "fabricated.bib"), "--offline", "--cache-dir", str(FIXTURE_CACHE),
                     "--no-ads", "--json", str(out)])
    assert code == 1
    table = capsys.readouterr().out
    assert "does not check whether a cited work supports" in table
    data = json.loads(out.read_text())
    assert data["summary"]["counts"]["verified"] == 0
    code = cli_main([str(FIXTURES / "real_refs.bib"), "--offline", "--cache-dir", str(FIXTURE_CACHE),
                     "--no-ads", "-q"])
    assert code == 0


def test_arxiv_bundle_offline(tmp_path):
    """--arxiv reads a cached bibliography bundle when offline."""
    cache = Cache(tmp_path)
    bbl = (FIXTURES / "arxiv_2509.09678_subset.bbl").read_text()
    from citecheck.parsers.sources import _bundle_key
    cache.put("arxiv_bundle", _bundle_key("2509.09678"),
              Response(200, "https://arxiv.org/e-print/2509.09678", "application/json",
                       json.dumps({"main.bbl": bbl}).encode()))
    loaded = load_arxiv("arXiv:2509.09678", Http(cache, offline=True))
    assert loaded.arxiv_id == "2509.09678"
    assert loaded.kind == "arxiv-latex-bbl"
    assert len(loaded.refs) == 10
