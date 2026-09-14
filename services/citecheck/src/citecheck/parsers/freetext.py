# SPDX-License-Identifier: AGPL-3.0-or-later
"""Heuristic field extraction from one formatted reference (a \\bibitem body or a text line).

Astronomy bibliography styles (mnras, aasjournal) usually print no title, so the parser
aims for what is reliably there: identifiers, first-author surname, year, journal,
volume, and first page. Titles are taken only when the markup makes them clear.
"""

from __future__ import annotations

import re

from ..ids import arxiv_from_doi, extract_arxiv, extract_dois, parse_bibcode, pos_from_url
from ..journals import expand_macros, journal_key
from ..models import Reference
from ..textutil import fold, latex_to_text

YEAR = r"(?:1[89]\d\d|20\d\d)"

FLAG_PATTERNS = {
    "private_communication": r"priv(?:ate)?\.?\s*comm|personal communication",
    "in_preparation": r"\bin prep(?:aration)?\b|\bin prep\.",
    "submitted": r"\bsubmitted\b",
    "unpublished": r"\bunpublished\b",
    "in_press": r"\bin press\b|\baccepted\b",
    "thesis": r"\bph\.?\s?d\.?\b|\bthesis\b|\bdissertation\b",
    "software": r"\bsoftware\b|github\.com|gitlab|\bascl\b|source code library|\bzenodo\b|\bpython package\b",
    "website": r"https?://|\bwww\.|\burl\b|accessed",
    "proceedings": r"\bproc(?:eedings|\.)|\bconference\b|\bsymposium\b|\bworkshop\b|\bpos\b|\bbaas\b"
                   r"|aas meeting|\bspie\b|\biau\b|\bconf\.|\bcolloq",
    "book": r"\bpress\b|\bpublishing\b|\bpublisher\b|\beds?\.\s|\beditors?\b|\bbook\b|\bspringer\b"
            r"|\bwiley\b|univ(?:ersity)?\.? press|\bedition\b|\bed\.\)|\(eds?\.",
    "catalog": r"\bvizier\b|\bcatalog(?:ue)?\b|\bdata release\b|\bdr\d+\b",
}
NO_SEARCH_FLAGS = {"private_communication", "in_preparation", "unpublished"}
LOW_COVERAGE_FLAGS = {"thesis", "software", "website", "proceedings", "book", "catalog", "submitted",
                      "in_press"}

_COLLAB = re.compile(r"collaboration|consortium|\bteam\b|\bsurvey\b|\bproject\b|\bgroup\b|\bcollab\b",
                     re.I)
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def detect_flags(text: str) -> list[str]:
    f = fold(text)
    return [name for name, pat in FLAG_PATTERNS.items() if re.search(pat, f)]


def is_initial(tok: str) -> bool:
    t = tok.strip(",;")
    if not t:
        return True
    if t.lower().strip(".") in _SUFFIXES:
        return True
    if re.fullmatch(r"(?:[A-Z][a-z]?\.-?)+", t):  # W.  W.L.  Ch.  J.-P.
        return True
    core = t.replace(".", "").replace("-", "")
    return len(core) <= 2 and core[:1].isupper() and (len(core) == 1 or core[1:].isupper() or t.endswith("."))


def family_names(segment: str) -> tuple[list[str], str | None]:
    """Family names from an author segment such as 'W.L. Freedman and B.F. Madore'."""
    seg = re.sub(r"\bet\.?\s*al\.?", ",", segment)
    seg = re.sub(r"\s+(?:and|&|und|et)\s+", ",", seg)
    seg = seg.replace(";", ",")
    names: list[str] = []
    collab = None
    for chunk in seg.split(","):
        c = chunk.strip(" .:")
        if not c:
            continue
        if _COLLAB.search(c):
            collab = collab or c
            continue
        toks = c.split()
        if len(toks) > 5:
            break  # ran into a title or venue
        non_init = [t for t in toks if not is_initial(t)]
        if not non_init:
            continue
        if not is_initial(toks[0]) and all(is_initial(t) for t in toks[1:]):
            fam = toks[0]
        else:
            fam = non_init[-1]
        fam = fam.strip(".,;:()[]")
        if len(fam) < 2 or not fam[0].isalpha() or fold(fam) in {"and", "the", "in", "of"}:
            continue
        names.append(fam)
        if len(names) >= 30:
            break
    return names, collab


def _balanced_arg(s: str, start: int) -> tuple[str, int] | None:
    """s[start] must be '{'. Return (content, index after closing brace)."""
    if start >= len(s) or s[start] != "{":
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
    return None


