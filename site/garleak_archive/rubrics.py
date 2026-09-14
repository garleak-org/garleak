# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only access to the rubric files in packages/rubrics (SPEC §10.3).

The rubric package is standalone and owned by its maintainers. This module only reads
its YAML; it never imports the package or writes to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RubricItem:
    id: str
    tier: str
    required: bool
    title: str
    na_allowed: bool


@dataclass
class Rubric:
    id: str
    version: str
    title: str
    status: str
    family: str
    tiers: list[str]
    items: dict[str, RubricItem] = field(default_factory=dict)

    def items_at(self, tier: str) -> list[RubricItem]:
        return [i for i in self.items.values() if i.tier == tier]

    def required_at(self, tier: str) -> list[RubricItem]:
        return [i for i in self.items_at(tier) if i.required]

    @property
    def key(self) -> str:
        return f"{self.id}@{self.version}"


class RubricSet:
    def __init__(self, rubrics: list[Rubric]):
        self._by_key = {(r.id, r.version): r for r in rubrics}

    def get(self, rubric_id: str, version: str) -> Rubric | None:
        return self._by_key.get((rubric_id, str(version)))

    def ids(self) -> set[str]:
        return {k[0] for k in self._by_key}

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self):
        return iter(self._by_key.values())

    @classmethod
    def load(cls, directory: Path | None) -> RubricSet:
        rubrics: list[Rubric] = []
        if directory is None or not directory.is_dir():
            return cls(rubrics)
        for path in sorted(directory.glob("*/v*.yaml")):
            data = yaml.safe_load(path.read_text())
            if not isinstance(data, dict) or "items" not in data:
                continue
            r = Rubric(
                id=data["id"],
                version=str(data["version"]),
                title=data.get("title", data["id"]),
                status=data.get("status", "draft"),
                family=data.get("field", data["id"]),
                tiers=list(data.get("applies_to_tiers", [])),
            )
            for it in data["items"]:
                r.items[it["id"]] = RubricItem(
                    id=it["id"],
                    tier=it["tier"],
                    required=bool(it.get("required", False)),
                    title=it.get("title", it["id"]),
                    na_allowed=bool((it.get("criteria") or {}).get("not_applicable")),
                )
            rubrics.append(r)
        return cls(rubrics)
