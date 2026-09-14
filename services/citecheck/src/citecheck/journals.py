# SPDX-License-Identifier: AGPL-3.0-or-later
"""Journal-name normalization. Maps AAS macros and common spellings to a canonical key.

The canonical key is only used for soft agreement checks and for ADS bibstem queries.
Unknown journals fall back to token comparison, so the table does not need to be complete.
"""

from __future__ import annotations

import re

from .textutil import fold

# AAS / ADS BibTeX journal macros -> canonical key
AAS_MACROS = {
    "apj": "apj", "apjl": "apjl", "apjs": "apjs", "apjsupp": "apjs", "aj": "aj",
    "mnras": "mnras", "aap": "aa", "astap": "aa", "aaps": "aas_supp", "aapr": "aarv",
    "pasp": "pasp", "pasj": "pasj", "pasa": "pasa", "araa": "araa", "nat": "nature",
    "nature": "nature", "natastro": "natastro", "sci": "science", "science": "science",
    "prd": "prd", "prl": "prl", "pra": "pra", "prb": "prb", "prc": "prc", "pre": "pre",
    "jcap": "jcap", "physrep": "physrep", "ssr": "ssrv", "apss": "apss", "icarus": "icarus",
    "planss": "pss", "solphys": "solphys", "memsai": "memsai", "baas": "baas", "actaa": "acta",
    "aplett": "aplett", "caa": "chaa", "cjaa": "chjaa", "gca": "gca", "grl": "grl", "jgr": "jgr",
    "jqsrt": "jqsrt", "psj": "psj", "procspie": "spie", "rmxaa": "rmxaa", "na": "newa",
    "nar": "newar", "rnaas": "rnaas", "iaucirc": "iauc", "jrasc": "jrasc", "qjras": "qjras",
    "zap": "zap", "azh": "azh", "bain": "ban", "fcp": "fcp", "jcp": "jcp", "nphysa": "npa",
    "ao": "apopt", "skytel": "skytel", "mnassa": "mnassa", "apspr": "apspr",
}

# canonical key -> ADS bibstem
BIBSTEMS = {
    "apj": "ApJ", "apjl": "ApJL", "apjs": "ApJS", "aj": "AJ", "mnras": "MNRAS", "aa": "A&A",
    "pasp": "PASP", "pasj": "PASJ", "pasa": "PASA", "araa": "ARA&A", "nature": "Natur",
    "natastro": "NatAs", "science": "Sci", "prd": "PhRvD", "prl": "PhRvL", "jcap": "JCAP",
    "physrep": "PhR", "ssrv": "SSRv", "apss": "Ap&SS", "icarus": "Icar", "psj": "PSJ",
    "rnaas": "RNAAS", "aarv": "A&ARv", "newa": "NewA", "newar": "NewAR", "solphys": "SoPh",
    "acta": "AcA", "spie": "SPIE", "an": "AN", "galaxies": "Galax", "universe": "Univ",
    "epjc": "EPJC", "jhep": "JHEP", "cqg": "CQGra", "prx": "PhRvX", "natphys": "NatPh",
    "pss": "P&SS", "grl": "GeoRL", "jgr": "JGRA", "rmxaa": "RMxAA", "aas_supp": "A&AS",
    "memsai": "MmSAI", "baas": "BAAS", "aspc": "ASPC", "epjwc": "EPJWC",
}

