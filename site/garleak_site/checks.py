# SPDX-License-Identifier: AGPL-3.0-or-later
"""Checks over a built site, run in CI and by the tests.

    links      every internal href, src, srcset, form action, refresh target and CSS url()
               resolves to a file, and every #fragment to an id in it
    markup     doctype, lang, a title, balanced tags, unique ids
    dashes     no em dash anywhere in the output
    branding   no "arxiv" string and no color near arXiv's maroon
    wording    no "published" or "real paper", and "peer review", "journal" and "preprint
               server" only in sentences that deny them; no LLM-marker words in site copy
    indexing   noindex on /example/, listings, diffs and T0 or gated pages; the banner on
               every /example/ page; the sitemap lists no noindex page
    boundary   no invented record appears outside /example/
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
EM_DASH = re.compile("—|&mdash;|&#8212;|&#x2014;", re.I)
NEGATION = re.compile(r"\b(not|never|no|nor|nothing|without|narrower|cannot|isn't|doesn't)\b", re.I)
NEEDS_NEGATION = re.compile(r"peer review|journal|preprint server", re.I)
FORBIDDEN = re.compile(r"\bpublished\b|\breal paper", re.I)
MARKERS = re.compile(r"\b(delve|underscore|pivotal|leverag\w*|robust|seamless\w*|comprehensive|intricate|"
                     r"meticulous\w*|crucial|showcase\w*|streamline\w*|harness\w*|landscape|realm|foster\w*)\b", re.I)
HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
MAROON = "b31b1b"
MAROON_DELTA_E = 15.0
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []
        self.ids: set[str] = set()
        self.dup_ids: set[str] = set()
        self.stack: list[str] = []
        self.recflags: list[bool] = []
        self.rec = 0  # depth inside elements marked data-record (text from records)
        self.chrome: list[str] = []
        self.errors: list[str] = []
        self.meta: dict[str, str] = {}
        self.text: list[str] = []
        self.skip = 0
        self.lang: str | None = None
        self.title = ""
        self.in_title = False
        self.doctype = False
        self.banner = False

    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype"):
            self.doctype = True

    def handle_starttag(self, tag: str, attrs) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang")
        if "id" in a:
            (self.dup_ids if a["id"] in self.ids else self.ids).add(a["id"])
        for key in ("href", "src", "action"):
            if key in a and not (tag == "link" and a.get("rel") == "canonical"):
                self.urls.append(a[key])
        if "srcset" in a:
            self.urls.extend(part.strip().split()[0] for part in a["srcset"].split(",") if part.strip())
        if tag == "meta":
            if a.get("name"):
                self.meta[a["name"]] = a.get("content", "")
            if a.get("http-equiv", "").lower() == "refresh":
                m = re.search(r"url=(.+)$", a.get("content", ""), re.I)
                if m:
                    self.urls.append(m[1].strip())
        if "banner" in a.get("class", "").split():
            self.banner = True
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag not in VOID:
            self.stack.append(tag)
            flag = "data-record" in a
            self.recflags.append(flag)
            self.rec += flag

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self._pop()

    def _pop(self) -> str:
        self.rec -= self.recflags.pop()
        return self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False
        if self.stack and self.stack[-1] == tag:
            self._pop()
            return
        self.errors.append(f"</{tag}> does not close <{self.stack[-1] if self.stack else 'nothing'}>")
        if tag in self.stack:
            while self._pop() != tag:
                pass

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data
        if not self.skip:
            self.text.append(data)
            if not self.rec and not self.in_title:
                self.chrome.append(data)

    @property
    def body_text(self) -> str:
        """All visible text, record content included."""
        return " ".join(" ".join(self.text).split())

    @property
    def chrome_text(self) -> str:
        """The site's own copy: text outside elements marked data-record and outside <title>."""
        return " ".join(" ".join(self.chrome).split())


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    pages: int = 0
    files: int = 0
    bytes: int = 0
    js_bytes: int = 0

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    @property
    def ok(self) -> bool:
        return not self.errors


