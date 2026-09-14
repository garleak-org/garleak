# SPDX-License-Identifier: AGPL-3.0-or-later
"""The result of one intake run, and the texts the workflow posts from it: the issue
comment, the pull request title and body, the commit message, labels and step outputs.

Only fixed values reach the workflow's step outputs (an action word, true or false, a
branch name of a fixed shape). Anything that came from the issue goes into files that
are passed to `gh` with --body-file, never into a shell line."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from . import labels as L
from .context import BOT_MARKER

SUBMIT_URL = "https://garleak.org/submit/"
BRANCH_RE = re.compile(r"^intake/issue-[0-9]+(-[a-z]+)?$")
OUTCOME_WORDS = {"pass": "passed", "fail": "did not pass", "flag": "flagged", "skip": "skipped", "info": "note"}


@dataclass
class Check:
    id: str
    title: str
    outcome: str  # pass | fail | flag | skip | info
    detail: str
    criterion: str = ""
    version: str = ""
    score: float | None = None


@dataclass
class Result:
    issue: int
    kind: str
    status: str = "noop"  # accepted | held | refused | waiting | noop | acknowledged | rejected | removed | error
    headline: str = ""
    lead: str = ""
    checks: list[Check] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    automerge: bool = False
    branch: str = ""
    pr_title: str = ""
    closes_issue: bool = True
    labels_add: list[str] = field(default_factory=list)
    close_issue: str = ""  # "" | completed | not planned
    close_pr: bool = False
    notes: list[str] = field(default_factory=list)
    balance: dict | None = None
    meta: dict = field(default_factory=dict)
    comment: bool = True
    errors: list[str] = field(default_factory=list)
    previews: dict[str, str] = field(default_factory=dict)

    # -------------------------------------------------------- checks

    def add(self, id: str, title: str, outcome: str, detail: str, criterion: str = "", version: str = "",
            score: float | None = None) -> Check:
        c = Check(id, title, outcome, detail, criterion, version, score)
        self.checks.append(c)
        return c

    def ok(self, id, title, detail, **kw):
        return self.add(id, title, "pass", detail, **kw)

    def fail(self, id, title, detail, criterion, **kw):
        return self.add(id, title, "fail", detail, criterion, **kw)

    def flag(self, id, title, detail, criterion="", **kw):
        return self.add(id, title, "flag", detail, criterion, **kw)

    def info(self, id, title, detail, **kw):
        return self.add(id, title, "info", detail, **kw)

    def skip(self, id, title, detail, **kw):
        return self.add(id, title, "skip", detail, **kw)

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.outcome == "fail"]

    @property
    def flagged(self) -> list[Check]:
        return [c for c in self.checks if c.outcome == "flag"]

    @property
    def action(self) -> str:
        if self.files and self.status in ("accepted", "held", "removed", "rejected"):
            return "pr"
        return "comment" if self.comment else "none"

    # -------------------------------------------------------- labels

    def labels(self) -> tuple[list[str], list[str]]:
        add = list(self.labels_add)
        status_label = L.STATUS.get(self.status)
        if status_label:
            add.append(status_label)
        add = [x for x in dict.fromkeys(add) if L.LABEL_RE.match(x)]
        remove = [x for x in L.STATUS.values() if x not in add]
        if self.status in ("noop", "acknowledged"):
            remove = []
        return add, remove

    # -------------------------------------------------------- texts

    def comment_markdown(self) -> str:
        parts = [BOT_MARKER, f"**{self.headline}**"]
        if self.lead:
            parts.append(self.lead)
        shown = sorted(self.checks, key=lambda c: {"fail": 0, "flag": 1}.get(c.outcome, 2))
        if shown:
            rows = ["| Check | Result | Details |", "|---|---|---|"]
            for c in shown:
                detail = c.detail
                if c.criterion and c.outcome in ("fail", "flag"):
                    detail += f" Criterion: {c.criterion}."
                rows.append(f"| {_cell(c.title)} | {OUTCOME_WORDS[c.outcome]} | {_cell(detail)} |")
            parts.append("\n".join(rows))
        if self.balance:
            b = self.balance
            parts.append(f"Credits of u/{b['account']} in {b['field']}: {b['before']} before, {b['after']} after "
                         f"(the floor is {b['floor']}). Anyone can recompute this from the public records.")
        parts += self.notes
        parts.append(f"<sub>Your GitHub handle is public, and so is everything in this issue and the record it "
                     f"creates. How intake works: {SUBMIT_URL}</sub>")
        return "\n\n".join(p for p in parts if p) + "\n"

    def pr_body(self) -> str:
        closing = f"Closes #{self.issue}" if self.closes_issue else f"From #{self.issue}"
        parts = [f"{self.pr_title}.", closing]
        if self.checks:
            rows = ["| Check | Result | Details |", "|---|---|---|"]
            for c in self.checks:
                rows.append(f"| {_cell(c.title)} | {OUTCOME_WORDS[c.outcome]} | {_cell(c.detail)} |")
            parts.append("\n".join(rows))
        if self.automerge:
            parts.append("The intake workflow merges this pull request once the site checks pass.")
        else:
            parts.append("A moderator reviews and merges this pull request. Screening checks admissibility, "
                         "never quality (SPEC §8.1).")
        parts.append("Files:\n" + "\n".join(f"- `{f}`" for f in self.files))
        parts.append(f"<!-- garleak-intake {json.dumps(self.meta, sort_keys=True)} -->")
        return "\n\n".join(parts) + "\n"

    def commit_message(self) -> str:
        return f"{self.pr_title}\n\nIntake from issue #{self.issue}.\n"

    def outputs(self) -> dict[str, str]:
        out = {
            "action": self.action,
            "status": self.status,
            "kind": self.kind if re.fullmatch(r"[a-z]*", self.kind or "") else "",
            "automerge": "true" if (self.automerge and self.action == "pr") else "false",
            "branch": self.branch if BRANCH_RE.match(self.branch or "") else "",
            "close": self.close_issue if self.close_issue in ("completed", "not planned") else "",
            "close_pr": "true" if self.close_pr else "false",
            "comment": "true" if self.comment else "false",
        }
        return out

    def to_json(self) -> str:
        d = asdict(self)
        d["action"] = self.action
        d.pop("previews", None)
        return json.dumps(d, indent=2, default=str)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")
