# SPDX-License-Identifier: AGPL-3.0-or-later
"""Data classes shared by parsers, resolvers, the checker, and the report writer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    """Per-reference verdicts. This enum is part of the report schema (v1); do not rename."""

    VERIFIED = "verified"
    ID_MISMATCH_REAL_REF = "id_mismatch_real_ref"
    METADATA_MISMATCH = "metadata_mismatch"
    UNRESOLVED = "unresolved"
    NOT_CHECKABLE = "not_checkable"


VERDICT_ORDER = [
    Verdict.VERIFIED,
    Verdict.ID_MISMATCH_REAL_REF,
    Verdict.METADATA_MISMATCH,
    Verdict.UNRESOLVED,
    Verdict.NOT_CHECKABLE,
]


def confidence_label(c: float) -> str:
    if c >= 0.8:
        return "high"
    if c >= 0.5:
        return "medium"
    return "low"


@dataclass
class Reference:
    """One entry of a reference list, as parsed from the input."""

    index: int
    raw: str
    source_format: str
    key: str | None = None
    entry_type: str | None = None
    title: str | None = None
    title_reliable: bool = False
    authors: list[str] = field(default_factory=list)  # family names, in order
    collaboration: str | None = None
    year: int | None = None
    journal: str | None = None
    volume: str | None = None
    page: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    bibcode: str | None = None
    bibcode_hint: str | None = None  # a bibcode-shaped citation key (not printed in the paper)
    url: str | None = None
    flags: list[str] = field(default_factory=list)

    def has_identifier(self) -> bool:
        return bool(self.doi or self.arxiv or self.bibcode)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "entry_type": self.entry_type,
            "title": self.title,
            "title_reliable": self.title_reliable,
            "authors": list(self.authors),
            "collaboration": self.collaboration,
            "year": self.year,
            "journal": self.journal,
            "volume": self.volume,
            "page": self.page,
            "identifiers": {
                k: v
                for k, v in (
                    ("doi", self.doi),
                    ("arxiv", self.arxiv),
                    ("bibcode", self.bibcode),
                    ("url", self.url),
                )
                if v
            },
            "flags": list(self.flags),
        }


@dataclass
class Record:
    """A bibliographic record returned by a resolver."""

    source: str
    ids: dict[str, str] = field(default_factory=dict)
    title: str | None = None
    authors: list[str] = field(default_factory=list)  # display names
    family_names: list[str] = field(default_factory=list)
    year: int | None = None
    container: str | None = None
    volume: str | None = None
    page: str | None = None
    type: str | None = None
    registry: str | None = None
    related_ids: dict[str, str] = field(default_factory=dict)  # e.g. journal DOI of an arXiv preprint
    issue: str | None = None  # JCAP/JHEP print the issue where other journals print the volume

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "source": self.source,
            "ids": dict(self.ids),
            "title": self.title,
            "authors": self.authors[:10],
            "n_authors": len(self.authors),
            "year": self.year,
            "container": self.container,
            "volume": self.volume,
            "issue": self.issue,
            "page": self.page,
            "type": self.type,
            "registry": self.registry,
        }
        if self.related_ids:
            d["related_ids"] = dict(self.related_ids)
        return d


@dataclass
class Evidence:
    """One step of the checking trail: what was asked, of whom, and what came back."""

    resolver: str
    action: str
    query: str
    status: str  # found | not_found | error | offline_miss | skipped
    record: Record | None = None
    scores: dict[str, Any] | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolver": self.resolver,
            "action": self.action,
            "query": self.query,
            "status": self.status,
            "record": self.record.to_dict() if self.record else None,
            "scores": self.scores,
            "note": self.note,
        }


@dataclass
class RefResult:
    reference: Reference
    verdict: Verdict
    confidence: float
    reason: str
    corrected_ids: dict[str, str] = field(default_factory=dict)
    matched_record: Record | None = None
    scores: dict[str, Any] | None = None
    evidence: list[Evidence] = field(default_factory=list)
    incomplete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.reference.index,
            "key": self.reference.key,
            "raw": self.reference.raw,
            "parsed": self.reference.to_dict(),
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 3),
            "confidence_label": confidence_label(self.confidence),
            "reason": self.reason,
            "corrected_ids": dict(self.corrected_ids),
            "matched_record": self.matched_record.to_dict() if self.matched_record else None,
            "scores": self.scores,
            "incomplete": self.incomplete,
            "evidence": [e.to_dict() for e in self.evidence],
        }
