# SPDX-License-Identifier: AGPL-3.0-or-later
"""The automated first pass (SPEC §8.3). It may admit or flag, and never rejects: only a
moderator rejects (§8.3.2). Every check reports an id and a version (§8.3.4). The
assistance classifier plays no part (§8.3.3)."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from garleak_archive.models import Archive

CHECK_VERSION = "1"
WORD = re.compile(r"\w+", re.UNICODE)
PLACEHOLDER = re.compile(r"lorem ipsum|\[insert\b|\bTBD\b|\bXXX\b|<placeholder>", re.I)
TEST_ONLY = re.compile(r"^\s*(test|testing|asdf+|hello( world)?|foo|bar|qwerty)\s*[.!]?\s*$", re.I)
TERMINAL = re.compile(r"[.!?:;)\]\"'`*_$]\s*$")


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text or "").casefold().split())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def tokens(text: str) -> list[str]:
    return WORD.findall(normalize(text))


def shingles(toks: list[str], k: int) -> set[tuple[str, ...]]:
    if len(toks) < k:
        return {tuple(toks)} if toks else set()
    return {tuple(toks[i:i + k]) for i in range(len(toks) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Match:
    ref: str
    score: float
    exact: bool


def best_match(text: str, corpus: list[tuple[str, str]], k: int) -> Match | None:
    """The closest earlier text by content hash, then by shingle Jaccard similarity."""
    h = content_hash(text)
    mine = shingles(tokens(text), k)
    best: Match | None = None
    for ref, other in corpus:
        if content_hash(other) == h:
            return Match(ref, 1.0, True)
        s = jaccard(mine, shingles(tokens(other), k))
        if best is None or s > best.score:
            best = Match(ref, s, False)
    return best


def paper_corpus(archive: Archive, exclude: int | None = None) -> list[tuple[str, str]]:
    out = []
    for p in archive.papers.values():
        if p.number == exclude:
            continue
        for v in p.versions:
            out.append((f"paper:{p.number}v{v.number}", f"{v.title}\n{v.abstract}\n{v.body}"))
    return out


def sketch_corpus(archive: Archive) -> list[tuple[str, str]]:
    return [(f"sketch:{s.number}", f"{s.statement}\n{s.detail}") for s in archive.sketches.values()]


def _last_prose_line(body: str) -> str:
    in_fence = False
    last = ""
    for ln in body.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not s or s.startswith(("#", "|", "$$", "[", "-", "*", ">")) or re.match(r"^\d+\.\s", s):
            continue
        last = s
    return last


def paper_flags(title: str, abstract: str, body: str, cfg: dict) -> list[str]:
    """Heuristics for empty, truncated or placeholder submissions."""
    sc = cfg["screening"]
    out = []
    n = len(tokens(body))
    if n < sc["min_paper_body_words"]:
        out.append(f"the body has {n} words, fewer than {sc['min_paper_body_words']}")
    na = len(tokens(abstract))
    if na < sc["min_abstract_words"]:
        out.append(f"the abstract has {na} words, fewer than {sc['min_abstract_words']}")
    if body.count("```") % 2:
        out.append("a code block is opened and never closed")
    if body.count("$$") % 2:
        out.append("a display equation is opened and never closed")
    last = _last_prose_line(body)
    if last and not TERMINAL.search(last):
        out.append("the body seems to stop mid-sentence")
    if PLACEHOLDER.search(body) or PLACEHOLDER.search(abstract):
        out.append("it contains placeholder text")
    if TEST_ONLY.match(title) or TEST_ONLY.match(abstract):
        out.append("the title or abstract reads like a test post")
    return out


def sketch_flags(statement: str, detail: str, cfg: dict) -> list[str]:
    sc = cfg["screening"]
    out = []
    n = len(tokens(statement))
    if n < sc["min_sketch_statement_words"]:
        out.append(f"the statement has {n} words, fewer than {sc['min_sketch_statement_words']}")
    if len(statement) > sc["max_sketch_statement_chars"]:
        out.append(f"the statement is longer than {sc['max_sketch_statement_chars']} characters; "
                   "put the rest in the detail")
    if TEST_ONLY.match(statement) or PLACEHOLDER.search(statement + " " + detail):
        out.append("it reads like a test post or placeholder")
    return out


def gated_hits(text: str, keywords: list[str]) -> list[str]:
    t = normalize(text)
    return sorted({k for k in keywords if re.search(r"(?<!\w)" + re.escape(k.casefold()) + r"(?!\w)", t)})


def calibration_sampled(issue: int, digest: str, rate: float) -> bool:
    """A deterministic draw, so a recheck of the same content gives the same answer."""
    h = int(hashlib.sha256(f"{issue}:{digest}".encode()).hexdigest()[:8], 16)
    return h % 10000 < round(rate * 10000)


def numbers_math_refs(text: str) -> tuple[set, set, set]:
    nums = set(re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text))
    math = set(re.findall(r"\$[^$\n]+\$", text))
    tables = {ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")}
    return nums, math, tables


def bump_flags(parent_body: str, new_body: str, parent_bib: str, new_bib: str) -> list[str]:
    """SPEC §6.3.6: flag a minor version that touches numbers, mathematics, tables or
    references. A flag, never a refusal: the maintainer states the bump type."""
    a, b = numbers_math_refs(parent_body), numbers_math_refs(new_body)
    out = []
    if a[0] != b[0]:
        out.append("numbers")
    if a[1] != b[1]:
        out.append("mathematics")
    if a[2] != b[2]:
        out.append("tables")
    if (parent_bib or "").strip() != (new_bib or "").strip():
        out.append("the reference list")
    return out


# ---------------------------------------------------------------- citecheck


@dataclass
class CitecheckResult:
    status: str  # pass | review | incomplete | skipped | error
    detail: str
    version: str = ""
    total: int = 0
    flagged: int = 0


def run_citecheck(bib_text: str, executable: str | None, timeout: int, max_refs: int) -> CitecheckResult:
    """Run the standalone citecheck CLI on the submitted references. citecheck stays a
    separate package (CLAUDE.md), so it is called as a program, never imported."""
    if not executable:
        return CitecheckResult("skipped", "citecheck is not installed here, so the references were not checked")
    with tempfile.TemporaryDirectory(prefix="garleak-citecheck-") as d:
        bib = Path(d) / "refs.bib"
        bib.write_text(bib_text, encoding="utf-8")
        out = Path(d) / "report.json"
        cmd = [executable, str(bib), "--json", str(out), "--exit-zero", "-q", "--max-refs", str(max_refs)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except FileNotFoundError:
            return CitecheckResult("skipped", "citecheck is not installed here, so the references were not checked")
        except subprocess.TimeoutExpired:
            return CitecheckResult("incomplete", f"citecheck did not finish within {timeout} seconds")
        if proc.returncode == 2 or not out.is_file():
            return CitecheckResult("error", "citecheck could not read the reference list")
        try:
            report = json.loads(out.read_text(encoding="utf-8"))
            summ = report["summary"]
            status = summ["prescreen"]["status"]
            return CitecheckResult(status, summ.get("headline", ""), str(report["tool"]["version"]),
                                   int(summ.get("n_references", 0)), len(summ.get("flagged_indices") or []))
        except (ValueError, KeyError, TypeError):
            return CitecheckResult("error", "citecheck wrote a report this version cannot read")
