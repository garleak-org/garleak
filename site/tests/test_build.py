# SPDX-License-Identifier: AGPL-3.0-or-later
"""Full builds of both archives, and the checks CI runs over them."""

import datetime as dt
import json
import re

from garleak_archive.loader import load_archive
from garleak_site.build import Builder
from garleak_site.checks import EM_DASH, _Page, check_site

from .conftest import BUILD_DATE, EXAMPLE, ArchiveMaker, page

BODY = "## Results\n\nSome text that is long enough to count as a paper body.\n"


def html_files(root):
    return sorted(root.rglob("*.html"))


def meta_robots(text):
    m = re.search(r'<meta name="robots" content="([^"]+)">', text)
    return m[1] if m else ""


def test_full_build_of_both_archives(built):
    root, stats = built
    assert stats["pages"] > 400 and stats["pdfs"] == 1
    for path in ("/", "/about/", "/stages/", "/spec/", "/verify/", "/submit/", "/citecheck/", "/terms/",
                 "/moderation/", "/search/", "/list/", "/sketch/list/", "/graduated/",
                 "/list/phys.astro/recent/", "/list/phys.astro/2026-09/", "/sketch/list/phys.astro/recent/",
                 "/example/", "/example/abs/4471/", "/example/diff/4471/1.0..3.0/", "/example/sketch/8812/"):
        assert page(root, path).startswith("<!doctype html>"), path
    assert (root / "CNAME").read_text().strip() == "garleak.org"
    assert "Sitemap: https://garleak.org/sitemap.xml" in (root / "robots.txt").read_text()
    assert (root / "list" / "phys.astro" / "feed.xml").is_file()
    assert not (root / "example" / "list" / "phys.astro" / "feed.xml").exists()


def test_site_passes_every_check(built):
    """Links and fragments resolve, markup is well formed, no em dash, wording, noindex,
    the banner, the sitemap, and no invented record outside /example/."""
    root, _ = built
    report = check_site(root, EXAMPLE)
    assert report.errors == []
    assert report.pages > 400


def test_html_is_well_formed(built):
    root, _ = built
    for f in html_files(root):
        pg = _Page()
        pg.feed(f.read_text())
        pg.close()
        assert pg.doctype and pg.lang == "en" and pg.title.strip(), f
        assert not pg.errors and not pg.stack and not pg.dup_ids, (f, pg.errors, pg.stack, pg.dup_ids)


def test_zero_em_dashes(built):
    root, _ = built
    for f in list(root.rglob("*.html")) + list(root.rglob("*.xml")):
        assert not EM_DASH.search(f.read_text()), f


def test_every_example_page_has_banner_and_noindex(built):
    root, _ = built
    files = html_files(root / "example")
    assert len(files) > 300
    for f in files:
        text = f.read_text()
        assert meta_robots(text) == "noindex, nofollow", f
        assert "Example records. Every paper, person and number here is invented." in text, f
    for f in html_files(root):
        if not f.is_relative_to(root / "example"):
            assert 'class="banner"' not in f.read_text(), f


def test_no_invented_record_outside_example(built):
    root, _ = built
    a = load_archive(EXAMPLE)
    needles = {v.title for p in a.papers.values() for v in p.versions} | {s.statement for s in a.sketches.values()}
    # SPEC.md's own examples use paper:4471 and u/kestrel, so identifiers alone are not a
    # leak. Titles, statements and invented names are.
    needles |= {"R. Nakamura", "S. Haddad", "survey-scout"}
    for f in root.rglob("*"):
        if f.is_file() and f.suffix in (".html", ".xml", ".txt") and not f.is_relative_to(root / "example"):
            text = " ".join(f.read_text().split())
            for n in needles:
                assert " ".join(n.split()) not in text, (f, n)
    sitemap = (root / "sitemap.xml").read_text()
    assert "/example/" not in sitemap and "<loc>https://garleak.org/</loc>" in sitemap


def test_listings_and_diffs_carry_noindex(built):
    root, _ = built
    for f in html_files(root):
        rel = "/" + f.relative_to(root).as_posix()
        if re.match(r"^(/example)?/(list|sketch/list|graduated|diff)/", rel):
            assert "noindex" in meta_robots(f.read_text()), rel


def test_noindex_rules_for_a_populated_archive(built_as_root):
    root = built_as_root
    assert meta_robots(page(root, "/abs/4502/")) == "noindex, follow"       # current version T0
    assert meta_robots(page(root, "/abs/4471v1.0/")) == "noindex, follow"   # T0 version
    assert meta_robots(page(root, "/abs/4471/")) == ""                     # T3, indexable
    assert meta_robots(page(root, "/abs/4471v3.0/")) == ""
    assert meta_robots(page(root, "/list/phys.astro/recent/")) == "noindex, follow"
    assert meta_robots(page(root, "/abs/4512/")) == "noindex, follow"       # gated below T1
    sitemap = (root / "sitemap.xml").read_text()
    assert "/abs/4471/" in sitemap and "/abs/4471v3.0/" in sitemap
    assert "/abs/4502/" not in sitemap and "/abs/4471v3/" not in sitemap   # series pages point elsewhere
    assert check_site(root).errors == []


