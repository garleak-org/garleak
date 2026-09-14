# SPDX-License-Identifier: AGPL-3.0-or-later
"""Garleak archive library.

The git repository is the database. This package reads an archive directory (format in
archive/FORMAT.md), checks it against SPEC.md, and derives what the site shows. It has no
knowledge of HTML, so the submission pipeline can import it directly.

Modules
    ids           identifier grammar (§2.3)
    models        dataclasses for every record
    loader        YAML files -> models, with schema checks
    schema        a small JSON Schema checker for schemas/*.schema.json
    rubrics       read-only access to packages/rubrics
    stages        stage derivation, carrying and clearing, graduation, visibility
    assistance    the writing and analysis axes, interval and median
    pct           pct_original, algorithm po-1 (§6.6)
    diff          word-level diff
    hashing       tree hash used for the v1.0 guard
    immutability  git-level guard for CI
    validate      the full rule set

A credits ledger (ledger.py) belongs beside these: it should read the same Archive and
add CreditEvent records without changing the modules above.
"""

from .ids import Identifier, VersionNumber
from .loader import load_archive
from .validate import validate

__all__ = ["Identifier", "VersionNumber", "load_archive", "validate"]
