# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command line: validate an archive, hash a version directory, or run the git guard.

    python -m garleak_archive validate ../archive ../archive-example
    python -m garleak_archive hash ../archive/papers/4471/v1.0
    python -m garleak_archive guard --base origin/main ../archive
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hashing import tree_sha256
from .validate import validate_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="garleak_archive")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check one or more archive directories")
    v.add_argument("archives", nargs="+", type=Path)
    v.add_argument("--rubrics", type=Path, default=None)
    h = sub.add_parser("hash", help="print the tree hash of a version directory")
    h.add_argument("directory", type=Path)
    g = sub.add_parser("guard", help="check that no version changed since a git revision")
    g.add_argument("archives", nargs="+", type=Path)
    g.add_argument("--base", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "hash":
        print(tree_sha256(args.directory))
        return 0
    if args.cmd == "guard":
        from .immutability import guard

        errs = [e for root in args.archives for e in guard(root, args.base)]
        for e in errs:
            print("error:", e)
        print(f"guard: {len(errs)} error(s)")
        return 1 if errs else 0
    bad = 0
    for root in args.archives:
        arch, issues = validate_path(root, args.rubrics)
        for i in issues:
            print(i)
        n_err = sum(1 for i in issues if i.level == "error")
        bad += n_err
        print(f"{root}: {len(arch.papers)} papers, {len(arch.scratches)} scratches, "
              f"{len(arch.accounts)} accounts, {n_err} error(s), {len(issues) - n_err} warning(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
