# SPDX-License-Identifier: AGPL-3.0-or-later
"""End to end: an issue from each form becomes records that validate and that the site
builds from, or a refusal that names its criterion."""

import json

import pytest
import yaml

from garleak_archive import ledger
from garleak_intake.cli import main as cli_main
from garleak_intake.orcid import OrcidClient
from garleak_intake.http import Response
from garleak_site.build import Builder
from garleak_site.checks import check_site

from .conftest import BUILD_DATE, page
from .intake_support import (
    Arch,
    FakeHttp,
    answers,
    command_event,
    comment,
    ctx,
    make_issue,
    run,
)


@pytest.fixture
def arch(tmp_path):
    a = Arch(tmp_path)
    for h in ("alice", "bob", "carol", "mod"):
        a.account(h)
    a.account("kestrel", github="Kestrel", pseud=True, path="institutional_email")
    return a


def fails(res):
    return {c.id for c in res.failed}


# ---------------------------------------------------------------- sketch


def test_sketch_is_accepted_and_merges_on_its_own(arch):
    res = run(arch, make_issue("sketch", author="alice"))
    assert res.status == "accepted" and res.automerge and res.action == "pr"
    assert res.ids == ["sketch:1"] and res.files == ["sketches/1.yaml"]
    assert arch.errors() == []
    s = arch.load().sketches[1]
    assert s.intake == {"path": "issue-form", "issue": 1, "at": "2026-09-14T10:00:00Z"}
    assert s.assistance["analysis"] is None and s.track == "human-prompted"
    text = res.comment_markdown()
    assert "Credits of u/alice in Physics: 0.0 before, -1.5 after (the floor is -2.0)" in text
    assert "Your GitHub handle is public" in text and "—" not in text
    assert res.outputs() == {"action": "pr", "status": "accepted", "kind": "sketch", "automerge": "true",
                             "branch": "intake/issue-1", "close": "", "close_pr": "false", "comment": "true"}
    assert "Closes #1" in res.pr_body() and '"ids": ["sketch:1"]' in res.pr_body()


def test_dry_run_leaves_the_archive_untouched(arch):
    res = run(arch, make_issue("sketch"), dry_run=True)
    assert res.status == "accepted" and "sketches/1.yaml" in res.previews
    assert not (arch.root / "sketches" / "1.yaml").exists()


def test_an_unlinked_github_account_is_refused(arch):
    res = run(arch, make_issue("sketch", author="stranger"))
    assert res.status == "refused" and "account" in fails(res) and res.action == "comment"
    assert "Criterion: SPEC §3.1, §3.7.2." in res.comment_markdown()


def test_already_recorded_issue_is_a_noop(arch):
    run(arch, make_issue("sketch"))
    res = run(arch, make_issue("sketch", answers("sketch", statement="An edited statement about wide binaries.")))
    assert res.status == "noop" and "Already recorded as sketch:1" in res.headline
    assert not (arch.root / "sketches" / "2.yaml").exists()


def test_form_problems_are_named(arch):
    res = run(arch, make_issue("sketch", answers("sketch", models="", confirm=[])))
    titles = {c.title for c in res.failed}
    assert "Form: Models used" in titles and "Form: Confirm" in titles


# ---------------------------------------------------------------- paper and versions


def test_paper_is_held_and_builds(arch, tmp_path, config):
    res = run(arch, make_issue("paper", answers("paper", authors="alice\nbob"), author="alice"))
    assert res.status == "held" and not res.automerge and res.ids == ["paper:1"]
    assert arch.errors() == []
    p = arch.load().papers[1]
    assert p.versions[0].authors == ["alice", "bob"] and p.versions[0].intake["issue"] == 1
    assert p.versions[0].rubric_families == ["computational"]
    out = tmp_path / "_site"
    Builder(dict(config, archive=arch.root, example_archive=None), out, BUILD_DATE).build()
    assert "A lighter halo from a rotation curve fit" in page(out, "/abs/1/")
    assert check_site(out).errors == []


def test_new_version_by_a_maintainer(arch):
    arch.paper(1, "alice")
    res = run(arch, make_issue("version", number=2))
    assert res.status == "held" and res.ids == ["paper:1v1.1"]
    assert arch.errors() == []
    p = arch.load().papers[1]
    assert "1.1" in p.version_sha256 and p.versions[1].change == "minor"