# (regex over folded, punctuation-stripped name, canonical key); order matters (specific first)
_PATTERNS: list[tuple[str, str]] = [
    (r"^(?:the )?astrophysical journal,? letters?$|^astrophys(?:ical)? j(?:ournal)? lett(?:ers)?$"
     r"|^apj ?l(?:ett(?:ers)?)?$|^apjlett$", "apjl"),
    (r"^(?:the )?astrophysical journal,? supplement(?: series)?$|^astrophys(?:ical)? j(?:ournal)? supp?l"
     r"(?:ement)?(?: ser(?:ies)?)?$|^apjs(?:upp)?$", "apjs"),
    (r"^(?:the )?astrophysical journal$|^astrophys(?:ical)? j(?:ournal)?$|^apj$|^ap j$", "apj"),
    (r"^(?:the )?astronomical journal$|^astron(?:omical)? j(?:ournal)?$|^aj$", "aj"),
    (r"^monthly notices of (?:the )?(?:royal astronomical society|ras)(?: letters)?$"
     r"|^mon(?:thly)? not(?:ices)?\.? (?:of )?(?:the )?r(?:oy(?:al)?)?\.? astron(?:omical)?\.? soc(?:iety)?"
     r"(?: lett(?:ers)?)?$|^mnras ?l?$", "mnras"),
    (r"^astronomy (?:and |& |)astrophysics$|^astron(?:omy)? (?:and )?astrophys(?:ics)?$|^a ?and ?a$"
     r"|^aa$|^a a$", "aa"),
    (r"^publications of (?:the )?astronomical society of (?:the )?pacific$|^publ(?:ications)? astron"
     r"(?:omical)? soc(?:iety)? pac(?:ific)?$|^publications of (?:the )?asp$|^pasp$", "pasp"),
    (r"^publications of (?:the )?astronomical society of japan$|^publ astron soc (?:jpn|japan)$"
     r"|^pasj$", "pasj"),
    (r"^publications of (?:the )?astronomical society of australia$|^publ astron soc aust(?:ralia)?$"
     r"|^pasa$", "pasa"),
    (r"^annual review of astronomy (?:and )?astrophysics$|^ann(?:u)?(?:al)? rev(?:iew)?\.? (?:of )?"
     r"astron(?:omy)? (?:and )?astrophys(?:ics)?$|^araa$|^ara and a$", "araa"),
    (r"^astronomy (?:and |& )?astrophysics review$|^astron astrophys rev$|^a and arv$", "aarv"),
    (r"^nature astronomy$|^nat(?:ure)? astron(?:omy)?$|^natas$", "natastro"),
    (r"^nature physics$|^nat phys$", "natphys"),
    (r"^nature$|^natur$", "nature"),
    (r"^science$|^sci$", "science"),
    (r"^phys(?:ical)? rev(?:iew)? d$|^prd$|^phrvd$", "prd"),
    (r"^phys(?:ical)? rev(?:iew)? lett(?:ers)?$|^prl$|^phrvl$", "prl"),
    (r"^phys(?:ical)? rev(?:iew)? x$|^prx$", "prx"),
    (r"^journal of cosmology and astroparticle physics$|^j(?:ournal)? cosmol(?:ogy)? astropart"
     r"(?:icle)? phys(?:ics)?$|^jcap$", "jcap"),
    (r"^journal of high energy physics$|^j high energy phys$|^jhep$", "jhep"),
    (r"^european physical journal c$|^eur phys j c$|^epjc$", "epjc"),
    (r"^classical and quantum gravity$|^class(?:ical)? quant(?:um)? grav(?:ity)?$|^cqg$", "cqg"),
    (r"^physics reports$|^phys rep(?:t|orts)?$", "physrep"),
    (r"^space science reviews$|^space sci rev$|^ssrv$", "ssrv"),
    (r"^astrophysics and space science$|^astrophys space sci$|^ap and ss$", "apss"),
    (r"^(?:the )?planetary science journal$|^planet sci j$|^psj$", "psj"),
    (r"^research notes of (?:the )?(?:american astronomical society|aas)$|^res notes aas$|^rnaas$",
     "rnaas"),
    (r"^icarus$|^icar$", "icarus"),
    (r"^astronomische nachrichten$|^astron nachr$|^an$", "an"),
    (r"^new astronomy$|^new astron$|^newa$", "newa"),
    (r"^new astronomy reviews$|^new astron rev$", "newar"),
    (r"^solar physics$|^sol phys$|^soph$", "solphys"),
    (r"^proc(?:eedings)?(?: of)? (?:the )?spie$|^spie$|^society of photo optical instrumentation"
     r" engineers.*$", "spie"),
    (r"^astronomical society of (?:the )?pacific conference series$|^asp conf(?:erence)?\.? ser(?:ies)?$"
     r"|^aspc$", "aspc"),
    (r"^european physical journal web of conferences$|^epj web of conferences$|^epjwc$", "epjwc"),
    (r"^galaxies$", "galaxies"),
    (r"^universe$", "universe"),
]
_COMPILED = [(re.compile(p), k) for p, k in _PATTERNS]


def _clean(name: str) -> str:
    s = fold(name)
    s = s.replace("\\", " ")
    s = re.sub(r"[^a-z0-9& ]+", " ", s)
    s = s.replace("&", " and ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def journal_key(name: str | None) -> tuple[str | None, bool]:
    """Return (canonical key or None, typo_flag).

    typo_flag is True when the name only matched after collapsing a doubled letter,
    e.g. 'mmnras'. That is a journal-string typo on what is usually a real reference.
    """
    if not name:
        return None, False
    raw = name.strip()
    m = re.fullmatch(r"\\?([A-Za-z]+)", raw)
    if m and raw.startswith("\\") and m.group(1).lower() in AAS_MACROS:
        return AAS_MACROS[m.group(1).lower()], False
    s = _clean(raw)
    if not s:
        return None, False
    if s.replace(" ", "") in AAS_MACROS and len(s) <= 8:
        return AAS_MACROS[s.replace(" ", "")], False
    for rx, key in _COMPILED:
        if rx.match(s):
            return key, False
    collapsed = re.sub(r"([a-z])\1", r"\1", s)
    if collapsed != s:
        if collapsed.replace(" ", "") in AAS_MACROS and len(collapsed) <= 8:
            return AAS_MACROS[collapsed.replace(" ", "")], True
        for rx, key in _COMPILED:
            if rx.match(collapsed):
                return key, True
    return None, False


_MACRO_RE = re.compile(r"\\([A-Za-z]+)(?![A-Za-z])")


def expand_macros(latex: str) -> str:
    """Replace AAS journal macros (\\apj, \\mnras, ...) with readable abbreviations."""

    def repl(m: re.Match) -> str:
        k = m.group(1).lower()
        if m.group(1) in AAS_MACROS or (k in AAS_MACROS and m.group(1).islower()):
            key = AAS_MACROS[k]
            return BIBSTEMS.get(key, key.upper())
        return m.group(0)

    return _MACRO_RE.sub(repl, latex)


def bibstem_for(name: str | None) -> str | None:
    key, _ = journal_key(name)
    return BIBSTEMS.get(key) if key else None


def journals_agree(a: str | None, b: str | None) -> bool | None:
    """True/False when both names are known or comparable, None when there is not enough to say."""
    if not a or not b:
        return None
    ka, _ = journal_key(a)
    kb, _ = journal_key(b)
    if ka and kb:
        # ApJ letters are often filed as ApJ with an L page; treat the pair as compatible
        if {ka, kb} <= {"apj", "apjl"} or {ka, kb} <= {"mnras"}:
            return True
        return ka == kb
    ta = set(_clean(a).split()) - {"the", "of", "and", "journal"}
    tb = set(_clean(b).split()) - {"the", "of", "and", "journal"}
    if not ta or not tb:
        return None
    j = len(ta & tb) / len(ta | tb)
    if j >= 0.5:
        return True
    return None  # abbreviations make low overlap uninformative