def emph_groups(latex: str) -> list[str]:
    out = []
    for m in re.finditer(r"\\(?:emph|textit|textsl)\s*(?=\{)", latex):
        r = _balanced_arg(latex, m.end())
        if r:
            out.append(r[0])
    for m in re.finditer(r"\{\\(?:em|it|itshape|sl)\s+", latex):
        # {\em Title} : content until the brace that closes the group
        depth = 1
        i = m.end()
        while i < len(latex) and depth:
            if latex[i] == "{":
                depth += 1
            elif latex[i] == "}":
                depth -= 1
            i += 1
        out.append(latex[m.end():i - 1])
    return out


def bibinfo_fields(latex: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in re.finditer(r"\\bibinfo\s*\{(\w+)\}\s*(?=\{)", latex):
        r = _balanced_arg(latex, m.end())
        if r and m.group(1) not in fields:
            fields[m.group(1)] = r[0]
    return fields


_VENUE_PATTERNS = [
    # JHEP / JCAP: Astrophys. J. 919 (2021) 16
    re.compile(r"(?P<j>[A-Z][A-Za-z.&'\- ]{0,60}?)\.?\s+(?P<v>[A-Z]?\d{1,5}[A-Z]?)\s*\((?P<y>" + YEAR +
               r")\)\s*(?P<p>[A-Z]?\d+)"),
    # mnras / aasjournal: 2021, ApJ, 919, 16
    re.compile(r"(?P<y>" + YEAR + r")[a-z]?[,.]?\s+(?P<j>[A-Za-z&][^,\d]{0,70}?),\s*(?P<v>[A-Z]?\d{1,5}[A-Z]?),"
               r"\s*(?:p\.\s*|id\.?\s*|pp\.\s*)?(?P<p>[A-Z]?\d+)"),
    # Nature / Science: Nature 123, 456-460 (2020)
    re.compile(r"(?P<j>[A-Z][A-Za-z.&'\- ]{0,60}?)\s+(?P<v>\d{1,5}),\s*(?P<p>[A-Z]?\d+)(?:\s*[-\u2013]\s*\d+)?\s*"
               r"\((?P<y>" + YEAR + r")\)"),
    # proceedings series: in Astronomical Society of the Pacific Conference Series, Vol. 167, <title>, ed. X, 54
    re.compile(r"\bin\s+(?P<j>[A-Z][^,]{3,100}?),\s*Vol\.?\s*(?P<v>\d{1,5}),.*?[,\s](?P<p>[A-Z]?\d{1,6})\s*\.?\s*$"),
    # APA: Journal Name, 12(3), 45-67
    re.compile(r"(?P<j>[A-Z][A-Za-z.&'\- ]{2,80}?),\s*(?P<v>\d{1,5})(?:\s*\([\w\-\u2013]+\))?,\s*(?:pp?\.\s*)?"
               r"(?P<p>[A-Z]?\d+)"),
    # revtex: Phys. Rev. D 103, 083533 (2021)  (covered by Nature pattern) and ApJ 919:16
    re.compile(r"(?P<j>[A-Z][A-Za-z.&'\- ]{0,60}?)\s+(?P<v>\d{1,5}):\s*(?P<p>[A-Z]?\d+)"),
]


def _strip_ids(text: str) -> str:
    t = re.sub(r"https?://\S+", " ", text)
    t = re.sub(r"\bdoi\s*:?\s*10\.\S+", " ", t, flags=re.I)
    t = re.sub(r"10\.\d{4,9}/\S+", " ", t)
    t = re.sub(r"arxiv(?:\s*e-?prints?)?[\s,:.]*(?:p\.\s*)?(?:arxiv\s*:\s*)?\S*\d", " ", t, flags=re.I)
    t = re.sub(r"\[\s*\d{4}\.\d{4,5}(?:v\d+)?\s*\]", " ", t)
    t = re.sub(r"\[[a-z\-]+(?:\.[A-Z]{2})?\]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_reference(latex: str, *, index: int, source_format: str, key: str | None = None,
                    label: str | None = None) -> Reference:
    body = expand_macros(latex)
    dois = extract_dois(body)
    arxivs = extract_arxiv(body)
    text = latex_to_text(body)
    ref = Reference(index=index, raw=text, source_format=source_format, key=key)

    # identifiers
    doi = None
    for d in dois:
        a = arxiv_from_doi(d)
        if a:
            if a not in arxivs:
                arxivs.append(a)
            continue
        doi = doi or d
    ref.doi = doi
    ref.arxiv = arxivs[0] if arxivs else None
    m = re.search(r"adsabs\.harvard\.edu/(?:abs|cgi-bin/nph-bib_query\?bibcode=)/?([0-9]{4}[\w.&%]{15})", body)
    if m:
        from urllib.parse import unquote
        bc = unquote(m.group(1))
        if parse_bibcode(bc):
            ref.bibcode = bc
    if key and parse_bibcode(key):
        ref.bibcode_hint = key
    urls = re.findall(r"https?://[^\s{}\\]+", body)
    for u in urls:
        if "doi.org" in u or "arxiv.org" in u:
            continue
        ref.url = u.rstrip(".,;")
        break
    if pos_from_url(ref.url):
        ref.flags.append("pos")

    fields = bibinfo_fields(body)
    title = None
    reliable = False
    if "title" in fields:
        title, reliable = latex_to_text(fields["title"]), True
    if not title:
        for g in emph_groups(body):
            t = latex_to_text(g).strip(" ,.")
            words = t.split()
            if len(words) >= 2 and journal_key(t)[0] is None and not re.fullmatch(r"[\d\s]+", t):
                title, reliable = t, len(words) >= 4
                break
    if not title:
        q = re.search(r"[\"\u201c]([^\"\u201d]{12,}?)[,.]?[\"\u201d]", text)
        if q:
            title, reliable = q.group(1).strip(" ,."), True
    if not title:
        apa = re.search(r"\((" + YEAR + r")[a-z]?\)\.\s+([^.?!]{12,}[.?!])", text)
        if apa:
            title, reliable = apa.group(2).strip(" ."), False
    if not title or len(title) < 4:
        title = None
    ref.title = title
    ref.title_reliable = bool(title) and reliable

    stripped = _strip_ids(text)
    work = stripped.replace(title, " ") if title else stripped

    # venue
    for pat in _VENUE_PATTERNS:
        vm = pat.search(work)
        if not vm:
            continue
        j = vm.group("j").strip(" .,")
        # reject author lists caught as a journal ('et al', or bare initials like 'A.'); journal
        # names themselves often contain 'and' (Communications in Applied Mathematics and ...)
        # (abbreviated journals such as 'J. Mach. Learn. Res.' also contain bare initials, so
        # only the shape 'W. L. Freedman' counts as a name)
        looks_like_authors = re.search(r"\bet al\b", j) or re.fullmatch(
            r"(?:[A-Z]\.\s?-?){1,3}\s*[A-Z][a-z'\-]+(?:\s+(?:and|&)\s+.*)?", j)
        if not j or len(j) > 100 or (looks_like_authors and journal_key(j)[0] is None):
            continue
        if len(j.split()) > 12:
            continue
        ref.journal = j
        ref.volume = vm.group("v")
        ref.page = vm.group("p")
        try:
            yv = vm.group("y")
        except IndexError:
            yv = None
        if yv:
            ref.year = int(yv)
        break
    if "journal" in fields and not ref.journal:
        ref.journal = latex_to_text(fields["journal"])
    if "volume" in fields and not ref.volume:
        ref.volume = latex_to_text(fields["volume"])
    if "pages" in fields and not ref.page:
        ref.page = re.split(r"[-\u2013]", latex_to_text(fields["pages"]))[0].strip() or None
    if ref.journal and journal_key(ref.journal)[1]:
        ref.flags.append("journal_string_typo")

    # year
    if ref.year is None and "year" in fields:
        ym = re.search(YEAR, fields["year"])
        ref.year = int(ym.group(0)) if ym else None
    if ref.year is None:
        ym = re.search(r"\((" + YEAR + r")[a-z]?\)", work) or re.search(
            r"(?:^|[\s,(])(" + YEAR + r")[a-z]?(?=[\s,.;)]|$)", work)
        if ym:
            ref.year = int(ym.group(1))
    if ref.year is None and label:
        lm = re.search(YEAR, label)
        if lm:
            ref.year = int(lm.group(0))

    # authors: text before the title, or before the first year
    cut = len(text)
    if title and title in text:
        cut = text.index(title)
    else:
        ym = re.search(r"(?:^|[\s,(])(" + YEAR + r")[a-z]?(?=[\s,.;)])", text)
        if ym:
            cut = ym.start(1)
    seg = text[:cut].strip(" ,.(")
    if len(seg) > 400:
        seg = seg[:400]
    if "bibnamefont" in body:
        names = [latex_to_text(n) for n in re.findall(r"\\bibnamefont\s*\{([^{}]+)\}", body)]
        ref.authors = [n.split()[-1] for n in names if n.strip()]
    else:
        ref.authors, ref.collaboration = family_names(seg)
    if not ref.authors and not ref.collaboration and label:
        lab = latex_to_text(re.sub(r"\\protect\\citeauthoryear\{([^{}]*)\}.*", r"\1", label))
        lab = re.sub(r"\(.*", "", lab)
        ref.authors, ref.collaboration = family_names(lab)

    flags = detect_flags(text)
    ref.flags.extend(f for f in flags if f not in ref.flags)
    if ref.bibcode_hint and not (ref.volume and ref.page):
        bc = parse_bibcode(ref.bibcode_hint)
        if bc and bc.get("volume") and bc.get("page") and bc.get("year") == ref.year:
            ref.volume = ref.volume or bc["volume"]
            ref.page = ref.page or bc["page"]
    return ref
