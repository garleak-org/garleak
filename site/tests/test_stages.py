# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stage derivation, SPEC §2.4, §2.5 and §6.3: a major version clears verifications and
a minor version carries them, with reopened items pending."""

from garleak_archive.ids import VersionNumber as VN
from garleak_archive.loader import load_archive
from garleak_archive.stages import compute_paper, sketch_stage
from garleak_archive.validate import validate

from .conftest import EXAMPLE

BODY = "## Results\n\nSome text that is long enough to count as a paper body.\n"


def states(root, n):
    a = load_archive(root)
    assert not [i for i in validate(a) if i.level == "error"], validate(a)
    return compute_paper(a.papers[n], a.rubrics)


def test_example_paper_4471():
    a = load_archive(EXAMPLE)
    s = compute_paper(a.papers[4471], a.rubrics)
    assert s[VN(1, 0)].tier == "T0" and s[VN(1, 0)].statuses["T1"] == "failed"
    assert s[VN(1, 1)].tier == "T1" and s[VN(1, 1)].statuses["T2"] == "failed"  # fix 11 reopened, re-check passed
    assert s[VN(2, 0)].tier == "T2"
    assert s[VN(3, 0)].tier == "T3"


def test_example_carry_and_clear():
    a = load_archive(EXAMPLE)
    assert compute_paper(a.papers[4420], a.rubrics)[VN(1, 2)].tier == "T2"  # carried through two minors
    s4398 = compute_paper(a.papers[4398], a.rubrics)
    assert s4398[VN(1, 0)].tier == "T2" and s4398[VN(2, 0)].tier == "T0"  # major clears
    assert compute_paper(a.papers[4356], a.rubrics)[VN(4, 0)].tier == "T4"


def test_minor_carries_major_clears(maker):
    maker.paper(1, [("1.0", "initial", "2026-09-01", BODY), ("1.1", "minor", "2026-09-05", BODY + "\nTypo.\n"),
                    ("2.0", "major", "2026-09-08", BODY + "\nNew claim.\n")])
    maker.verification(1, "1-01", "1.0", "T1", "2026-09-02")
    maker.verification(1, "1-02", "1.0", "T2", "2026-09-03")
    s = states(maker.root, 1)
    assert s[VN(1, 0)].tier == "T2"
    assert s[VN(1, 1)].tier == "T2" and all(e.carried for e in s[VN(1, 1)].effective)
    assert s[VN(2, 0)].tier == "T0" and not s[VN(2, 0)].effective


def test_reopened_items_are_pending_until_rechecked(maker):
    maker.paper(2, [("1.0", "initial", "2026-09-01", BODY), ("1.1", "minor", "2026-09-05", BODY + "\nNew ref.\n")],
                reopens={"1.1": ["cit.T1.exists"]})
    maker.verification(2, "2-01", "1.0", "T1", "2026-09-02")
    s = states(maker.root, 2)
    assert s[VN(1, 1)].tier == "T1" and s[VN(1, 1)].pending and s[VN(1, 1)].statuses["T1"] == "pending"
    maker.verification(2, "2-02", "1.1", "T1", "2026-09-06", verifier="otto")
    s = states(maker.root, 2)
    assert not s[VN(1, 1)].pending and s[VN(1, 1)].statuses["T1"] == "passed"


def test_contested_tier(maker):
    maker.paper(3, [("1.0", "initial", "2026-09-01", BODY)])
    maker.verification(3, "3-01", "1.0", "T1", "2026-09-02")
    maker.verification(3, "3-02", "1.0", "T1", "2026-09-03", verifier="otto", fail=True)
    s = states(maker.root, 3)[VN(1, 0)]
    assert s.statuses["T1"] == "contested" and s.tier == "T0"


def test_tiers_are_cumulative(maker):
    maker.paper(4, [("1.0", "initial", "2026-09-01", BODY)])
    maker.verification(4, "4-01", "1.0", "T2", "2026-09-02")
    s = states(maker.root, 4)[VN(1, 0)]
    assert s.statuses["T2"] == "passed" and s.tier == "T0"  # counts once T1 is held (§2.4.5)


def test_t4_needs_a_recorded_independent_verifier(maker):
    maker.paper(5, [("1.0", "initial", "2026-09-01", BODY)])
    for i, t in enumerate(("T1", "T2", "T3")):
        maker.verification(5, f"5-0{i}", "1.0", t, "2026-09-02")
    maker.verification(5, "5-09", "1.0", "T4", "2026-09-03", verifier="otto", independent=False)
    a = load_archive(maker.root)
    errs = [i.message for i in validate(a) if i.level == "error"]
    assert any("T4 verification needs an independent verifier" in e for e in errs)
    assert compute_paper(a.papers[5], a.rubrics)[VN(1, 0)].tier == "T3"


def test_sketch_stages():
    a = load_archive(EXAMPLE)
    assert sketch_stage(a.sketches[8813]) == ("N0", "")
    assert sketch_stage(a.sketches[8812])[0] == "N1"
    assert sketch_stage(a.sketches[8815])[0] == "N2"
    assert sketch_stage(a.sketches[8816]) == ("N3", "no prior work found")
