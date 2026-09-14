# SPDX-License-Identifier: AGPL-3.0-or-later
"""Where things live in the repository checkout."""

from __future__ import annotations

import shutil
from pathlib import Path

PKG = Path(__file__).resolve().parent
SITE = PKG.parent
REPO = SITE.parent
FORMS_DIR = REPO / ".github" / "ISSUE_TEMPLATE"
LABELS_FILE = REPO / ".github" / "labels.yml"
ARCHIVE = REPO / "archive"
RUBRICS = REPO / "packages" / "rubrics"


def find_citecheck(explicit: str | None = None) -> str | None:
    """The citecheck executable: an explicit path, the standalone package's own venv, or
    PATH. None when it is not installed, in which case the check is skipped cleanly."""
    if explicit:
        if Path(explicit).is_file():
            return str(Path(explicit))
        return shutil.which(explicit)
    local = REPO / "services" / "citecheck" / ".venv" / "bin" / "citecheck"
    if local.is_file():
        return str(local)
    return shutil.which("citecheck")
