# SPDX-License-Identifier: AGPL-3.0-or-later
"""Input dispatch: files, directories, tarballs, plain text, and arXiv e-prints."""

from __future__ import annotations

import gzip
import io
import json
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ..http import Cache, FetchError, Http, OfflineMiss, Response
from ..ids import normalize_arxiv
from ..models import Reference
from .bbl import is_biblatex, load_bbl, parse_thebibliography
from .bibtex import load_bibtex
from .freetext import parse_reference

TEXT_EXT = (".tex", ".bbl", ".bib", ".ltx", ".txt")
MAX_MEMBER_BYTES = 20_000_000


class InputError(ValueError):
    pass


@dataclass
class LoadedInput:
    refs: list[Reference]
    kind: str
    source: str
    files_used: list[str] = field(default_factory=list)
    arxiv_id: str | None = None
    notes: list[str] = field(default_factory=list)

    def info(self) -> dict:
        d = {"kind": self.kind, "source": self.source, "files_used": self.files_used, "notes": self.notes}
        if self.arxiv_id:
            d["arxiv_id"] = self.arxiv_id
        return d


def _decode(b: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


# ------------------------------------------------------------------ plain text


_HEADER = re.compile(r"^\s*(references|bibliography|works cited|literature cited)\s*:?\s*$", re.I)


def load_plaintext(text: str) -> list[Reference]:
    """One reference per line, or per blank-line-separated block."""
    text = text.replace("\r\n", "\n")
    blocks = [b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    multi_line = sum(1 for b in blocks if "\n" in b.strip())
    if len(blocks) >= 2 and multi_line >= len(blocks) / 2:
        entries = [" ".join(b.split()) for b in blocks]
    else:
        entries = [ln.strip() for ln in text.splitlines() if ln.strip()]
    refs = []
    for e in entries:
        if _HEADER.match(e):
            continue
        e = re.sub(r"^\s*(?:\[\d+\]|\d+[.)]|\(\d+\)|[-*\u2022])\s+", "", e)
        if len(e) < 8:
            continue
        refs.append(parse_reference(e, index=len(refs) + 1, source_format="text"))
    return refs


def load_text(text: str, hint: str | None = None) -> tuple[list[Reference], str]:
    """Parse text whose format is given by hint ('bib', 'bbl', 'tex', 'text') or sniffed."""
    kind = hint
    if kind is None:
        if re.search(r"^\s*@\s*[A-Za-z]+\s*[{(]", text, re.M):
            kind = "bib"
        elif is_biblatex(text) or "\\bibitem" in text:
            kind = "bbl" if "\\documentclass" not in text else "tex"
        else:
            kind = "text"
    if kind == "bib":
        return load_bibtex(text), "bibtex"
    if kind == "bbl":
        return load_bbl(text), "bbl"
    if kind == "tex":
        loaded = load_source_files({"main.tex": text.encode()}, origin="tex")
        return loaded.refs, "latex"
    return load_plaintext(text), "text"


# ------------------------------------------------------------------ LaTeX sources

_CITE_RE = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}")


def cited_keys(tex_texts: list[str]) -> tuple[set[str], bool]:
    keys: set[str] = set()
    nocite_all = False
    for t in tex_texts:
        t = re.sub(r"(?<!\\)%.*", "", t)
        for m in _CITE_RE.finditer(t):
            for k in m.group(1).split(","):
                k = k.strip()
                if k == "*":
                    nocite_all = True
                elif k:
                    keys.add(k)
    return keys, nocite_all


def _is_main_tex(t: str) -> bool:
    return "\\documentclass" in t and "\\begin{document}" in t


def load_source_files(files: dict[str, bytes], origin: str) -> LoadedInput:
    texts = {p: _decode(b) for p, b in files.items() if p.lower().endswith(TEXT_EXT)}
    tex = {p: t for p, t in texts.items() if p.lower().endswith((".tex", ".ltx"))}
    bbls = {p: t for p, t in texts.items() if p.lower().endswith(".bbl")}
    bibs = {p: t for p, t in texts.items() if p.lower().endswith(".bib")}
    mains = [p for p, t in tex.items() if _is_main_tex(t)]

    if bbls:
        chosen = None
        for m in mains:
            stem = m.rsplit(".", 1)[0]
            if stem + ".bbl" in bbls:
                chosen = stem + ".bbl"
                break
        if chosen is None:
            chosen = max(bbls, key=lambda p: bbls[p].count("\\bibitem") + bbls[p].count("\\entry{"))
        refs = load_bbl(bbls[chosen])
        if refs:
            notes = [f"{len(bbls)} .bbl files found; used {chosen}"] if len(bbls) > 1 else []
            return LoadedInput(refs, "latex-bbl", origin, [chosen], notes=notes)

    # \bibliography{a,b} or \addbibresource{x.bib}
    wanted: list[str] = []
    for p in (mains or list(tex)):
        for m in re.finditer(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\{([^}]*)\}", tex[p]):
            for name in m.group(1).split(","):
                name = name.strip()
                if name:
                    wanted.append(name if name.endswith(".bib") else name + ".bib")
    if bibs:
        use = []
        for w in wanted:
            for p in bibs:
                if p == w or p.endswith("/" + w) or Path(p).name == Path(w).name:
                    use.append(p)
        if not use:
            use = list(bibs)
        keys, all_keys = cited_keys(list(tex.values()))
        text = "\n".join(bibs[p] for p in dict.fromkeys(use))
        refs = load_bibtex(text, None if (all_keys or not keys) else keys)
        notes = []
        if keys and not all_keys:
            notes.append(f"kept {len(refs)} entries cited in the .tex files")
        if refs:
            return LoadedInput(refs, "latex-bib", origin, list(dict.fromkeys(use)), notes=notes)

    for p, t in tex.items():
        if "\\begin{thebibliography}" in t:
            refs = parse_thebibliography(t, "tex")
            if refs:
                return LoadedInput(refs, "latex-inline", origin, [p])
    raise InputError("no bibliography found (looked for .bbl, .bib, and \\begin{thebibliography})")


def files_from_archive(data: bytes) -> dict[str, bytes]:
    """Read text members of a tar/tar.gz/zip/gzip archive into memory (never onto disk)."""
    if data[:4] == b"%PDF":
        raise InputError("the archive is a PDF; citecheck needs LaTeX source, a .bib/.bbl, or a text list")
    if data[:2] == b"PK":
        out = {}
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                if not info.is_dir() and info.filename.lower().endswith(TEXT_EXT) and info.file_size < MAX_MEMBER_BYTES:
                    out[info.filename] = z.read(info)
        return out
    try:
        out = {}
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name.lower().endswith(TEXT_EXT) and m.size < MAX_MEMBER_BYTES:
                    f = tf.extractfile(m)
                    if f is not None:
                        out[m.name.lstrip("./")] = f.read()
        return out
    except tarfile.TarError:
        pass
    if data[:2] == b"\x1f\x8b":
        raw = gzip.decompress(data)
        if raw[:4] == b"%PDF":
            raise InputError("arXiv provides only a PDF for this paper; no LaTeX source to read")
        return {"main.tex": raw}
    return {"main.tex": data}


def load_path(path: str | Path) -> LoadedInput:
    p = Path(path)
    if str(path) == "-":
        import sys
        refs, kind = load_text(sys.stdin.read())
        return LoadedInput(refs, kind, "stdin")
    if not p.exists():
        raise InputError(f"no such file or directory: {path}")
    if p.is_dir():
        files = {}
        for f in p.rglob("*"):
            if f.is_file() and f.suffix.lower() in TEXT_EXT and ".venv" not in f.parts and f.stat().st_size < MAX_MEMBER_BYTES:
                files[str(f.relative_to(p))] = f.read_bytes()
        return load_source_files(files, str(p))
    name = p.name.lower()
    if name.endswith((".tar", ".tar.gz", ".tgz", ".zip", ".gz")):
        return load_source_files(files_from_archive(p.read_bytes()), str(p))
    text = _decode(p.read_bytes())
    if name.endswith(".bib"):
        return LoadedInput(load_bibtex(text), "bibtex", str(p), [p.name])
    if name.endswith(".bbl"):
        return LoadedInput(load_bbl(text), "bbl", str(p), [p.name])
    if name.endswith((".tex", ".ltx")):
        sib = {}
        for f in p.parent.iterdir():
            if f.is_file() and f.suffix.lower() in (".bib", ".bbl") and f.stat().st_size < MAX_MEMBER_BYTES:
                sib[f.name] = f.read_bytes()
        # only the .bbl that belongs to this .tex, plus any .bib files
        sib = {k: v for k, v in sib.items() if k.endswith(".bib") or k == p.stem + ".bbl"}
        sib[p.name] = p.read_bytes()
        return load_source_files(sib, str(p))
    refs, kind = load_text(text)
    return LoadedInput(refs, kind, str(p), [p.name])


# ------------------------------------------------------------------ arXiv e-prints


def _bundle_key(arxiv_id: str) -> str:
    return Cache.make_key(f"citecheck:arxiv-bundle:{arxiv_id}", None)


def load_arxiv(arxiv_id: str, http: Http) -> LoadedInput:
    """Fetch the arXiv e-print source and read its bibliography.

    Only the bibliography-bearing text files are cached (as a small JSON bundle), so
    re-runs and --offline work without keeping multi-megabyte tarballs.
    """
    raw_id = arxiv_id.strip()
    aid = normalize_arxiv(raw_id)
    if not aid:
        raise InputError(f"not an arXiv identifier: {arxiv_id}")
    vm = re.search(r"(v\d+)\s*$", raw_id)
    fetch_id = aid + (vm.group(1) if vm else "")
    ns = "arxiv_bundle"
    key = _bundle_key(fetch_id)
    files: dict[str, bytes] | None = None
    if http.cache is not None:
        hit = http.cache.get(ns, key, offline=True)
        if hit is not None and hit.status == 200:
            files = {k: v.encode() for k, v in json.loads(hit.text).items()}
    if files is None:
        if http.offline:
            raise InputError(f"--offline: the e-print for arXiv:{fetch_id} is not in the cache")
        try:
            resp = http.get(f"https://arxiv.org/e-print/{fetch_id}", ns="arxiv_eprint", rate_key="arxiv",
                            interval=3.0, use_cache=False)
        except (FetchError, OfflineMiss) as e:
            raise InputError(f"could not fetch the arXiv e-print: {e}") from None
        if resp.status != 200:
            raise InputError(f"arXiv returned HTTP {resp.status} for the e-print of {fetch_id}")
        all_files = files_from_archive(resp.content)
        files = {k: v for k, v in all_files.items() if k.lower().endswith((".tex", ".bbl", ".bib", ".ltx"))}
        if http.cache is not None:
            bundle = json.dumps({k: _decode(v) for k, v in files.items()})
            http.cache.put(ns, key, Response(200, f"https://arxiv.org/e-print/{fetch_id}", "application/json",
                                             bundle.encode()))
    loaded = load_source_files(files, f"arXiv:{fetch_id}")
    loaded.arxiv_id = fetch_id
    loaded.kind = "arxiv-" + loaded.kind
    return loaded
