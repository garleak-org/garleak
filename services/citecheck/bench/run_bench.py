#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Small live benchmark for citecheck.

Two measurements:
  * false-fabricated rate: the share of references in real astro-ph papers that come out
    'unresolved' (the verdict that means "could be fabricated"). Previous audits found
    essentially no fabricated references in astro-ph, so every such verdict is treated as
    a tool miss until inspected by hand.
  * recall on synthetic fabricated references: the share of invented references (plausible
    titles, realistic author names, fake DOIs/arXiv IDs or none) that are flagged
    ('unresolved' or 'metadata_mismatch'). None of them should ever be 'verified'.

Traffic is kept polite: one e-print request per paper at 3 s spacing, batched arXiv/DataCite
and Crossref lookups, and an on-disk cache so a re-run costs almost nothing.

    python bench/run_bench.py                      # run and write bench/RESULTS.md
    python bench/run_bench.py --papers 2509.09678  # a subset
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from citecheck import __version__  # noqa: E402
from citecheck.checker import Checker  # noqa: E402
from citecheck.http import Cache, Http, default_cache_dir  # noqa: E402
from citecheck.models import Reference, Verdict  # noqa: E402
from citecheck.parsers import InputError, load_arxiv, load_bibtex  # noqa: E402
from citecheck.report import build_report  # noqa: E402
from citecheck.resolvers import build_resolvers  # noqa: E402

# Real astro-ph papers spanning bibliography styles (JHEP, AAS, A&A, MNRAS, OJA, biblatex).
REAL_PAPERS = [
    ("2509.09678", "reionization / H0 tension paper with known wrong-suffix DOIs (JHEP style)"),
    ("2106.15656", "Freedman 2021, ApJ (AAS style)"),
    ("2112.04510", "Riess et al. 2022, ApJL (AAS style, long list)"),
    ("1807.06209", "Planck 2018 VI, A&A"),
    ("2310.01112", "Simmonds et al. 2024, MNRAS"),
    ("2512.19652", "Saad & Ting, wide binaries I (OJA)"),
    ("2603.11015", "Saad & Ting, wide binaries II (OJA)"),
    ("2512.01270", "Ting, Saad & Liu, Egent"),
]

FLAGGED = {Verdict.UNRESOLVED.value, Verdict.METADATA_MISMATCH.value}

# ---------------------------------------------------------------- synthetic fakes

_OPENERS = ["Constraints on", "A census of", "Probing", "Evidence for", "Revisiting", "The imprint of",
            "Tracing", "Measuring", "On the origin of", "Signatures of", "A new look at", "Modelling"]
_TOPICS = ["dark matter subhalos", "the circumgalactic medium", "stellar feedback", "tidal streams",
           "the Hubble tension", "hot Jupiter atmospheres", "fast radio bursts", "intermediate-mass black holes",
           "metal-poor halo stars", "the cosmic dawn 21 cm signal", "Type Ia supernova progenitors",
           "wide binary orbits", "magnetar outbursts", "protoplanetary disc winds", "quasar outflows",
           "ultra-diffuse galaxies", "the Milky Way bar", "globular cluster formation"]
_CONTEXTS = ["with JWST NIRSpec spectroscopy", "from Gaia DR3 astrometry", "in the TNG50 simulation",
             "using machine-learned emulators", "at redshifts 6 < z < 9", "in the Local Group",
             "with deep MUSE observations", "from a joint Bayesian analysis", "across the SDSS-V footprint",
             "in low-metallicity environments", "with the Event Horizon Telescope", "at sub-kiloparsec scales"]
_SURNAMES = ["Okafor", "Lindqvist", "Hartmann", "Nakagawa", "Moretti", "Castellanos", "Petrov", "Achterberg",
             "Rahman", "Kowalski", "Delacroix", "Singh", "Oyelaran", "Brennan", "Takahashi", "Ferreira",
             "Novak", "Whitcombe", "Haddad", "Johansson", "Mbeki", "Arslan", "Qureshi", "Vasilenko",
             "Esposito", "Zhang", "Iyer", "Laurent", "Kaminski", "Obradovic"]
_INITIALS = "ABCDEFGHJKLMNPRSTVW"
_JOURNALS = [  # macro, volume range, page style, DOI template
    ("\\apj", (880, 990), "num", "10.3847/1538-4357/a{}"),
    ("\\apjl", (880, 990), "L", "10.3847/2041-8213/a{}"),
    ("\\mnras", (500, 535), "num", "10.1093/mnras/sta{}"),
    ("\\aap", (640, 690), "A", "10.1051/0004-6361/2023{}"),
    ("\\aj", (160, 170), "num", "10.3847/1538-3881/a{}"),
    ("\\prd", (104, 110), "num", "10.1103/PhysRevD.{}"),
]


