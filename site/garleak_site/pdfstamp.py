# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stamp a notice on every page of a PDF (SPEC §9.3).

PDFs travel without the web page, so the stamp goes inside the file, as real text at the
foot of each page. It is made at every build, so a stage change reaches the stamp with
the next build.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

FONT = "Helvetica"
SIZE = 6.5
LEADING = 8.5
MARGIN = 18


def _overlay(width: float, height: float, left: float, bottom: float, lines: list[str]):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(left + width, bottom + height))
    avail = width - 2 * MARGIN
    size = SIZE
    while size > 4 and max(stringWidth(ln, FONT, size) for ln in lines) > avail:
        size -= 0.25
    band = 8 + LEADING * len(lines)
    c.setFillColorRGB(1, 1, 1)
    c.rect(left, bottom, width, band, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont(FONT, size)
    y = bottom + band - LEADING
    for ln in lines:
        c.drawString(left + MARGIN, y, ln)
        y -= LEADING
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def stamp_pdf(src: Path, dst: Path, lines: list[str]) -> int:
    """Write `src` to `dst` with `lines` at the foot of every page. Returns the page count."""
    writer = PdfWriter(clone_from=str(src))
    for page in writer.pages:
        box = page.mediabox
        page.merge_page(_overlay(float(box.width), float(box.height), float(box.left), float(box.bottom), lines))
    writer.add_metadata({"/Subject": lines[0]})
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as f:
        writer.write(f)
    return len(writer.pages)