def test_new_version_by_someone_else_is_refused(arch):
    arch.paper(1, "alice")
    res = run(arch, make_issue("version", number=2, author="bob"))
    assert "maintainer" in fails(res)


def test_minor_version_that_changes_numbers_is_flagged(arch):
    arch.paper(1, "alice")
    res = run(arch, make_issue("version", answers("version", body=long_body_with_number()), number=2))
    assert res.status == "held" and any(c.id == "bump" for c in res.flagged)


def long_body_with_number():
    from .intake_support import long_body

    return long_body("paper1").replace("number 3", "number 3.5")


# ---------------------------------------------------------------- verification


def test_t1_verification_is_accepted(arch):
    arch.paper(1, "alice")
    res = run(arch, make_issue("verify", number=3, author="bob"))
    assert res.status == "accepted" and res.automerge
    assert arch.errors() == []
    v = arch.load().papers[1].verifications[0]
    assert v.id == "1-01" and v.result == "passed" and v.attestation and v.independent is None
    assert "Credits of u/bob in Physics: 0.0 before, 1.0 after" in res.comment_markdown()


def test_failed_item_makes_a_failed_verification(arch):
    arch.paper(1, "alice")
    items = answers("verify")["items"].replace("cit.T1.exists | pass", "cit.T1.exists | fail")
    res = run(arch, make_issue("verify", answers("verify", items=items), number=3, author="bob"))
    assert res.status == "accepted"
    assert arch.load().papers[1].verifications[0].result == "failed"


def test_verification_rules(arch):
    arch.paper(1, "alice")
    missing = "cit.T1.exists | pass | https://example.org/x"
    res = run(arch, make_issue("verify", answers("verify", items=missing), number=3, author="bob"))
    assert "items" in fails(res) and "cit.T1.retractions" in res.comment_markdown()
    res = run(arch, make_issue("verify", number=4, author="alice"))
    assert "independence" in fails(res)
    res = run(arch, make_issue("verify", answers("verify", rubric_version="0.9.0"), number=5, author="bob"))
    assert "rubric" in fails(res)
    res = run(arch, make_issue("verify", answers("verify", version="paper:1v2.0"), number=6, author="bob"))
    assert "version" in fails(res)
    noevidence = answers("verify")["items"].replace(" | https://example.org/evidence/cit.T1.exists", "")
    res = run(arch, make_issue("verify", answers("verify", items=noevidence), number=7, author="bob"))
    assert "evidence" in res.comment_markdown()


def test_t4_waits_for_the_moderators_conflict_check(arch):
    arch.paper(1, "alice")
    for vid, tier in (("1-01", "T1"), ("1-02", "T2"), ("1-03", "T3")):
        arch.verification(1, vid, "carol", tier=tier)
    items = "\n".join(f"{i} | pass | https://example.org/{i}" for i in (
        "comp.T4.independent-verifier", "comp.T4.own-infrastructure", "comp.T4.full-rerun", "comp.T4.no-contributor-help"))
    ans = answers("verify", tier="T4: independently reproduced", rubric="computational (T2 to T4)", items=items)
    res = run(arch, make_issue("verify", ans, number=5, author="bob"))
    assert res.status == "waiting" and res.files == []
    c = comment("/conflict-check independent", "mod", 7)
    res = run(arch, make_issue("verify", ans, number=5, author="bob"), ctx([c], {"mod": "admin"}))
    assert res.status == "accepted"
    assert arch.errors() == []
    v = next(x for x in arch.load().papers[1].verifications if x.tier == "T4")
    assert v.independent["value"] is True and v.t4_attestation
    declared = dict(ans, conflicts="Shared affiliation with a contributor")
    res = run(arch, make_issue("verify", declared, number=6, author="carol"), ctx([c], {"mod": "admin"}))
    assert "conflict" in fails(res)


# ---------------------------------------------------------------- novelty, contest, vote, claim, report


def test_novelty_check(arch):
    arch.sketch(1, "alice")
    res = run(arch, make_issue("novelty", number=4, author="bob"))
    assert res.status == "accepted" and arch.errors() == []
    s = arch.load().sketches[1]
    assert s.checks[0].id == "1-n1" and s.v1_sha256 == s.content_sha256
    assert "independence" in fails(run(arch, make_issue("novelty", number=5, author="alice")))
    n3 = run(arch, make_issue("novelty", answers("novelty", outcome="N3: judged tractable", tractability="A month."),
                              number=6, author="carol"))
    assert n3.status == "accepted"