def make_fakes(n: int, seed: int = 20260914) -> str:
    """Deterministic BibTeX of invented references."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        title = f"{rng.choice(_OPENERS)} {rng.choice(_TOPICS)} {rng.choice(_CONTEXTS)}"
        k = rng.randint(1, 4)
        authors = " and ".join(f"{rng.choice(_SURNAMES)}, {rng.choice(_INITIALS)}." for _ in range(k))
        macro, (v0, v1), pstyle, doi_t = rng.choice(_JOURNALS)
        year = rng.randint(2019, 2025)
        vol = rng.randint(v0, v1)
        page = rng.randint(1, 400)
        page_s = {"L": f"L{page % 60 + 1}", "A": f"A{page}", "num": str(page)}[pstyle]
        mode = rng.choice(["doi", "doi", "arxiv_real_shape", "arxiv_out_of_range", "none", "none"])
        extra = ""
        if mode == "doi":
            if "PhysRevD" in doi_t:
                doi = doi_t.format(f"{vol}.{rng.randint(10000, 99999):06d}")
            elif "0004-6361" in doi_t:
                doi = doi_t.format(f"{rng.randint(45000, 49999)}")
            elif "mnras" in doi_t:
                doi = doi_t.format(f"{rng.choice('abcd')}{rng.randint(1000, 3999)}")
                doi = doi.replace("/sta", "/sta")
            else:
                doi = doi_t.format("".join(rng.choice("0123456789abcdef") for _ in range(5)))
            extra = f"  doi = {{{doi}}},\n"
        elif mode == "arxiv_real_shape":
            yymm = f"{rng.randint(19, 25):02d}{rng.randint(1, 12):02d}"
            extra = f"  eprint = {{{yymm}.{rng.randint(1000, 19999):05d}}},\n  archivePrefix = {{arXiv}},\n"
        elif mode == "arxiv_out_of_range":
            yymm = f"{rng.randint(19, 25):02d}{rng.randint(1, 12):02d}"
            extra = f"  eprint = {{{yymm}.{rng.randint(60000, 99999):05d}}},\n  archivePrefix = {{arXiv}},\n"
        out.append(f"@article{{fake{i:03d}_{mode},\n  author = {{{authors}}},\n  title = {{{title}}},\n"
                   f"  journal = {{{macro}}},\n  year = {year},\n  volume = {vol},\n  pages = {{{page_s}}},\n"
                   f"{extra}}}\n")
    return "\n".join(out)


# ---------------------------------------------------------------- report


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def render_markdown(s: dict) -> str:
    """Tables for bench/RESULTS.md. The interpretation is written by hand around them."""
    real, fake = s["real"], s["fake"]
    cols = ["verified", "id_mismatch_real_ref", "metadata_mismatch", "unresolved", "not_checkable"]
    lines = [f"citecheck {s['citecheck_version']}, run {s['date']}, {s['elapsed_s']:.0f} s wall time, "
             f"resolvers {', '.join(s['resolvers'])}.", "",
             "### Real papers", "",
             "| arXiv | style source | refs | " + " | ".join(cols) + " |",
             "|---|---|---:|" + "---:|" * len(cols)]
    for p in real["papers"]:
        if "error" in p:
            lines.append(f"| {p['arxiv']} | error: {p['error']} |" + " |" * (len(cols) + 1))
            continue
        lines.append(f"| {p['arxiv']} | {p.get('kind', '')} | {p['n']} | "
                     + " | ".join(str(p.get(c, 0)) for c in cols) + " |")
    tot = real["verdicts"]
    lines.append(f"| **total** | | **{real['n']}** | " + " | ".join(f"**{tot.get(c, 0)}**" for c in cols) + " |")
    lines += ["", f"False-fabricated rate (unresolved / all real references): **{_pct(real['false_fabricated_rate'])}**"
              f" ({tot.get('unresolved', 0)} of {real['n']}).",
              f"Excluding not_checkable: {_pct(real['false_fabricated_rate_checkable'])}. "
              f"Metadata-mismatch rate: {_pct(real['metadata_mismatch_rate'])}.", "",
              "### Synthetic fabricated references", "",
              f"{fake['n']} invented references. Flagged (unresolved or metadata_mismatch): "
              f"**{_pct(fake['recall_flagged'])}**. Unresolved alone: {_pct(fake['recall_unresolved_only'])}. "
              f"Wrongly verified: **{fake['n_verified']}**.", "",
              "| identifier mode | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
    for mode, c in sorted(fake["by_mode"].items()):
        lines.append(f"| {mode} | " + " | ".join(str(c.get(v, 0)) for v in cols) + " |")
    lines += ["", "### Requests", "", "| host | requests | cache hits | errors |", "|---|---:|---:|---:|"]
    for host, st in sorted(s["network"].items()):
        lines.append(f"| {host} | {st['requests']} | {st['cache_hits']} | {st['errors']} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- runs


def run_refs(refs: list[Reference], http: Http, resolvers) -> list:
    return Checker(resolvers).check_all(refs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", nargs="*", help="arXiv IDs (default: the built-in list)")
    ap.add_argument("--n-fakes", type=int, default=40)
    ap.add_argument("--cache-dir", default=str(default_cache_dir()))
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--no-ads", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    http = Http(Cache(args.cache_dir))
    enabled = {"arxiv", "crossref", "doi.org", "openalex", "pos"} | (set() if args.no_ads else {"ads"})
    resolvers = build_resolvers(http, enabled)
    papers = [(p, "") for p in args.papers] if args.papers else REAL_PAPERS
    t0 = time.time()

    real_rows = []
    real_verdicts = collections.Counter()
    unresolved_list = []
    mismatch_list = []
    for aid, desc in papers:
        started = dt.datetime.now(dt.timezone.utc)
        try:
            loaded = load_arxiv(aid, http)
        except InputError as e:
            real_rows.append({"arxiv": aid, "desc": desc, "error": str(e)})
            print(f"{aid}: {e}", file=sys.stderr)
            continue
        results = Checker(resolvers).check_all(loaded.refs)
        report = build_report(results, loaded.info(), {"resolvers": sorted(resolvers)}, {}, started,
                              dt.datetime.now(dt.timezone.utc))
        (out / f"real_{aid.replace('/', '_')}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
        c = collections.Counter(r.verdict.value for r in results)
        real_verdicts.update(c)
        for r in results:
            if r.verdict == Verdict.UNRESOLVED:
                unresolved_list.append((aid, r.reference.index, r.reference.raw, r.reason, r.incomplete))
            if r.verdict == Verdict.METADATA_MISMATCH:
                mismatch_list.append((aid, r.reference.index, r.reference.raw, r.reason))
        real_rows.append({"arxiv": aid, "desc": desc, "kind": loaded.kind, "n": len(results), **dict(c),
                          "corrections": [(r.reference.index, r.corrected_ids) for r in results
                                          if r.verdict == Verdict.ID_MISMATCH_REAL_REF]})
        print(f"{aid}: {len(results)} refs {dict(c)}", file=sys.stderr)

    # synthetic fabricated references: generated set + the hand-written fixtures
    fake_bib = make_fakes(args.n_fakes)
    (out / "synthetic_fakes.bib").write_text(fake_bib)
    fakes = load_bibtex(fake_bib)
    hand = load_bibtex((ROOT / "tests" / "fixtures" / "fabricated.bib").read_text())
    for i, r in enumerate(hand):
        r.index = len(fakes) + i + 1
    fakes += hand
    started = dt.datetime.now(dt.timezone.utc)
    fres = Checker(resolvers).check_all(fakes)
    freport = build_report(fres, {"kind": "bibtex", "source": "synthetic"}, {}, {}, started,
                           dt.datetime.now(dt.timezone.utc))
    (out / "synthetic_fakes.json").write_text(json.dumps(freport, indent=1, ensure_ascii=False))
    fake_verdicts = collections.Counter(r.verdict.value for r in fres)
    fake_by_mode = collections.defaultdict(collections.Counter)
    for r in fres:
        mode = r.reference.key.split("_", 1)[1] if r.reference.key.startswith("fake0") else "hand-written"
        fake_by_mode[mode][r.verdict.value] += 1
    elapsed = time.time() - t0

    n_real = sum(real_verdicts.values())
    n_real_checkable = n_real - real_verdicts.get("not_checkable", 0)
    n_unres = real_verdicts.get("unresolved", 0)
    n_mism = real_verdicts.get("metadata_mismatch", 0)
    n_fake = len(fres)
    n_flag = sum(fake_verdicts.get(v, 0) for v in FLAGGED)
    summary = {
        "citecheck_version": __version__,
        "date": dt.date.today().isoformat(),
        "elapsed_s": round(elapsed, 1),
        "resolvers": sorted(resolvers),
        "real": {"papers": real_rows, "verdicts": dict(real_verdicts), "n": n_real,
                 "n_checkable": n_real_checkable,
                 "false_fabricated_rate": n_unres / n_real if n_real else None,
                 "false_fabricated_rate_checkable": n_unres / n_real_checkable if n_real_checkable else None,
                 "metadata_mismatch_rate": n_mism / n_real if n_real else None,
                 "unresolved": unresolved_list, "metadata_mismatch": mismatch_list},
        "fake": {"n": n_fake, "verdicts": dict(fake_verdicts),
                 "recall_flagged": n_flag / n_fake if n_fake else None,
                 "recall_unresolved_only": fake_verdicts.get("unresolved", 0) / n_fake if n_fake else None,
                 "n_verified": fake_verdicts.get("verified", 0) + fake_verdicts.get("id_mismatch_real_ref", 0),
                 "by_mode": {k: dict(v) for k, v in fake_by_mode.items()}},
        "network": http.stats,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    (HERE / "RESULTS.generated.md").write_text(render_markdown(summary))
    print(json.dumps({k: summary[k] for k in ("elapsed_s",)} | {"real": {k: v for k, v in summary["real"].items()
                                                                         if k not in ("papers", "unresolved",
                                                                                      "metadata_mismatch")},
                      "fake": summary["fake"]}, indent=1))
    http.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
