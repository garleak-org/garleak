# SPDX-License-Identifier: AGPL-3.0-or-later
"""Quotas, rate limits, the credit floor and the gated switch, as the intake enforces them."""

import pytest

from .intake_support import Arch, answers, ctx, make_issue, open_pr, run

TODAY = "2026-09-14"


@pytest.fixture
def arch(tmp_path):
    a = Arch(tmp_path)
    for h in ("alice", "bob", "carol"):
        a.account(h)
    a.account("scout", kind="agent", operator="alice")
    a.account("scout2", kind="agent", operator="alice")
    return a


def failing(res):
    return {c.id: c for c in res.failed}


def test_paper_quota_counts_open_pull_requests(arch):
    arch.set("credits.spend.paper", 0.0)
    arch.paper(1, "alice", date=TODAY)
    arch.paper(2, "alice", date=TODAY)
    assert run(arch, make_issue("paper", number=3)).status == "held"
    pending = open_pr(40, 9, {"kind": "paper", "ids": ["paper:3"], "account": "alice", "field": "phys",
                              "spend": "0", "date": TODAY})
    res = run(arch, make_issue("paper", number=10), ctx(open_prs=[pending]))
    c = failing(res)["quota"]
    assert "limit is 3" in c.detail and c.criterion == "SPEC §5.6.7 (OQ-12)"


def test_agent_and_operator_sketch_quotas(arch):
    arch.set("credits.spend.sketch", 0.0)
    arch.set("credits.agent_balance_floor", -100.0)
    for n in (1, 2, 3):
        arch.sketch(n, "scout", date=TODAY, statement=f"Agent sketch {n} about the Galactic tide and binaries.")
    res = run(arch, make_issue("sketch", number=20, author="scout"))
    assert "agent limit is 3" in failing(res)["quota"].detail
    for n in (4, 5):
        arch.sketch(n, "scout2", date=TODAY, statement=f"Second agent sketch {n} about stellar streams today.")
    arch.sketch(6, "scout2", date="2026-09-13", statement="Yesterday's sketch does not count toward today.")
    res = run(arch, make_issue("sketch", number=21, author="scout2"), dry_run=True)
    assert res.status == "held" and any(c.id == "agent" for c in res.flagged)  # 5 of 6 for the operator
    pending = open_pr(41, 30, {"kind": "sketch", "ids": ["sketch:7"], "account": "scout", "field": "phys",
                               "spend": "0", "date": TODAY})
    res = run(arch, make_issue("sketch", number=22, author="scout2"), ctx(open_prs=[pending]))
    assert "limit per operator is 6" in failing(res)["quota"].detail


def test_the_credit_floor_refuses_and_names_its_criterion(arch):
    arch.paper(1, "alice")
    res = run(arch, make_issue("paper", number=5))
    c = failing(res)["credits"]
    assert c.criterion == "SPEC §5.4.3 (OQ-10)" and "-4.0, below the floor of -2.0" in c.detail
    pending = open_pr(42, 8, {"kind": "paper", "ids": ["paper:2"], "account": "bob", "field": "phys",
                              "spend": "2.0", "date": TODAY})
    res = run(arch, make_issue("paper", number=6, author="bob"), ctx(open_prs=[pending]))
    assert "credits" in failing(res)


def test_verification_daily_limit(arch):
    for n in range(1, 7):
        arch.paper(n, "alice")
    for n in range(1, 6):
        arch.verification(n, f"{n}-01", "bob", date=TODAY)
    res = run(arch, make_issue("verify", answers("verify", version="paper:6v1.0"), number=9, author="bob"))
    c = failing(res)["rate"]
    assert "limit is 5" in c.detail and c.criterion == "SPEC §5.6.6 (OQ-12)"


def test_a_burst_is_flagged_not_blocked(arch):
    for n in range(1, 5):
        arch.paper(n, "alice")
    for n, at in ((1, "09:20"), (2, "09:40"), (3, "09:55")):
        arch.verification(n, f"{n}-01", "bob", date=TODAY, at=f"{TODAY}T{at}:00Z")
    res = run(arch, make_issue("verify", answers("verify", version="paper:4v1.0"), number=9, author="bob"))
    assert res.status == "accepted" and res.automerge
    assert [c.id for c in res.flagged] == ["burst"] and "flag:burst" in res.labels()[0]


def test_novelty_daily_limit(arch):
    arch.sketch(1, "alice")
    for i in range(1, 11):
        arch.sketch(10 + i, "carol", statement=f"Carol's sketch number {i} about a new idea for tides.")
        arch.check(10 + i, f"{10 + i}-n1", "bob", date=TODAY)
    res = run(arch, make_issue("novelty", number=9, author="bob"))
    assert "limit is 10" in failing(res)["rate"].detail


# ---------------------------------------------------------------- gated categories


@pytest.mark.parametrize("kind", ["sketch", "paper"])
def test_gated_categories_are_refused_in_phase_1(arch, kind):
    res = run(arch, make_issue(kind, answers(kind, category="med.clinical: Clinical research"), number=5))
    c = failing(res)["gated"]
    assert c.criterion == "SPEC §3.7.7 (OQ-24)" and "Phase 2" in c.detail and "contact@garleak.org" in c.detail
    assert res.files == [] and res.status == "refused"


def test_the_gated_switch_opens_them_held_for_a_person(arch):
    arch.set("intake.accept_gated", True)
    res = run(arch, make_issue("sketch", answers("sketch", category="med.clinical: Clinical research"), number=5))
    assert res.status == "held" and not res.automerge and any(c.id == "gated" for c in res.flagged)
    assert arch.errors() == [] and arch.load().sketches[1].gated is True


def test_agents_never_enter_gated_categories(arch):
    arch.set("intake.accept_gated", True)
    res = run(arch, make_issue("paper", answers("paper", category="med.clinical: Clinical research"), number=5,
                               author="scout"))
    assert failing(res)["category"].criterion == "SPEC §3.4.5"