def test_n3_needs_an_earlier_check(arch):
    arch.sketch(1, "alice")
    res = run(arch, make_issue("novelty", answers("novelty", outcome="N3: judged tractable", tractability="x"),
                               number=4, author="bob"))
    assert "outcome" in fails(res)


def test_contest_by_a_contributor(arch):
    arch.paper(1, "alice")
    (arch.root / "papers/1/signals").mkdir()
    (arch.root / "papers/1/signals/1-p1.yaml").write_text(yaml.safe_dump({
        "id": "1-p1", "kind": "prediction", "version": "1.0", "date": "2026-09-02",
        "classifier": {"id": "garleak-assist", "version": "0.1"}, "writing": {"W2": 0.6, "W3": 0.4},
        "analysis": {"A1": 1.0}}))
    res = run(arch, make_issue("contest", number=5, author="alice"))
    assert res.status == "accepted" and arch.errors() == []
    assert "contributor" in fails(run(arch, make_issue("contest", number=6, author="bob")))


def test_vote_and_its_replacement(arch):
    arch.paper(1, "alice")
    res = run(arch, make_issue("vote", number=5, author="bob"))
    assert res.status == "accepted" and arch.errors() == []
    t = arch.load().papers[1].tallies[0]
    assert t.counts["writing"] == {"W2": 1} and t.counts["analysis"] == {}
    earlier = make_issue("vote", number=5, author="bob", labels=["status:merged"])
    again = make_issue("vote", answers("vote", writing="W3: a model wrote it, with light or no human edits"),
                       number=6, author="bob")
    res = run(arch, again, ctx(votes=[{"number": 5, "body": earlier["body"], "labels": earlier["labels"]}]))
    assert res.status == "accepted"
    t = arch.load().papers[1].tallies[0]
    assert t.counts["writing"] == {"W3": 1}
    assert "contributor" in fails(run(arch, make_issue("vote", number=7, author="alice")))
    merged = make_issue("vote", number=5, author="bob", labels=["status:merged"])
    assert run(arch, merged).status == "noop"


def test_claim(arch):
    arch.sketch(1, "alice")
    res = run(arch, make_issue("claim", number=5, author="bob"))
    assert res.status == "accepted" and arch.errors() == []
    c = arch.load().sketches[1].claims[0]
    assert str(c.expires) == "2026-12-13"
    assert "claim" in fails(run(arch, make_issue("claim", number=6, author="bob")))


def test_report_goes_to_the_moderators(arch):
    res = run(arch, make_issue("report", number=5, author="bob"))
    assert res.status == "acknowledged" and res.files == [] and "moderation:report" in res.labels()[0]


# ---------------------------------------------------------------- identity


def orcid_client(urls, name="Dana Example"):
    body = json.dumps({"researcher-url": [{"url": {"value": u}} for u in urls]}).encode()
    person = json.dumps({"name": {"given-names": {"value": name.split()[0]},
                                  "family-name": {"value": name.split()[1]}}}).encode()
    http = FakeHttp({"https://pub.orcid.org/v3.0/0000-0002-1825-0097/researcher-urls": Response(200, body),
                     "https://pub.orcid.org/v3.0/0000-0002-1825-0097/person": Response(200, person)})
    return OrcidClient(http, api_base="https://pub.orcid.org/v3.0", token_url="https://orcid.org/oauth/token")


def test_orcid_link(arch):
    ok = orcid_client(["https://github.com/Dana"])
    res = run(arch, make_issue("identity", number=8, author="Dana"), offline=False, orcid_client=ok)
    assert res.status == "held" and res.ids == ["u/dana"] and arch.errors() == []
    acc = arch.load().accounts["dana"]
    assert acc.orcid == "0000-0002-1825-0097" and acc.github == "Dana" and acc.identity_path == "orcid"


def test_orcid_record_without_the_github_url_is_refused(arch):
    res = run(arch, make_issue("identity", number=8, author="Dana"), offline=False,
              orcid_client=orcid_client(["https://github.com/someone-else"]))
    assert res.status == "refused" and "Websites and social links" in res.comment_markdown()
    bad = answers("identity", orcid="0000-0002-1825-0098")
    res = run(arch, make_issue("identity", bad, number=9, author="Dana"))
    assert "check digit" in res.comment_markdown()


