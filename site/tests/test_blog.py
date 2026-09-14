# SPDX-License-Identifier: AGPL-3.0-or-later
"""The blog: posts and statements from Markdown files, with an index, one page each and a feed."""

import datetime as dt

import pytest

from garleak_site.blog import BlogError, load_posts
from garleak_site.build import Builder
from garleak_site.checks import check_site

from .conftest import page


def _blog(tmp_path):
    b = tmp_path / "blog"
    b.mkdir()
    (b / "README.md").write_text("# Not a post\n")
    (b / "2026-09-10-why-garleak.md").write_text(
        "---\ntitle: Why Garleak\nauthor: Serat Saad\nsummary: The idea in one line.\n---\n\n"
        "Posts may mention arXiv and journals.\n")
    (b / "2026-09-12-on-screening.md").write_text("---\ntitle: On screening\nkind: statement\n---\n\nA statement.\n")
    (b / "2026-09-13-later.md").write_text("---\ntitle: Not ready\ndraft: true\n---\n\nA draft.\n")
    return b


def test_posts_are_newest_first_and_drafts_are_skipped(tmp_path):
    posts = load_posts(_blog(tmp_path))
    assert [p.slug for p in posts] == ["on-screening", "why-garleak"]
    assert posts[0].kind_label == "Statement" and posts[0].author == "Garleak"
    assert posts[1].date == dt.date(2026, 9, 10) and posts[1].url == "/blog/why-garleak/"


@pytest.mark.parametrize("name, text", [
    ("Bad Name.md", "---\ntitle: x\n---\n"),
    ("2026-09-10-x.md", "no front matter"),
    ("2026-09-10-y.md", "---\nkind: post\n---\n"),
    ("2026-09-10-z.md", "---\ntitle: t\nkind: essay\n---\n"),
])
def test_malformed_posts_are_refused(tmp_path, name, text):
    b = tmp_path / "blog"
    b.mkdir()
    (b / name).write_text(text)
    with pytest.raises(BlogError):
        load_posts(b)


def test_no_blog_folder_means_an_empty_index(tmp_path):
    assert load_posts(tmp_path / "missing") == [] and load_posts(None) == []


def test_blog_builds_indexes_and_passes_checks(tmp_path, config):
    out = tmp_path / "_site"
    Builder(dict(config, blog=_blog(tmp_path)), out, dt.date(2026, 9, 14)).build()
    index = page(out, "/blog/")
    assert "Why Garleak" in index and "(statement)" in index and "Not ready" not in index
    post = page(out, "/blog/why-garleak/")
    assert "Posts may mention arXiv and journals." in post and 'name="robots"' not in post
    assert "<loc>https://garleak.org/blog/why-garleak/</loc>" in (out / "sitemap.xml").read_text()
    assert "/blog/on-screening/" in (out / "blog" / "feed.xml").read_text()
    assert 'href="/blog/"' in page(out, "/")
    report = check_site(out)
    assert not report.errors, report.errors
