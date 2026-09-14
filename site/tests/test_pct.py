# SPDX-License-Identifier: AGPL-3.0-or-later
"""pct_original, algorithm po-1 (SPEC §6.6), with the test vectors §6.6.6 asks for."""

from garleak_archive.pct import covered_positions, po1, rendition, round_half_up, shingles, tokenize

V1 = "We fit the rotation curve with a single exponential disk and find a flat outer profile"
VN = ("We fit the rotation curve with a single exponential disk plus a bulge and find a slowly "
      "falling outer profile")


def test_spec_worked_example():
    """§6.6.4: C = 10 of 20, pct_original 50; 10 of 16 retained, shown as 63."""
    assert len(tokenize(V1)) == 16
    assert len(tokenize(VN)) == 20
    r = po1(V1, VN)
    assert (r.covered, r.tokens, r.value) == (10, 20, 50)
    assert (r.retained_covered, r.v1_tokens, r.retained_value) == (10, 16, 63)
    assert (r.algorithm, r.k) == ("po-1", 5)


def test_v1_is_100():
    r = po1(V1, V1, is_v1=True)
    assert r.value == 100 and r.retained_value == 100


def test_empty_version_is_na():
    r = po1(V1, "")
    assert r.value is None and r.display() == "n/a"


def test_empty_v1():
    r = po1("", VN)
    assert r.value == 0 and r.retained_value is None


def test_fewer_than_k_tokens_covers_nothing():
    assert po1("a b c d", "a b c d").covered == 0


def test_moved_paragraph_still_counts():
    a = "one two three four five six. seven eight nine ten eleven twelve."
    b = "seven eight nine ten eleven twelve. one two three four five six."
    assert po1(a, b).value == 100


def test_normalization_and_latex():
    assert tokenize(r"Café \alpha-Centauri, 2026") == ["café", "alpha", "centauri", "2026"]
    assert tokenize("ＡＢＣ") == ["abc"]  # NFKC


def test_rounding_halves_up():
    assert round_half_up(1, 8) == 13  # 12.5
    assert round_half_up(5, 8) == 63  # 62.5


def test_covered_positions_counts_each_position_once():
    t = tokenize("a b c d e f")
    assert covered_positions(t, shingles(t, 5), 5) == 6


def test_rendition_excludes_references_and_code():
    body = "## Results\n\nWe find x.\n\n```\ncode here\n```\n\n## References\n\nSmith 2020.\n"
    text = rendition("Title", "Abstract.", body)
    assert "We find x" in text and "Smith" not in text and "code here" not in text