def test_gated_content_is_hidden_below_t1(built_as_root):
    root = built_as_root
    title = "Timing of a second antiemetic dose"
    gated = page(root, "/abs/4512/")
    assert title not in gated and "gated category" in gated
    assert not (root / "text" / "4512v1.0").exists() and not (root / "src" / "4512v1.0").exists()
    for f in root.rglob("*"):
        if f.is_file() and f.suffix in (".html", ".xml"):
            assert title not in f.read_text(), f


def test_gated_paper_appears_at_t1(tmp_path, config):
    m = ArchiveMaker(tmp_path / "archive")
    m.paper(9, [("1.0", "initial", "2026-09-10", BODY)], category="med.clinical", families=())
    out = tmp_path / "_site"
    cfg = dict(config, archive=m.root, example_archive=None)
    Builder(cfg, out, BUILD_DATE).build()
    assert "Test paper 9" not in page(out, "/abs/9/")
    m.verification(9, "9-01", "1.0", "T1", "2026-09-11")
    Builder(cfg, out, BUILD_DATE).build()
    text = page(out, "/abs/9/")
    assert "Test paper 9" in text and meta_robots(text) == ""


def test_every_issued_identifier_resolves(built):
    root, _ = built
    a = load_archive(EXAMPLE)
    for n, p in a.papers.items():
        paths = [f"/example/abs/{n}/", f"/example/abs/paper:{n}/"]
        for v in p.versions:
            paths += [f"/example/abs/{n}v{v.number}/", f"/example/abs/{n}v{v.number.major}/",
                      f"/example/abs/paper:{n}v{v.number}/"]
        for path in paths:
            assert page(root, path), path
    for n in a.sketches:
        for path in (f"/example/sketch/{n}/", f"/example/sketch/{n}v1/", f"/example/sketch/{n}v1.0/",
                     f"/example/abs/sketch:{n}v1.0/"):
            assert page(root, path), path


def test_never_issued_ids_reach_a_page_that_says_so(built):
    root, _ = built
    text = page(root, "/404.html")
    data = json.loads(re.search(r'<script type="application/json" id="issued">(.*?)</script>', text, re.S)[1])
    assert data[""] == {"paper": {}, "sketch": {}}
    assert data["/example"]["paper"]["4471"] == ["1.0", "1.1", "2.0", "3.0"]
    assert "never issued" in text and 'src="/static/notfound.js"' in text


def test_series_pages_point_to_the_exact_version(built):
    root, _ = built
    text = page(root, "/example/abs/4420v1/")
    assert '<link rel="canonical" href="https://garleak.org/example/abs/4420v1.2/">' in text


def test_empty_real_archive_shows_invitations(built):
    root, _ = built
    listing = page(root, "/list/phys.astro/recent/")
    assert "What belongs here" in listing and 'class="rows"' not in listing
    assert "Submit it here as a paper" in page(root, "/")
    assert "Nothing is waiting to be checked" in page(root, "/verify/")
    assert "The first Graduated versions will be listed here" in page(root, "/graduated/")


def test_pages_work_without_javascript(built):
    """Scripts only enhance: no inline handlers, and every page's content is in its HTML."""
    root, _ = built
    for f in html_files(root):
        text = f.read_text()
        assert not re.search(r"\son[a-z]+=", text), f
    abs_page = page(root, "/example/abs/4471/")
    assert "/example/diff/4471/1.0..3.0/" in abs_page  # every diff is linked without the script
    assert sum(f.stat().st_size for f in root.rglob("*.js")) < 6000


def test_phase1_identity_is_stated(built):
    root, _ = built
    sentence = "Your GitHub account is public, and so is the ORCID link that verifies it."
    for path in ("/submit/", "/about/", "/terms/"):
        assert sentence in page(root, path), path
    assert "Nobody else does" not in page(root, "/")


def test_example_listing_matches_the_prototype(built):
    root, _ = built
    text = page(root, "/example/list/phys.astro/recent/")
    assert "New papers (showing 7 of 7 entries)" in text and "New versions (showing 4 of 4 entries)" in text
    assert "W2 A1 declared" in text and "4471v3" in text and "4420v1.2" in text


def test_build_date_is_used_for_the_real_archive(tmp_path, config):
    out = tmp_path / "_site"
    Builder(config, out, dt.date(2027, 1, 5)).build()
    assert "Recent submissions" in page(out, "/list/phys.astro/recent/")
    assert (out / "list" / "phys.astro" / "2027-01" / "index.html").is_file()
    assert "/list/phys.astro/recent/" in page(out, "/list/phys.astro/new/")


def test_recent_listing_is_not_a_date_window(tmp_path, config, maker):
    """Entries older than a few days still list. The listing shows the newest entries."""
    maker.paper(1, [("1.0", "initial", "2025-01-05", BODY)])
    maker.paper(2, [("1.0", "initial", "2026-08-01", BODY)])
    maker.sketch(3, "An old idea worth testing.", date="2025-02-02")
    out = tmp_path / "_site"
    Builder(dict(config, archive=maker.root, example_archive=None), out, dt.date(2026, 9, 21)).build()
    papers = page(out, "/list/phys.astro/recent/")
    assert "Test paper 1" in papers and "Test paper 2" in papers
    assert "An old idea worth testing." in page(out, "/sketch/list/phys.astro/recent/")
