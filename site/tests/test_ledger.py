# SPDX-License-Identifier: AGPL-3.0-or-later
"""Credits, loops and standing, all derived from the records (garleak_archive.ledger)."""

import datetime as dt

import pytest
import yaml

from garleak_archive import ledger
from garleak_archive.ledger import Action, Pending, dec, detect_loops
from garleak_archive.models import ScreeningRecord
from garleak_archive.stages import compute_paper

from .intake_support import Arch

D = dt.date


@pytest.fixture
def arch(tmp_path):
    a = Arch(tmp_path)
    for h in ("alice", "bob", "carol", "dave", "erin"):
        a.account(h)
    a.account("scout", kind="agent", operator="alice")
    return a


def bal(a, h, f="phys"):
    return ledger.balance(a, h, f)


# ---------------------------------------------------------------- earn and spend


def test_spend_and_earn_are_field_scoped(arch):
    arch.paper(1, "alice")
    arch.verification(1, "1-01", "bob")
    arch.scratch(1, "bob", category="math.nt")
    a = arch.load()
    assert bal(a, "alice") == dec(-2) and bal(a, "bob") == dec(1) and bal(a, "bob", "math") == dec("-1.5")
    kinds = {e.kind for e in ledger.events(a)}
    assert kinds == {"spend_paper", "earn_verification", "spend_scratch"}
    assert all(e.config_version == "0.1" for e in ledger.events(a))


def test_the_floor_allows_one_paper_per_field(arch):
    a = arch.load()
    first = ledger.check_spend(a, "alice", "phys", "paper")
    assert first.ok and (first.before, first.after, first.floor) == (dec(0), dec(-2), dec(-2))
    arch.paper(1, "alice")
    a = arch.load()
    assert not ledger.check_spend(a, "alice", "phys", "paper").ok
    assert ledger.check_spend(a, "alice", "math", "paper").ok  # another field has its own floor
    arch.paper(2, "bob")
    arch.verification(2, "2-01", "alice")
    arch.verification(2, "2-02", "alice", tier="T2")
    a = arch.load()
    assert ledger.check_spend(a, "alice", "phys", "paper").ok  # verified two, so one more paper


def test_an_agent_spends_from_its_operator_and_may_not_overdraw(arch):
    sc = ledger.check_spend(arch.load(), "scout", "phys", "scratch")
    assert sc.payer == "alice" and sc.floor == 0 and not sc.ok
    arch.paper(1, "bob")
    arch.verification(1, "1-01", "alice")
    arch.verification(1, "1-02", "alice", tier="T2")
    assert ledger.check_spend(arch.load(), "scout", "phys", "scratch").ok


def test_refund_on_removal_except_for_criterion_one(arch):
    arch.paper(1, "alice", status="removed", removal={"date": "2026-09-10", "criterion": "2"})
    arch.scratch(1, "bob", status="removed", removal={"date": "2026-09-10", "criterion": "1"})
    a = arch.load()
    assert bal(a, "alice") == 0 and bal(a, "bob") == dec("-1.5")


def test_a_rejection_under_criterion_one_keeps_its_charge(arch):
    (arch.root / "screening").mkdir()
    (arch.root / "screening" / "reject-4.yaml").write_text(yaml.safe_dump({
        "id": "reject-4", "decision": "reject", "criterion": 1, "date": "2026-09-14", "object": "paper",
        "category": "phys.astro", "submitter": "bob"}))
    a = arch.load()
    assert arch.errors() == []
    assert bal(a, "bob") == dec(-2)
    assert ledger.daily_counts(a, ["bob"], D(2026, 9, 14)).papers == 1


def test_withdrawn_is_reversed_and_overturned_keeps_its_credit(arch):
    arch.paper(1, "alice")
    arch.verification(1, "1-01", "bob", status="withdrawn",
                      status_history=[{"status": "withdrawn", "by": "bob", "date": "2026-09-07", "reason": "wrong"}])
    arch.verification(1, "1-02", "carol", status="overturned")
    a = arch.load()
    assert bal(a, "bob") == 0 and bal(a, "carol") == 1


def test_promotion_credits_the_scratch_author(arch):
    arch.scratch(1, "bob", promoted_to=[1])
    arch.paper(1, "alice", promoted_from="scratch:1v1.0")
    a = arch.load()
    assert arch.errors() == []
    assert bal(a, "bob") == dec(1 - 1.5)


def test_pending_spends_count(arch):
    a = arch.load()
    p = [Pending("paper", "alice", "phys", D(2026, 9, 14), spend=dec(2), issue=9)]
    sc = ledger.check_spend(a, "alice", "phys", "paper", p)
    assert sc.before == dec(-2) and not sc.ok


def test_amounts_come_from_the_config(arch):
    arch.set("credits.spend.paper", 3.0)
    arch.paper(1, "alice")
    assert bal(arch.load(), "alice") == dec(-3)


