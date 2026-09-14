# SPDX-License-Identifier: AGPL-3.0-or-later
"""Make the garlic mark and favicon set from the source raster.

Run once when the source mark changes; the outputs are committed under
garleak_site/static/. Needs Pillow (installed with reportlab).

    .venv/bin/python scripts/make_mark.py /path/to/garleak_logo.jpeg
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

STATIC = Path(__file__).resolve().parents[1] / "garleak_site" / "static"


def knock_out_background(img: Image.Image) -> Image.Image:
    """Turn the cream ground transparent, un-mixing anti-aliased edge pixels."""
    img = img.convert("RGB")
    w, h = img.size
    corners = [img.getpixel(p) for p in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]]
    bg = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    out = Image.new("RGBA", img.size)
    src = img.load()
    dst = out.load()
    lo, hi = 10.0, 60.0
    for y in range(h):
        for x in range(w):
            r, g, b = src[x, y]
            d = max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2]))
            a = min(1.0, max(0.0, (d - lo) / (hi - lo)))
            if a <= 0:
                dst[x, y] = (0, 0, 0, 0)
                continue
            # un-premultiply against the background so edges do not keep a cream halo
            ch = []
            for c, cb in zip((r, g, b), bg):
                v = (c - (1 - a) * cb) / a
                ch.append(int(round(min(255, max(0, v)))))
            dst[x, y] = (ch[0], ch[1], ch[2], int(round(a * 255)))
    return out


def square_crop(img: Image.Image, margin: float = 0.04) -> Image.Image:
    bbox = img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    img = img.crop(bbox)
    side = int(max(img.size) * (1 + 2 * margin))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def main(src: str) -> None:
    mark = square_crop(knock_out_background(Image.open(src)))
    STATIC.mkdir(parents=True, exist_ok=True)
    for px in (40, 80):
        mark.resize((px, px), Image.LANCZOS).save(STATIC / f"mark-{px}.png", optimize=True)
    mark.resize((32, 32), Image.LANCZOS).save(STATIC / "favicon-32.png", optimize=True)
    mark.resize((48, 48), Image.LANCZOS).save(
        STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]
    )
    touch = Image.new("RGBA", (180, 180), (255, 255, 255, 255))
    inner = mark.resize((150, 150), Image.LANCZOS)
    touch.paste(inner, (15, 15), inner)
    touch.convert("RGB").save(STATIC / "apple-touch-icon.png", optimize=True)
    for p in sorted(STATIC.glob("*.png")) + [STATIC / "favicon.ico"]:
        print(p.name, p.stat().st_size, "bytes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Downloads" / "garleak_logo.jpeg"))
