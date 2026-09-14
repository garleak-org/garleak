# SPDX-License-Identifier: AGPL-3.0-or-later
"""PDFs are served only in their stamped form, and the ones that cannot carry noindex are
kept away from crawlers through robots.txt (GitHub Pages cannot send X-Robots-Tag)."""


def _pdf_urls(root):
    return sorted("/" + p.relative_to(root).as_posix() for p in root.rglob("*.pdf"))


def test_only_stamped_pdfs_are_published(built):
    root, _ = built
    urls = _pdf_urls(root)
    assert urls, "the example archive should produce at least one stamped PDF"
    # The raw upload must never be copied next to the source files.
    assert not [u for u in urls if "/src/" in u], urls
    assert all("/pdf/" in u for u in urls), urls


def test_unindexable_pdfs_are_disallowed(built):
    root, _ = built
    robots = (root / "robots.txt").read_text(encoding="utf-8")
    for url in _pdf_urls(root):
        if url.startswith("/example/"):
            assert f"Disallow: {url}\n" in robots, url
    assert robots.index("Disallow:") < robots.index("Allow: /")
