# SPDX-License-Identifier: AGPL-3.0-or-later
"""The automated first pass: near-duplicates, truncation, gated keywords, the calibration
sample and citecheck. It flags and never rejects."""

import json
import sys

import pytest

from garleak_intake import screen

from .intake_support import Arch, answers, long_body, make_issue, run


@pytest.fixture
def arch(tmp_path):
    a = Arch(tmp_path)
    for h in ("alice", "bob"):
        a.account(h)
    return a


def flags(res):
    return {c.id for c in res.flagged}


def test_an_identical_scratch_is_flagged_and_held(arch):
    statement = answers("scratch")["statement"]
    arch.scratch(1, "bob", statement=statement)
    res = run(arch, make_issue("scratch", number=5))
    assert res.status == "held" and "near-duplicate" in flags(res)
    assert "identical to scratch:1" in next(c.detail for c in res.flagged)


def test_near_duplicates_by_shingles():
    text = long_body("x")
    edited = text.replace("number 3 gives", "number 3 still gives")
    m = screen.best_match(text, [("paper:1v1.0", edited), ("paper:2v1.0", "Something else entirely.")], 5)
    assert m.ref == "paper:1v1.0" and not m.exact and m.score >= 0.8
    m = screen.best_match("A different idea about comets and their tails.", [("scratch:1", text)], 3)
    assert m.score < 0.1
    assert screen.best_match(text, [("paper:3v1.0", text.upper())], 5).exact


def test_a_paper_near_an_earlier_one_is_flagged(arch):
    arch.paper(1, "bob", body=long_body())
    res = run(arch, make_issue("paper", number=5))
    assert res.status == "held" and "near-duplicate" in flags(res)


def test_truncation_heuristics(arch):
    cfg = arch.load().config
    assert screen.paper_flags("T", "short", "## A\n\nIt stops mid", cfg)
    body = long_body() + "\n```python\nx = 1\n"
    assert any("code block" in f for f in screen.paper_flags("Title", answers("paper")["abstract"], body, cfg))
    assert screen.paper_flags("Title", answers("paper")["abstract"], long_body(), cfg) == []
    assert screen.scratch_flags("test", "", cfg)
    res = run(arch, make_issue("paper", answers("paper", body="## Results\n\nToo short, and it stops mid"), number=5))
    assert res.status == "held" and "truncated" in flags(res)


def test_gated_keywords_filed_elsewhere_are_flagged(arch):
    body = long_body() + "\nThe dosage for patients in the clinical trial was fixed.\n"
    res = run(arch, make_issue("paper", answers("paper", body=body), number=5))
    assert "gated-content" in flags(res)
    c = next(c for c in res.flagged if c.id == "gated-content")
    assert c.criterion == "admission criterion 3" and c.version.startswith("gated-keywords/")


def test_the_calibration_sample_is_deterministic(arch):
    h = screen.content_hash("x")
    assert screen.calibration_sampled(1, h, 0.05) == screen.calibration_sampled(1, h, 0.05)
    assert not screen.calibration_sampled(1, h, 0.0) and screen.calibration_sampled(1, h, 1.0)
    arch.set("screening.sample_rate", 1.0)
    res = run(arch, make_issue("scratch", number=5))
    assert res.status == "held" and flags(res) == {"calibration-sample"}


def test_bump_flags():
    assert screen.bump_flags("We find 1.2 Gyr.", "We find 1.3 Gyr.", "", "") == ["numbers"]
    assert screen.bump_flags("x $a+b$", "x $a-b$", "@a{}", "@b{}") == ["mathematics", "the reference list"]
    assert screen.bump_flags("Same words.", "Same  words.", "", "") == []


# ---------------------------------------------------------------- citecheck


def fake_citecheck(tmp_path, status="review", flagged=(0,)):
    report = {"schema_version": "1", "tool": {"name": "citecheck", "version": "0.1.0"},
              "summary": {"n_references": 3, "counts": {}, "flagged_indices": list(flagged),
                          "headline": f"{3 - len(flagged)} of 3 references verified",
                          "prescreen": {"status": status, "claim_support_checked": False}}}
    tmp_path.mkdir(parents=True, exist_ok=True)
    exe = tmp_path / "citecheck"
    exe.write_text(f"#!{sys.executable}\nimport json, sys\nout = sys.argv[sys.argv.index('--json') + 1]\n"
                   f"json.dump(json.loads({json.dumps(report)!r}), open(out, 'w'))\n")
    exe.chmod(0o755)
    return exe


def test_citecheck_is_skipped_cleanly_when_missing(arch):
    res = run(arch, make_issue("paper", answers("paper", refs="@article{a, title={A}}"), number=5))
    c = next(c for c in res.checks if c.id == "citations")
    assert c.outcome == "skip" and "not installed" in c.detail and res.status == "held"


def test_citecheck_report_is_read(arch, tmp_path):
    exe = fake_citecheck(tmp_path)
    r = screen.run_citecheck("@article{a, title={A}}", str(exe), 30, 10)
    assert (r.status, r.flagged, r.total, r.version) == ("review", 1, 3, "0.1.0")
    res = run(arch, make_issue("paper", answers("paper", refs="@article{a, title={A}}"), number=5),
              citecheck=str(exe))
    c = next(c for c in res.checks if c.id == "citations")
    assert c.outcome == "flag" and c.version == "citecheck/0.1.0" and "flag:citations" in res.labels()[0]
    assert arch.load().papers[1].versions[0].bib is not None
    ok = fake_citecheck(tmp_path / "ok", status="pass", flagged=())
    assert screen.run_citecheck("@x{}", str(ok), 30, 10).status == "pass"
