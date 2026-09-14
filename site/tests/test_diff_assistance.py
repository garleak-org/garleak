# SPDX-License-Identifier: AGPL-3.0-or-later
"""Word diff, the two assistance axes, and safe rendering of record bodies."""

import pytest

from garleak_archive import assistance as asst
from garleak_archive.diff import inline_diff_html, render_html, word_diff
from garleak_site.markup import render_body


def test_word_diff_counts_and_marks():
    r = word_diff("the gap lasts 1.2 Gyr", "the gap lasts 0.6 Gyr")
    assert (r.added, r.removed) == (1, 1)
    out = render_html(r)
    assert "<del>1.2</del>" in out and "<ins>0.6</ins>" in out


def test_identical_texts_have_no_changes():
    assert not word_diff("same words here", "same words here").changed


def test_diff_escapes_html():
    out = render_html(word_diff("a", "a <script>x</script>"))
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_diff_keeps_blocks():
    out = render_html(word_diff("## Intro\n\nOld text.", "## Intro\n\nNew text."))
    assert out.startswith("<h4>Intro</h4>") and "<p>" in out


def test_inline_diff():
    assert inline_diff_html("A title", "A new title") == "A <ins>new</ins> title"


def test_median_two_middle_codes():
    m = asst.median("writing", {"W1": 3, "W2": 3})
    assert (m.low, m.high, str(m)) == ("W1", "W2", "W1 to W2")


def test_median_odd_and_threshold():
    assert str(asst.median("analysis", {"A0": 1, "A1": 7, "A2": 3})) == "A1"
    assert asst.median("writing", {"W1": 2, "W2": 2}) is None  # fewer than 5 votes


def test_predicted_interval_is_smallest_run():
    iv = asst.predicted_interval("analysis", {"A0": 0.05, "A1": 0.30, "A2": 0.65})
    assert iv.point == "A2" and iv.members == ("A1", "A2") and iv.mass >= 0.9


def test_axes_are_separate_scales():
    assert asst.codes("writing") == ["W0", "W1", "W2", "W3"]
    assert asst.codes("analysis") == ["A0", "A1", "A2"]
    assert not hasattr(asst, "combined")


@pytest.mark.parametrize("src,bad", [
    ("<script>alert(1)</script>", "<script"),
    ("[x](javascript:alert(1))", "javascript:"),
    ('<img src=x onerror="alert(1)">', "<img"),
])
def test_record_bodies_are_rendered_safely(src, bad):
    assert bad not in render_body(src, "/src/1v1.0/")


def test_relative_targets_point_into_the_source_directory():
    out = render_body("![figure](fig1.png) [site](/admin/)", "/src/1v1.0/")
    assert 'src="/src/1v1.0/fig1.png"' in out and 'href="/admin/"' not in out