def test_institutional_email_waits_for_a_moderator(arch):
    ans = answers("identity", path="Institutional email: a moderator checks it by hand", orcid="",
                  display="Handle only (pseudonymous)", display_name="")
    res = run(arch, make_issue("identity", ans, number=8, author="lowtide"))
    assert res.status == "waiting" and "contact@garleak.org" in res.lead
    fake = comment("/approve-email", "bob", 5)
    assert run(arch, make_issue("identity", ans, number=8, author="lowtide"), ctx([fake])).status == "waiting"
    c = comment("/approve-email", "mod", 6)
    res = run(arch, make_issue("identity", ans, number=8, author="lowtide"), ctx([c], {"mod": "maintain"}))
    assert res.status == "held" and arch.errors() == []
    acc = arch.load().accounts["lowtide"]
    assert acc.pseudonymous and acc.display_name == "u/lowtide" and acc.orcid is None


def test_agent_registration_needs_its_operator(arch):
    ans = answers("identity", kind="Agent operated by a human account", operator="alice",
                  agent_models="gpt-5, OpenAI, 2026-06", display_name="Survey Scout")
    res = run(arch, make_issue("identity", ans, number=8, author="scout-bot"))
    assert res.status == "waiting" and "@alice" in res.lead
    c = comment("/confirm-operator", "alice", 5)
    res = run(arch, make_issue("identity", ans, number=8, author="scout-bot"), ctx([c]))
    assert res.status == "held" and arch.errors() == []
    assert arch.load().accounts["scout-bot"].operator == "alice"


# ---------------------------------------------------------------- moderators


def test_reject_under_criterion_one_keeps_the_charge(arch):
    issue = make_issue("sketch", number=4, author="bob")
    c = comment("/reject 1 spam", "mod", 9)
    res = run(arch, issue, ctx([c], {"mod": "admin"}), command_event(c))
    assert res.status == "rejected" and res.close_pr and res.close_issue == "not planned"
    assert res.branch == "intake/issue-4-rejection" and res.automerge
    assert arch.errors() == []
    a = arch.load()
    assert ledger.balance(a, "bob", "phys") == ledger.dec("-1.5")


def test_reject_under_another_criterion_writes_nothing(arch):
    c = comment("/reject 2", "mod", 9)
    res = run(arch, make_issue("paper", number=4, author="bob"), ctx([c], {"mod": "admin"}), command_event(c))
    assert res.status == "rejected" and res.files == [] and "criterion 2" in res.headline


def test_only_moderators_reject(arch):
    c = comment("/reject 1", "bob", 9)
    res = run(arch, make_issue("sketch", number=4, author="carol"), ctx([c], {"bob": "read"}), command_event(c))
    assert res.status == "noop" and "Only moderators" in res.headline


def test_remove_after_merge_refunds_unless_spam(arch):
    run(arch, make_issue("sketch", number=4, author="bob"))
    assert ledger.balance(arch.load(), "bob", "phys") == ledger.dec("-1.5")
    c = comment("/remove 4 not ours to post", "mod", 9)
    res = run(arch, make_issue("sketch", number=4, author="bob", state="closed"), ctx([c], {"mod": "admin"}),
              command_event(c))
    assert res.status == "removed" and res.automerge and res.branch == "intake/issue-4-removal"
    a = arch.load()
    assert a.sketches[1].status == "removed" and ledger.balance(a, "bob", "phys") == 0
    assert arch.errors() == []


# ---------------------------------------------------------------- the CLI


def test_cli_dry_run(arch, tmp_path, capsys):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"action": "opened", "issue": make_issue("sketch")}))
    assert cli_main(["process", "--event", str(event), "--archive", str(arch.root), "--dry-run", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "status: accepted" in out and "--- sketches/1.yaml" in out and "v1_sha256" in out
    assert not (arch.root / "sketches" / "1.yaml").exists()


def test_cli_writes_outputs(arch, tmp_path):
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps(make_issue("sketch")))
    gh_out = tmp_path / "gh_output"
    out = tmp_path / "out"
    assert cli_main(["process", "--issue", str(issue), "--archive", str(arch.root), "--offline", "--out", str(out),
                     "--github-output", str(gh_out), "--now", "2026-09-14T12:00:00Z"]) == 0
    assert "action=pr\n" in gh_out.read_text() and "branch=intake/issue-1\n" in gh_out.read_text()
    assert (out / "pr-body.md").is_file() and (out / "commit-message.txt").read_text().startswith("Add sketch:1")
    assert "status:accepted" in (out / "labels-add.txt").read_text()