def test_moderation_credit_rule_is_ready_for_a_moderator_field(arch):
    a = arch.load()
    a.screening.append(ScreeningRecord("r1", "reject", 2, D(2026, 9, 14), "paper", "phys.astro", "bob",
                                       moderator="dave"))
    assert ledger.balance(a, "dave", "phys") == dec(1)


# ---------------------------------------------------------------- loops (§5.6)


def test_a_two_account_loop_is_labeled_and_earns_nothing(arch):
    arch.paper(1, "alice")
    arch.paper(2, "bob")
    arch.verification(1, "1-01", "bob", date="2026-09-05")
    arch.verification(2, "2-01", "alice", date="2026-09-10")
    a = arch.load()
    labels = {v.id: v.loop_label for p in a.papers.values() for v in p.verifications}
    assert labels == {"1-01": {"length": 2, "detected": "2026-09-10"}, "2-01": {"length": 2, "detected": "2026-09-10"}}
    assert bal(a, "bob") == dec(-2) and bal(a, "alice") == dec(-2)
    assert any("reciprocal loop of length 2" in e.reason for e in ledger.events(a))


def test_a_ring_of_three_earns_nothing_and_is_labeled(arch):
    """BUILD-PLAN S3: a test ring of three accounts verifying each other."""
    for n, h in ((1, "alice"), (2, "bob"), (3, "carol")):
        arch.paper(n, h)
    arch.verification(1, "1-01", "bob")
    arch.verification(2, "2-01", "carol")
    arch.verification(3, "3-01", "alice")
    a = arch.load()
    for p in a.papers.values():
        assert p.verifications[0].loop_label["length"] == 3
    for h in ("alice", "bob", "carol"):
        assert bal(a, h) == dec(-2)


def test_edges_further_apart_than_the_window_make_no_loop(arch):
    arch.paper(1, "alice", date="2025-12-01")
    arch.paper(2, "bob", date="2025-12-01")
    arch.verification(1, "1-01", "bob", date="2026-01-01")
    arch.verification(2, "2-01", "alice", date="2026-09-01")  # 243 days later
    a = arch.load()
    assert all(v.loop_label is None for p in a.papers.values() for v in p.verifications)
    arch.set("loops.window_days", 300)
    assert all(v.loop_label for p in arch.load().papers.values() for v in p.verifications)


def test_a_cycle_of_five_is_not_a_loop():
    people = ["a", "b", "c", "d", "e"]
    acts = [Action(f"verification:{i}", people[i], people[(i + 1) % 5], D(2026, 9, 1)) for i in range(5)]
    assert detect_loops(acts, 180) == {}
    assert len(detect_loops(acts[:4] + [Action("verification:x", "d", "a", D(2026, 9, 2))], 180)) == 4


def test_novelty_checks_are_edges_too(arch):
    arch.scratch(1, "alice")
    arch.scratch(2, "bob")
    arch.check(1, "1-n1", "bob")
    arch.check(2, "2-n1", "alice")
    a = arch.load()
    assert a.scratches[1].checks[0].loop_label["length"] == 2
    assert bal(a, "bob") == dec("-1.5")


def test_loop_labeled_records_count_to_t3_but_not_t4_or_standing(arch):
    arch.paper(1, "alice")
    arch.paper(2, "bob")
    for vid, tier in (("1-01", "T1"), ("1-02", "T2"), ("1-03", "T3")):
        arch.verification(1, vid, "carol", tier=tier, date="2026-01-10")
    arch.verification(1, "1-04", "bob", tier="T4", date="2026-01-10",
                      independent={"value": True, "computed_at": "2026-01-10", "sources": ["test"]},
                      t4_attestation={"text": "none", "date": "2026-01-10"})
    arch.verification(2, "2-01", "alice", date="2026-01-12")  # closes alice <-> bob
    a = arch.load()
    p1 = a.papers[1]
    assert p1.verifications[-1].loop_label is not None
    state = compute_paper(p1, a.rubrics)[p1.versions[0].number]
    assert state.tier == "T3"
    today = D(2026, 9, 1)
    assert ledger.standing(a, "bob", "phys", today) == 0 and ledger.standing(a, "carol", "phys", today) == 3
    assert a.papers[2].verifications[0].loop_label is not None  # and still counts toward T1
    state2 = compute_paper(a.papers[2], a.rubrics)[a.papers[2].versions[0].number]
    assert state2.tier == "T1"


def test_standing_counts_overturns_three_times(arch):
    arch.paper(1, "alice", date="2026-01-01")
    for i in range(1, 6):
        arch.verification(1, f"1-0{i}", "bob", date="2026-01-05")
    arch.verification(1, "1-06", "bob", date="2026-01-05", status="overturned")
    assert ledger.standing(arch.load(), "bob", "phys", D(2026, 9, 1)) == 5 - 3
    assert not ledger.has_field_standing(arch.load(), "bob", "phys", D(2026, 9, 1))
