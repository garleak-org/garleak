# SPDX-License-Identifier: AGPL-3.0-or-later
"""The issue forms, and parsing what GitHub renders from them."""

import re

import pytest
import yaml

from garleak_archive.ids import VersionNumber
from garleak_archive.loader import load_archive
from garleak_archive.rubrics import RubricSet
from garleak_intake import requests as R
from garleak_intake.forms import FormField, _value, parse_body, render_body
from garleak_intake.labels import ROUTING
from garleak_site.checks import MARKERS

from .conftest import page
from .intake_support import FORMS, REPO, RUBRICS, answers

TEMPLATES = REPO / ".github" / "ISSUE_TEMPLATE"


def build(kind, ans):
    form = FORMS[kind]
    values, missing = parse_body(form, render_body(form, ans))
    f = R.Fields(form, values, missing)
    return R.BUILDERS[kind](f), f


@pytest.mark.parametrize("kind", sorted(ROUTING))
def test_every_form_round_trips(kind):
    req, f = build(kind, answers(kind))
    assert f.problems == [], [(p.field, p.message) for p in f.problems]


def test_typed_values():
    s, _ = build("scratch", answers("scratch"))
    assert (s.category, s.writing, s.analysis, s.license) == ("phys.astro", "W3", None, "CC-BY-4.0")
    assert s.models == [{"name": "gpt-5", "provider": "OpenAI", "version": "2026-06"}]
    p, _ = build("paper", answers("paper", authors="u/alice\n@Bob"))
    assert p.rubric_families == ["computational"] and p.authors == ["alice", "bob"] and p.analysis == "A1"
    v, _ = build("verify", answers("verify"))
    assert (v.paper, v.version, v.tier, v.rubric_id, v.kind) == (1, VersionNumber(1, 0), "T1", "citations", "paper")
    assert len(v.items) == 5 and v.items[0].evidence == ["https://example.org/evidence/cit.T1.exists"]
    n, _ = build("novelty", answers("novelty", closest="Smith 2020 | measures something else"))
    assert n.closest == [{"ref": "Smith 2020", "why_not_close": "measures something else"}] and n.sources == ["ADS", "OpenAlex"]
    vote, _ = build("vote", answers("vote"))
    assert (vote.writing, vote.analysis) == ("W2", None)
    ident, _ = build("identity", answers("identity", orcid="https://orcid.org/0000-0002-1825-0097"))
    assert ident.path == "orcid" and not ident.pseudonymous


def test_no_response_and_unticked_boxes():
    form = FORMS["scratch"]
    ans = answers("scratch", detail="", confirm=[form.field("confirm").options[0]])
    body = render_body(form, ans)
    assert "_No response_" in body and "- [ ] I understand" in body
    values, missing = parse_body(form, body)
    assert values["detail"] == "" and missing == []
    f = R.Fields(form, values, missing)
    R.build_scratch(f)
    assert [p.field for p in f.problems] == ["Confirm"]


def test_a_heading_inside_the_body_stays_in_the_body():
    body_text = "## Method\n\n### Title\n\nA subsection that repeats an earlier label.\n\n### Results\n\nMore text."
    req, f = build("paper", answers("paper", body=body_text))
    assert req.body == body_text and req.title == "A lighter halo from a rotation curve fit"


def test_a_missing_section_is_reported():
    form = FORMS["scratch"]
    body = render_body(form, answers("scratch"))
    body = re.sub(r"### Statement, one line\n\n.*?\n\n", "", body, flags=re.S)
    values, missing = parse_body(form, body)
    f = R.Fields(form, values, missing)
    assert any("missing from the issue" in p.message for p in f.problems)


def test_bad_values_are_named():
    _, f = build("verify", answers("verify", version="paper:1", items="cit.T1.exists | maybe | x"))
    msgs = " ".join(p.message for p in f.problems)
    assert "exact paper version" in msgs and "verdict is pass, fail or na" in msgs
    _, f = build("identity", answers("identity", handle="Not A Handle!"))
    assert any(p.field.startswith("Garleak handle") for p in f.problems)


def test_a_rendered_code_fence_is_unwrapped():
    fld = FormField("x", "X", "textarea", render="yaml")
    assert _value(fld, "```yaml\na: 1\n```") == "a: 1"


def test_each_form_routes_and_says_the_handle_is_public():
    for p in sorted(TEMPLATES.glob("*.yml")):
        if p.name == "config.yml":
            continue
        data = yaml.safe_load(p.read_text())
        routing = [x for x in data["labels"] if x.startswith("intake:")]
        assert len(routing) == 1 and routing[0] in ROUTING.values(), p.name
        notice = data["body"][0]
        assert notice["type"] == "markdown" and "public" in notice["attributes"]["value"], p.name
        ids = [b["id"] for b in data["body"] if b["type"] != "markdown"]
        assert len(ids) == len(set(ids)), p.name
    assert sorted(FORMS) == sorted(ROUTING)


def test_blank_issues_are_disabled_and_the_submit_page_is_linked():
    cfg = yaml.safe_load((TEMPLATES / "config.yml").read_text())
    assert cfg["blank_issues_enabled"] is False
    assert "https://garleak.org/submit/" in [c["url"] for c in cfg["contact_links"]]


def test_category_dropdowns_list_the_non_gated_categories():
    a = load_archive(REPO / "archive")
    expected = [f"{c.code}: {c.name}" for c in a.categories.values() if not c.gated]
    for kind in ("scratch", "paper"):
        assert FORMS[kind].field("category").options == expected


def test_verify_form_lists_every_required_item():
    text = (TEMPLATES / "5-verify-paper.yml").read_text()
    for r in RubricSet.load(RUBRICS):
        for t in r.tiers:
            for item in r.required_at(t):
                assert item.id in text, item.id


def test_prose_rules():
    files = list(TEMPLATES.glob("*.yml")) + [REPO / "docs" / "INTAKE.md", REPO / ".github" / "labels.yml",
                                             REPO / ".github" / "CODEOWNERS"]
    for p in files:
        text = p.read_text()
        assert "—" not in text, p
        assert not MARKERS.search(text), (p, MARKERS.search(text))
        assert not re.search(r"\bpublished\b", text, re.I), p


def test_submit_and_verify_pages_describe_the_process(built):
    root, _ = built
    submit = page(root, "/submit/")
    assert "at launch" in submit and "issues/new?template=2-submit-scratch.yml" in submit
    assert "Your GitHub account is public, and so is the ORCID link that verifies it." in submit
    assert "not accepted in Phase 1" in submit
    verify = page(root, "/verify/")
    assert "issues/new?template=5-verify-paper.yml" in verify and "at launch" in verify
    assert "The queue fills when submissions open" in verify
