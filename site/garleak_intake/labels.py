# SPDX-License-Identifier: AGPL-3.0-or-later
"""Issue and pull request labels the intake bot reads and writes. Every name here is
defined, with a color and description, in `.github/labels.yml`."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .paths import LABELS_FILE

# The form a new issue came from. Each issue form applies exactly one of these.
ROUTING = {
    "identity": "intake:identity",
    "scratch": "intake:scratch",
    "paper": "intake:paper",
    "version": "intake:version",
    "verify": "intake:verify",
    "novelty": "intake:novelty",
    "contest": "intake:contest",
    "vote": "intake:vote",
    "claim": "intake:claim",
    "report": "intake:report",
}
KIND_OF_LABEL = {v: k for k, v in ROUTING.items()}

PR = "intake"  # every pull request the bot opens

STATUS = {
    "accepted": "status:accepted",
    "held": "status:held",
    "refused": "status:needs-changes",
    "waiting": "status:waiting",
    "rejected": "status:rejected",
    "removed": "status:removed",
    "merged": "status:merged",
    "error": "status:error",
}

FLAGS = {
    "near-duplicate": "flag:near-duplicate",
    "truncated": "flag:truncated",
    "gated-content": "flag:gated-content",
    "citations": "flag:citations",
    "burst": "flag:burst",
    "loop": "flag:loop",
    "calibration-sample": "flag:calibration-sample",
    "agent": "flag:agent",
    "bump": "flag:bump",
}

MODERATION = {"report": "moderation:report", "appeal": "moderation:appeal"}

LABEL_RE = re.compile(r"^[a-z]+(?::[a-z0-9-]+)?$")


def emitted() -> set[str]:
    return {PR} | set(ROUTING.values()) | set(STATUS.values()) | set(FLAGS.values()) | set(MODERATION.values())


def load_file(path: Path | None = None) -> list[dict]:
    data = yaml.safe_load(Path(path or LABELS_FILE).read_text(encoding="utf-8"))
    return list(data or [])


def tsv(path: Path | None = None) -> str:
    """name, color and description per line, for `gh label create --force` in a loop."""
    lines = []
    for item in load_file(path):
        name, color, desc = item["name"], str(item["color"]).lstrip("#"), item.get("description", "")
        if not LABEL_RE.match(name) or not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            raise ValueError(f"bad label definition: {item}")
        lines.append("\t".join([name, color, desc.replace("\t", " ")]))
    return "\n".join(lines) + "\n"
