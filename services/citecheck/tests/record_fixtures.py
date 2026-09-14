#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Re-record the HTTP fixtures used by the offline tests.

Runs citecheck live over every fixture input, once with NASA ADS (if a token is available
on this machine) and once without, writing responses into tests/fixtures/cache. Tokens are
never written: the cache stores URLs with secret parameters removed and no headers.

    python tests/record_fixtures.py            # add missing responses
    python tests/record_fixtures.py --fresh    # wipe and re-record everything
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIX = HERE / "fixtures"
CACHE = FIX / "cache"
INPUTS = ["arxiv_2509.09678_subset.bbl", "fabricated.bib", "real_refs.bib", "refs_mnras_style.txt"]


def main() -> int:
    from citecheck.cli import main as cli_main
    from citecheck.resolvers import load_token

    if "--fresh" in sys.argv and CACHE.exists():
        shutil.rmtree(CACHE)
    modes = [["--no-ads"]]
    if load_token():
        modes.insert(0, [])
    else:
        print("no ADS token on this machine: recording the no-ADS path only", file=sys.stderr)
    for inp in INPUTS:
        for extra in modes:
            args = [str(FIX / inp), "--cache-dir", str(CACHE), "-q", "--exit-zero", *extra]
            print("recording:", inp, " ".join(extra), file=sys.stderr)
            cli_main(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
