# SPDX-License-Identifier: AGPL-3.0-or-later
"""WCAG 2.x contrast of every text and UI token against the grounds it sits on.

Reads design/tokens.css so the table never drifts from the tokens. Prints a Markdown
table; exits 1 if a pair that must pass does not.

    .venv/bin/python scripts/contrast.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[2] / "design" / "tokens.css"

# (foreground, role, minimum, grounds). Minimum 4.5 is AA body text, 3.0 is AA for UI
# components and graphics that carry meaning (WCAG 1.4.11). None means exempt, with why.
GROUNDS = ["paper", "panel", "gold-wash"]
CHECKS = [
    ("ink", "body text", 4.5, GROUNDS + ["ins"]),
    ("ink-soft", "secondary text", 4.5, GROUNDS + ["ins"]),
    ("bronze", "links", 4.5, GROUNDS),
    ("flag", "warning text", 4.5, GROUNDS + ["flag-wash"]),
    ("rule-strong", "form control borders", 3.0, GROUNDS),
    ("s0", "stage glyph T0/N0", 3.0, GROUNDS),
    ("s1", "stage glyph T1/N1", 3.0, GROUNDS),
    ("s2", "stage glyph T2/N2", 3.0, GROUNDS),
    ("s3", "stage glyph T3/N3", 3.0, GROUNDS),
    ("s4", "stage glyph T4", 3.0, GROUNDS),
    ("gold", "identity (rule, mark, active underline)", None, GROUNDS),
    ("gold-pale", "pct_original bar fill", None, GROUNDS),
    ("rule", "hairlines", None, GROUNDS),
]
EXEMPT_WHY = {
    "gold": "decorative; the active nav item is also set in --ink at weight 600 with aria-current",
    "gold-pale": "supplementary; the percentage is printed beside every bar",
    "rule": "decorative separators; no information depends on them",
}


def tokens() -> dict[str, str]:
    text = TOKENS.read_text()
    return {m[1]: m[2] for m in re.finditer(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", text)}


def luminance(hex_: str) -> float:
    def ch(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main() -> int:
    t = tokens()
    print("| Token | Hex | Role | Min | " + " | ".join(f"on --{g}" for g in GROUNDS + ["ins", "flag-wash"]) + " |")
    print("|---|---|---|---|" + "---|" * (len(GROUNDS) + 2))
    bad = 0
    for fg, role, need, grounds in CHECKS:
        cells = []
        for g in GROUNDS + ["ins", "flag-wash"]:
            if g not in grounds:
                cells.append("")
                continue
            r = ratio(t[fg], t[g])
            ok = need is None or r >= need
            bad += 0 if ok else 1
            cells.append(f"{r:.2f}" + ("" if ok else " FAIL"))
        need_s = f"{need:.1f}" if need else "exempt"
        print(f"| --{fg} | `{t[fg]}` | {role} | {need_s} | " + " | ".join(cells) + " |")
    print()
    for k, why in EXEMPT_WHY.items():
        print(f"- `--{k}` exempt: {why}.")
    print(f"\nY (relative luminance) of the ramp: " + ", ".join(
        f"s{i} {luminance(t[f's{i}']):.3f}" for i in range(5)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