def _lab(hexcode: str) -> tuple[float, float, float]:
    rgb = [int(hexcode[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    x = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(a: str, b: str) -> float:
    return math.dist(_lab(a.lower()), _lab(b.lower()))


def _rel(root: Path, p: Path) -> str:
    return "/" + p.relative_to(root).as_posix()


def _resolve(root: Path, page: Path, url: str) -> tuple[Path, str] | None:
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or url.startswith(("mailto:", "data:", "javascript:")):
        return None
    path = unquote(parts.path)
    if not path:
        return page, parts.fragment
    target = root / path.lstrip("/") if path.startswith("/") else page.parent / path
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target, parts.fragment


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text)


def invented_strings(example_archive: Path) -> list[str]:
    """Titles and statements of every invented record, to find leaks outside /example/."""
    from garleak_archive.loader import load_archive

    a = load_archive(example_archive)
    out = {v.title for p in a.papers.values() for v in p.versions}
    out |= {s.statement for s in a.sketches.values()}
    return sorted(" ".join(x.split()) for x in out if len(x) > 20)


def check_site(root: Path, example_archive: Path | None = None) -> Report:
    root = Path(root)
    r = Report()
    parsed: dict[Path, _Page] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        r.files += 1
        r.bytes += p.stat().st_size
        if p.suffix == ".js":
            r.js_bytes += p.stat().st_size
        if p.suffix in (".html", ".xml", ".txt", ".css", ".js") and not p.is_relative_to(root / "pagefind"):
            raw = p.read_text(encoding="utf-8")
            where = _rel(root, p)
            if EM_DASH.search(raw):
                r.err(where, "contains an em dash")
            if "arxiv" in raw.lower() and where != "/spec/index.html" and not where.startswith("/blog/"):
                r.err(where, 'contains the string "arxiv"')
            if p.suffix in (".css", ".html"):
                for m in HEX.finditer(raw):
                    if delta_e(m[1], MAROON) < MAROON_DELTA_E:
                        r.err(where, f"color #{m[1]} is too close to arXiv's maroon")
            if p.suffix == ".css":
                for m in CSS_URL.finditer(raw):
                    res = _resolve(root, p, m[1])
                    if res and not res[0].is_file():
                        r.err(where, f"url({m[1]}) does not resolve")
            if p.suffix == ".html":
                pg = _Page()
                pg.feed(raw)
                pg.close()
                parsed[p] = pg
                r.js_bytes += sum(len(s) for s in re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>(.*?)</script>", raw, re.S))

    for p, pg in parsed.items():
        where = _rel(root, p)
        r.pages += 1
        if not pg.doctype:
            r.err(where, "no doctype")
        if not pg.lang:
            r.err(where, "no lang on <html>")
        if not pg.title.strip():
            r.err(where, "empty <title>")
        for e in pg.errors:
            r.err(where, e)
        if pg.stack:
            r.err(where, f"unclosed <{'>, <'.join(pg.stack)}>")
        for d in pg.dup_ids:
            r.err(where, f'duplicate id "{d}"')
        for url in pg.urls:
            res = _resolve(root, p, url)
            if res is None:
                continue
            target, frag = res
            if not target.is_file():
                r.err(where, f"link {url} does not resolve")
            elif frag and target.suffix == ".html":
                tp = parsed.get(target)
                if tp is not None and frag not in tp.ids:
                    r.err(where, f"link {url} names a missing #{frag}")

        robots = pg.meta.get("robots", "").replace(" ", "")
        example = where.startswith("/example/")
        if example:
            if robots != "noindex,nofollow":
                r.err(where, "an example page needs noindex, nofollow")
            if not pg.banner:
                r.err(where, "an example page needs the banner")
        elif pg.banner:
            r.err(where, "the example banner appears outside /example/")
        path = where.removeprefix("/example")
        if re.match(r"^/(list|sketch/list|graduated|diff)/", path) and "noindex" not in robots:
            r.err(where, "listings and diffs need noindex")
        stage = pg.meta.get("garleak:stage", "")
        if pg.meta.get("garleak:type") == "paper" and stage == "T0" and "noindex" not in robots:
            r.err(where, "a T0 paper page needs noindex")
        if pg.meta.get("garleak:gated") == "true" and stage in ("", "T0", "N0", "N1", "N2", "N3") and "noindex" not in robots:
            r.err(where, "gated content below T1 needs noindex")

        if where != "/spec/index.html" and not where.startswith("/blog/"):
            # Wording rules bind the site's own copy, not what submitters wrote.
            text = pg.chrome_text
            for s in _sentences(text):
                if FORBIDDEN.search(s):
                    r.err(where, f"forbidden wording in: {s[:120]}")
                if NEEDS_NEGATION.search(s) and not NEGATION.search(s):
                    r.err(where, f"claim-like use of a restricted term in: {s[:120]}")
            for mk in MARKERS.finditer(text):
                r.err(where, f'marker word "{mk[0]}"')

    sitemap = root / "sitemap.xml"
    if sitemap.is_file():
        for loc in re.findall(r"<loc>(.*?)</loc>", sitemap.read_text()):
            path = urlsplit(html.unescape(loc)).path
            if path.startswith("/example/"):
                r.err("/sitemap.xml", f"lists an example page {path}")
            target = root / path.lstrip("/")
            target = target / "index.html" if path.endswith("/") else target
            pg = parsed.get(target)
            if pg is None:
                r.err("/sitemap.xml", f"lists {path}, which does not exist")
            elif "noindex" in pg.meta.get("robots", ""):
                r.err("/sitemap.xml", f"lists {path}, which carries noindex")
    else:
        r.err("/", "no sitemap.xml")
    for name in ("robots.txt", "404.html", "CNAME"):
        if not (root / name).is_file():
            r.err("/", f"no {name}")

    if example_archive is not None:
        needles = invented_strings(example_archive)
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix not in (".html", ".xml", ".txt") or p.is_relative_to(root / "example"):
                continue
            text = parsed[p].body_text if p in parsed else " ".join(html.unescape(p.read_text(encoding="utf-8")).split())
            for n in needles:
                if n in text:
                    r.err(_rel(root, p), f"invented record outside /example/: {n[:60]}")
    return r
