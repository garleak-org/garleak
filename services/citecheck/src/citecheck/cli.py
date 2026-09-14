# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command-line interface.

Exit codes: 0 when nothing is flagged, 1 when at least one reference is unresolved or has
mismatched metadata (or the run was incomplete), 2 on usage or input errors.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import DISCLAIMER, __version__
from .checker import Checker
from .http import Cache, Http, default_cache_dir
from .parsers import InputError, load_arxiv, load_path
from .report import build_report, render_table
from .resolvers import ALL, build_resolvers


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="citecheck",
        description="Check that the references in a paper exist and that their identifiers and metadata agree. "
                    "It does not check whether a cited work supports the claim it is cited for.",
    )
    p.add_argument("input", nargs="?", help=".bib, .bbl, .tex, a LaTeX source directory or tarball, "
                                            "or a plain-text reference list ('-' for stdin)")
    p.add_argument("--arxiv", metavar="ID", help="fetch the arXiv e-print source for ID and check its bibliography")
    p.add_argument("--json", metavar="PATH", help="write the JSON report here ('-' for stdout)")
    p.add_argument("--offline", action="store_true", help="use the cache only; make no network requests")
    p.add_argument("--cache-dir", metavar="DIR", help=f"cache location (default: {default_cache_dir()})")
    p.add_argument("--no-cache", action="store_true", help="do not read or write the on-disk cache")
    p.add_argument("--resolvers", metavar="LIST", help=f"comma-separated subset of: {','.join(ALL)}")
    p.add_argument("--no-ads", action="store_true", help="do not use NASA ADS even if a token is present")
    p.add_argument("--no-arxiv-search", action="store_true", help="skip arXiv title search (it is slow, 3 s a call)")
    p.add_argument("--only-flagged", action="store_true", help="hide verified references in the table")
    p.add_argument("--max-refs", type=int, metavar="N", help="check only the first N references")
    p.add_argument("-q", "--quiet", action="store_true", help="no table and no progress output")
    p.add_argument("-v", "--verbose", action="store_true", help="log every request (URLs only, never tokens)")
    p.add_argument("--exit-zero", action="store_true", help="always exit 0 unless the input could not be read")
    p.add_argument("--version", action="version", version=f"citecheck {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if not args.input and not args.arxiv:
        make_parser().print_usage(sys.stderr)
        print("citecheck: give an input file/directory or --arxiv ID", file=sys.stderr)
        return 2
    cache = None if args.no_cache else Cache(Path(args.cache_dir).expanduser() if args.cache_dir else default_cache_dir())
    if args.offline and cache is None:
        print("citecheck: --offline needs the cache (drop --no-cache)", file=sys.stderr)
        return 2
    http = Http(cache, offline=args.offline, verbose=args.verbose)
    enabled = set(ALL)
    if args.resolvers:
        enabled = {x.strip() for x in args.resolvers.split(",") if x.strip()}
        unknown = enabled - set(ALL)
        if unknown:
            print(f"citecheck: unknown resolver(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
    if args.no_ads:
        enabled.discard("ads")
    started = dt.datetime.now(dt.timezone.utc)
    try:
        loaded = load_arxiv(args.arxiv, http) if args.arxiv else load_path(args.input)
    except InputError as e:
        print(f"citecheck: {e}", file=sys.stderr)
        return 2
    refs = loaded.refs[: args.max_refs] if args.max_refs else loaded.refs
    if not refs:
        print("citecheck: no references found in the input", file=sys.stderr)
        return 2
    resolvers = build_resolvers(http, enabled)
    show_progress = not args.quiet and sys.stderr.isatty() and not args.verbose

    def progress(i: int, n: int, ref) -> None:
        if show_progress:
            who = (ref.authors[0] if ref.authors else ref.collaboration or ref.key or "")[:30]
            print(f"\r[{i}/{n}] {who:<30}", end="", file=sys.stderr, flush=True)

    checker = Checker(resolvers, arxiv_search=not args.no_arxiv_search, progress=progress)
    try:
        results = checker.check_all(refs)
    except KeyboardInterrupt:
        print("\ncitecheck: interrupted", file=sys.stderr)
        return 130
    finally:
        http.close()
    if show_progress:
        print("\r" + " " * 50 + "\r", end="", file=sys.stderr)
    finished = dt.datetime.now(dt.timezone.utc)
    settings = {
        "offline": args.offline,
        "resolvers": sorted(resolvers),
        "ads_enabled": "ads" in resolvers,
        "arxiv_search": not args.no_arxiv_search,
        "max_refs": args.max_refs,
    }
    report = build_report(results, loaded.info(), settings, http.stats, started, finished)
    if args.json:
        text = json.dumps(report, indent=2, ensure_ascii=False)
        if args.json == "-":
            print(text)
        else:
            Path(args.json).write_text(text + "\n")
    if not args.quiet and args.json != "-":
        print(render_table(results, report["summary"], loaded.info(), only_flagged=args.only_flagged))
    elif args.quiet and args.json != "-":
        pass
    if args.json == "-" and not args.quiet:
        print("Note: " + DISCLAIMER, file=sys.stderr)
    status = report["summary"]["prescreen"]["status"]
    if args.exit_zero:
        return 0
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
