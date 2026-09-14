# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 1 intake for Garleak (SPEC §3.7, RFC 0001).

Issue forms in `.github/ISSUE_TEMPLATE/` arrive as GitHub issues. The intake workflow
(`.github/workflows/intake.yml`) hands each one to this package, which parses the form,
checks identity, credits, quotas, independence, loops and the gated switch, runs the
automated first pass, assigns identifiers, writes the records in the layout of
`archive/FORMAT.md`, and reports what it did. Issue text is untrusted data: this package
reads it from files and never passes it to a shell.

Modules
    forms        issue-form templates and the markdown GitHub renders from them
    requests     typed requests built from the parsed fields
    orcid        iD checksums, the GitHub URL match, and the ORCID public API client
    attachments  downloads of files attached to an issue, from allowed hosts only
    screen       the automated first pass (near-duplicates, truncation, gated keywords,
                 citecheck, calibration sample)
    context      comments, commands, permissions and open pull requests gathered by the
                 workflow
    assign       identifier assignment that skips numbers held by open pull requests
    records      writing YAML and Markdown records
    report       the result object and the issue comment, pull request body and outputs
    process      the checks for each form
    gitcheck     the collision check run before a merge
    cli          `garleak-intake`
"""

__version__ = "0.1.0"
