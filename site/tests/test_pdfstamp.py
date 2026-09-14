# SPDX-License-Identifier: AGPL-3.0-or-later
"""The PDF stamp (SPEC §9.3): a notice on every page, tested on a generated fixture."""

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas

from garleak_site.pdfstamp import stamp_pdf

LINES = [
    "Not peer reviewed. Garleak paper:1v2.0, stage T2 as of 2026-09-14. "
    "Admission is not endorsement; screening checks scope and form only.",
    "Current record: https://garleak.org/abs/1v2.0/",
]


def make_pdf(path, sizes):
    c = canvas.Canvas(str(path))
    for i, size in enumerate(sizes):
        c.setPageSize(size)
        c.drawString(72, size[1] - 72, f"Page {i + 1} of a test paper")
        c.showPage()
    c.save()


def test_every_page_is_stamped(tmp_path):
    src, dst = tmp_path / "in.pdf", tmp_path / "out.pdf"
    make_pdf(src, [letter, A4, (400, 300)])
    assert stamp_pdf(src, dst, LINES) == 3
    reader = PdfReader(str(dst))
    assert len(reader.pages) == 3
    for i, pg in enumerate(reader.pages):
        text = " ".join(pg.extract_text().split())
        assert "Not peer reviewed. Garleak paper:1v2.0, stage T2 as of 2026-09-14." in text
        assert "Admission is not endorsement" in text
        assert f"Page {i + 1} of a test paper" in text


def test_example_pdf_is_stamped_in_the_build(built):
    root, _ = built
    reader = PdfReader(str(root / "example" / "pdf" / "4471v3.0.pdf"))
    assert len(reader.pages) == 2
    for pg in reader.pages:
        text = " ".join(pg.extract_text().split())
        assert "Not peer reviewed. Garleak paper:4471v3.0, stage T3 as of 2026-09-14" in text
        assert "Example record" in text
