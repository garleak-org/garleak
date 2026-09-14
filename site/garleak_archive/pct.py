# SPDX-License-Identifier: AGPL-3.0-or-later
"""`pct_original`, algorithm po-1 (SPEC §6.6).

pct_original is the share of token positions in version n that lie inside at least one
k-token run (k = 5) that also occurs in v1.0. pct_v1_retained is the same computed in
the other direction. Both depend only on sets of k-grams, so there is no tie-breaking and
no dependence on a diff implementation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

ALGORITHM = "po-1"
DEFAULT_K = 5
EXTRACTOR = "garleak-md-rendition"
EXTRACTOR_VERSION = "1"

_CONTROL_WORD = re.compile(r"\\([A-Za-z]+)")


def normalize(text: str) -> str:
    """Step 2: NFKC, case folding, LaTeX control words replaced by their names."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return _CONTROL_WORD.sub(lambda m: " " + m[1] + " ", text)


def tokenize(text: str) -> list[str]:
    """Step 3: maximal runs of characters in Unicode categories L and N."""
    tokens: list[str] = []
    cur: list[str] = []
    for ch in normalize(text):
        if unicodedata.category(ch)[0] in "LN":
            cur.append(ch)
        elif cur:
            tokens.append("".join(cur))
            cur = []
    if cur:
        tokens.append("".join(cur))
    return tokens


def shingles(tokens: list[str], k: int) -> set[tuple[str, ...]]:
    """Step 4: the set of k-token sequences at consecutive positions."""
    return {tuple(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def covered_positions(tokens: list[str], reference: set[tuple[str, ...]], k: int) -> int:
    """Step 5: count positions covered by at least one k-gram found in `reference`."""
    covered = [False] * len(tokens)
    for i in range(len(tokens) - k + 1):
        if tuple(tokens[i : i + k]) in reference:
            for j in range(i, i + k):
                covered[j] = True
    return sum(covered)


def round_half_up(numerator: int, denominator: int) -> int:
    """100 * numerator / denominator rounded to an integer, halves up, in exact arithmetic."""
    return (200 * numerator + denominator) // (2 * denominator)


@dataclass(frozen=True)
class PctResult:
    value: int | None          # displayed pct_original, None means "n/a"
    covered: int               # C
    tokens: int                # |n|
    retained_value: int | None  # displayed pct_v1_retained
    retained_covered: int
    v1_tokens: int
    k: int = DEFAULT_K
    algorithm: str = ALGORITHM
    extractor: str = f"{EXTRACTOR}@{EXTRACTOR_VERSION}"

    def display(self) -> str:
        return "n/a" if self.value is None else f"{self.value}%"


def po1(v1_text: str, vn_text: str, k: int = DEFAULT_K, *, is_v1: bool = False) -> PctResult:
    """Compute po-1 for version n against v1.0, from their canonical renditions."""
    t1 = tokenize(v1_text)
    tn = tokenize(vn_text)
    if is_v1:
        n = len(tn)
        return PctResult(100 if n else None, n, n, 100 if n else None, n, n, k)
    c = covered_positions(tn, shingles(t1, k), k)
    rc = covered_positions(t1, shingles(tn, k), k)
    if not tn:
        value = None
    elif not t1:
        value = 0
    else:
        value = round_half_up(c, len(tn))
    retained = round_half_up(rc, len(t1)) if t1 else None
    return PctResult(value, c, len(tn), retained, rc, len(t1), k)


# ---------------------------------------------------------------- rendition (step 1)

_EXCLUDED_SECTIONS = re.compile(
    r"^(references|bibliography|acknowledg(e)?ments?|funding|works cited)\b", re.I
)
_FENCE = re.compile(r"^(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def rendition(title: str, abstract: str, body_markdown: str) -> str:
    """Canonical text rendition of a Markdown version.

    Includes the title, abstract, headings, body, captions and mathematics as source.
    Excludes the reference list, acknowledgments and funding sections, fenced and inline
    code, HTML comments, image targets, link targets, and citation, reference and label
    keys (§6.6.2 step 1).
    """
    lines_out: list[str] = []
    skip_level: int | None = None
    in_fence = False
    text = re.sub(r"<!--.*?-->", " ", body_markdown, flags=re.S)
    for line in text.splitlines():
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        h = _HEADING.match(line)
        if h:
            level = len(h[1])
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and _EXCLUDED_SECTIONS.match(h[2].strip()):
                skip_level = level
                continue
        if skip_level is not None:
            continue
        lines_out.append(line)
    body = "\n".join(lines_out)
    body = re.sub(r"`[^`]*`", " ", body)                        # inline code
    body = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", body)        # image -> caption
    body = re.sub(r"\[@[^\]]*\]", " ", body)                     # [@key] citations
    body = re.sub(r"(?<![\w@])@[A-Za-z][\w:.-]*", " ", body)      # bare @key
    body = re.sub(r"\\(cite[a-z]*|ref|eqref|label)\{[^}]*\}", " ", body)
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)          # link -> text
    return "\n".join([title or "", abstract or "", body])
