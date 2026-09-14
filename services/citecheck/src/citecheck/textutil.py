# SPDX-License-Identifier: AGPL-3.0-or-later
"""LaTeX-to-text conversion, accent folding, and tokenization."""

from __future__ import annotations

import re
import unicodedata

_ACCENT_CMDS = {
    "'": "\u0301",
    "`": "\u0300",
    "^": "\u0302",
    '"': "\u0308",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "u": "\u0306",
    "v": "\u030c",
    "H": "\u030b",
    "c": "\u0327",
    "k": "\u0328",
    "r": "\u030a",
}

_SPECIAL = {
    r"\aa": "å", r"\AA": "Å", r"\o": "ø", r"\O": "Ø", r"\ss": "ß", r"\l": "ł", r"\L": "Ł",
    r"\ae": "æ", r"\AE": "Æ", r"\oe": "œ", r"\OE": "Œ", r"\i": "ı", r"\j": "ȷ",
}

# Commands whose argument is kept as text.
_KEEP_ARG = (
    "emph", "textit", "textbf", "textrm", "textsc", "textsf", "texttt", "textup", "textsl",
    "mbox", "hbox", "text", "mathrm", "mathit", "mathbf", "bf", "it", "rm", "sc", "em",
    "url", "nolinkurl", "bibinfo", "bibnamefont", "bibfnamefont", "citenamefont",
    "ensuremath", "MakeUppercase", "MakeLowercase", "uppercase", "lowercase", "natexlab",
    "noopsort", "bibsc", "bibem", "bibfield", "bibitemsep",
)

_SYMBOLS = {
    r"\&": "&", r"\%": "%", r"\$": "$", r"\#": "#", r"\_": "_", r"\{": "{", r"\}": "}",
    r"\textendash": "-", r"\textemdash": "-", r"\ldots": "...", r"\dots": "...",
    r"\sim": "~", r"\odot": "sun", r"\alpha": "alpha", r"\beta": "beta", r"\gamma": "gamma",
    r"\Lambda": "Lambda", r"\lambda": "lambda", r"\sigma": "sigma", r"\mu": "mu",
    r"\nu": "nu", r"\Omega": "Omega", r"\omega": "omega", r"\Delta": "Delta", r"\delta": "delta",
    r"\pi": "pi", r"\tau": "tau", r"\chi": "chi", r"\rho": "rho", r"\epsilon": "epsilon",
    r"\eta": "eta", r"\theta": "theta", r"\kappa": "kappa", r"\phi": "phi", r"\psi": "psi",
    r"\xi": "xi", r"\zeta": "zeta", r"\times": "x", r"\pm": "+-", r"\approx": "~",
    r"\lesssim": "<~", r"\gtrsim": ">~", r"\le": "<=", r"\ge": ">=", r"\newblock": " ",
    r"\relax": "", r"\/": "", r"\,": " ", r"\;": " ", r"\!": "", r"\ ": " ", r"\\": " ",
}


def _apply_accents(s: str) -> str:
    # {\'e}, \'{e}, \'e, \' e, and {\'\i}
    def repl(m: re.Match) -> str:
        cmd, ch = m.group(1), m.group(2)
        if ch in ("\\i", "\\j"):
            ch = "i" if ch == "\\i" else "j"
        comb = _ACCENT_CMDS.get(cmd)
        return (ch + comb) if comb else ch

    pat = re.compile(r"\\([\'`^\"~=.])\s*\{?\s*(\\[ij](?![a-zA-Z])|[A-Za-z])\s*\}?")
    s = pat.sub(repl, s)
    pat2 = re.compile(r"\\([uvHckr])(?:\s+|\s*\{\s*)(\\[ij](?![a-zA-Z])|[A-Za-z])\s*\}?")
    s = pat2.sub(repl, s)
    return s


def latex_to_text(s: str | None) -> str:
    """Best-effort conversion of a LaTeX fragment (a bibitem, a BibTeX field) to plain text."""
    if not s:
        return ""
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"(?<!\\)%.*?$", "", s)  # comments (single line after join, rare)
    s = _apply_accents(s)
    for k in sorted(_SPECIAL, key=len, reverse=True):
        s = re.sub(re.escape(k) + r"(?![a-zA-Z])", _SPECIAL[k], s)
    # \href{url}{text} -> text ; \url{x} -> x
    s = re.sub(r"\\href\s*\{[^{}]*\}\s*", "", s)
    s = re.sub(r"\\(?:doi|dodoi|doarXiv|eprint|arxiv)\s*\{([^{}]*)\}", r" \1 ", s)
    for k in sorted(_SYMBOLS, key=len, reverse=True):
        s = s.replace(k, _SYMBOLS[k])
    # font switches like {\bfseries 919} {\scshape Planck} {\em x}
    s = re.sub(r"\\(?:bfseries|itshape|scshape|ttfamily|rmfamily|sffamily|mdseries|upshape|"
               r"normalfont|em|it|bf|sc|tt|rm|sl|sf|small|footnotesize|large|Large)\b\s*", "", s)
    # \bibinfo{field}{value} -> value
    s = re.sub(r"\\bibinfo\s*\{[^{}]*\}\s*", "", s)
    s = re.sub(r"\\(?:" + "|".join(_KEEP_ARG) + r")\b\s*", "", s)
    # drop remaining commands (keep their braced args as text)
    s = re.sub(r"\\[a-zA-Z@]+\*?", " ", s)
    s = s.replace("$", "")
    s = s.replace("{", "").replace("}", "")
    s = s.replace("~", " ")
    s = s.replace("``", '"').replace("''", '"')
    s = s.replace("--", "-")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    return s


def fold(s: str | None) -> str:
    """Lowercase and strip accents: 'García Marín' -> 'garcia marin'."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("ø", "o").replace("Ø", "o").replace("ł", "l").replace("ß", "ss")
    s = s.replace("æ", "ae").replace("œ", "oe").replace("ı", "i").replace("&", " and ")
    return s.lower()


STOPWORDS = frozenset(
    """a an the of and or in on at to for from by with without into onto over under via
    as is are be its it this that these those than then from using use new study
    de la le les des du et und der die das von zu im""".split()
)


def tokens(s: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(s))


def content_tokens(s: str | None) -> list[str]:
    return [t for t in tokens(s) if t not in STOPWORDS and (len(t) > 2 or t.isdigit())]


def norm_title(s: str | None) -> str:
    return " ".join(tokens(s))
