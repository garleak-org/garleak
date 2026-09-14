# SPDX-License-Identifier: AGPL-3.0-or-later
"""Writing records in the layout of archive/FORMAT.md."""

from __future__ import annotations

from pathlib import Path

import yaml


def dump(data: dict) -> str:
    """YAML as FORMAT.md asks: UTF-8, keys in the order given, dates and version numbers as
    quoted strings (PyYAML quotes any string that would otherwise read as a date or number)."""
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100, default_flow_style=False)


def intake_block(issue: int | None, at: str, path: str = "issue-form") -> dict:
    block: dict = {"path": path}
    if issue is not None:
        block["issue"] = int(issue)
    block["at"] = at
    return block


class Writer:
    """Writes files under an archive root and remembers which it created or changed."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.created: list[str] = []
        self.updated: list[str] = []

    def _target(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError(f"refusing to write outside the archive: {rel}")
        (self.updated if p.exists() else self.created).append(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def text(self, rel: str, content: str) -> None:
        content = content.replace("\r\n", "\n")
        if not content.endswith("\n"):
            content += "\n"
        self._target(rel).write_text(content, encoding="utf-8")

    def binary(self, rel: str, data: bytes) -> None:
        self._target(rel).write_bytes(data)

    def data(self, rel: str, obj: dict) -> None:
        self.text(rel, dump(obj))

    def load(self, rel: str) -> dict:
        return yaml.safe_load((self.root / rel).read_text(encoding="utf-8"))

    @property
    def files(self) -> list[str]:
        return sorted(set(self.created) | set(self.updated))
