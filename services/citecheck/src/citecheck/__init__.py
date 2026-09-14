# SPDX-License-Identifier: AGPL-3.0-or-later
"""citecheck: check that the references in a paper exist and that their metadata agree.

citecheck checks existence and bibliographic metadata. It does not check whether a
cited work supports the claim it is cited for. That stays a human judgment.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "1.0"
SCHEMA_ID = "https://garleak.org/schemas/citecheck/report.v1.json"

DISCLAIMER = (
    "citecheck checks that each reference exists and that its identifiers and "
    "bibliographic metadata (title, authors, year, venue) agree with a registry record. "
    "It does not check whether a cited work supports the claim it is cited for. "
    "An 'unresolved' verdict means no matching record was found in the registries "
    "consulted; it is not proof of fabrication."
)

from .models import Verdict, Reference, Record, Evidence, RefResult  # noqa: E402

__all__ = [
    "__version__",
    "SCHEMA_VERSION",
    "SCHEMA_ID",
    "DISCLAIMER",
    "Verdict",
    "Reference",
    "Record",
    "Evidence",
    "RefResult",
]
