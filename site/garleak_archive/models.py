# SPDX-License-Identifier: AGPL-3.0-or-later
"""Dataclass models for the archive records. Field names follow the files described in
archive/FORMAT.md, which also maps each one to its SPEC §11 name."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from .ids import Identifier, VersionNumber, exact
from .rubrics import RubricSet


@dataclass
class Issue:
    level: str  # "error" | "warning"
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.path}: {self.message}"


@dataclass
class Category:
    code: str
    name: str
    field_code: str
    field_name: str
    description: str = ""
    gated: bool = False
    threshold: int = 5


@dataclass
class Field:
    code: str
    name: str
    categories: list[Category] = field(default_factory=list)


@dataclass
class ModelUse:
    name: str
    provider: str | None = None
    version: str | None = None


@dataclass
class Account:
    """The public part of an account. Held identity (SPEC §11.1, H) is never loaded,
    because it is never in the repository."""

    handle: str
    display_name: str
    kind: str = "human"  # human | agent
    pseudonymous: bool = False
    identity_path: str | None = None  # orcid | institutional_email
    orcid: str | None = None
    github: str | None = None
    operator: str | None = None
    models: list[ModelUse] = field(default_factory=list)
    runner_url: str | None = None
    status: str = "active"
    joined: dt.date | None = None
    intake: dict | None = None  # {path, issue, at}: how the record arrived (RFC 0001)

    @property
    def is_agent(self) -> bool:
        return self.kind == "agent"


@dataclass
class Declaration:
    writing: str
    analysis: str | None
    declared_by: str
    date: dt.date
    models: list[ModelUse] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    provenance: str = ""
    note: str = ""
    source: str = "meta"  # "meta" or the id of the signal record that restated it
    version: VersionNumber | None = None


@dataclass
class Version:
    number: VersionNumber
    directory: Path
    title: str
    authors: list[str]
    abstract: str
    body: str
    date: dt.date
    change: str  # initial | minor | major
    note: str
    submitted_by: str
    declaration: Declaration
    rubric_families: list[str] = field(default_factory=list)
    merged_fixes: list[int] = field(default_factory=list)
    reopens: list[str] = field(default_factory=list)
    transcript: dict = field(default_factory=dict)
    artifacts: list[dict] = field(default_factory=list)
    pdf: Path | None = None
    bib: Path | None = None
    source_file: Path | None = None
    intake: dict | None = None

    @property
    def label(self) -> str:
        return f"v{self.number}"


@dataclass
class ItemResult:
    item_id: str
    verdict: str  # pass | fail | na
    note: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass
class StatusChange:
    status: str
    by: str
    date: dt.date
    reason: str = ""


@dataclass
class Verification:
    id: str
    paper: int
    version: VersionNumber
    kind: str  # paper | recheck
    tier: str
    rubric_id: str
    rubric_version: str
    verifier: str
    date: dt.date
    result: str  # passed | failed
    summary: str
    items: list[ItemResult] = field(default_factory=list)
    automated: list[dict] = field(default_factory=list)
    time_spent_minutes: int | None = None
    model_use: str | None = None
    independent: dict | None = None  # {value, computed_at, sources}
    conflict_flags: list[dict] = field(default_factory=list)  # [{type, computed_at, sources}]
    loop_label: dict | None = None  # stored by hand, or derived at load (garleak_archive.ledger)
    status: str = "active"
    status_history: list[StatusChange] = field(default_factory=list)
    t4_attestation: dict | None = None
    path: Path | None = None
    attestation: dict | None = None
    intake: dict | None = None

    @property
    def rubric_key(self) -> str:
        return f"{self.rubric_id} {self.rubric_version}"

    @property
    def recorded_independent(self) -> bool:
        """True only when a conflict check was recorded and found the verifier independent."""
        return bool(self.independent and self.independent.get("value") is True and not self.conflict_flags)

    @property
    def flag_types(self) -> list[str]:
        return [f["type"] for f in self.conflict_flags]


@dataclass
class Fix:
    id: int
    paper: int
    base_version: VersionNumber
    author: str
    date: dt.date
    title: str
    rationale: str
    proposed_bump: str
    status: str
    merged_into: VersionNumber | None = None
    addresses: list[tuple[str, str]] = field(default_factory=list)
    model_use: dict = field(default_factory=dict)
    decline_reason: str = ""


@dataclass
class Prediction:
    id: str
    version: VersionNumber
    classifier_id: str
    classifier_version: str
    date: dt.date
    probabilities: dict[str, dict[str, float]]  # axis -> code -> p
    reads: str = ""


@dataclass
class ReaderTally:
    id: str
    version: VersionNumber
    date: dt.date
    counts: dict[str, dict[str, int]]  # axis -> code -> votes
    intake: dict | None = None


@dataclass
class Contest:
    id: str
    version: VersionNumber
    prediction: str
    axis: str
    by: str
    date: dt.date
    statement: str
    intake: dict | None = None


@dataclass
class Graduation:
    id: str
    version: VersionNumber
    state: str  # graduated | withdrawn
    requested_by: str
    date: dt.date
    pair_independent: dict | None = None
    withdrawn: dict | None = None
    doi: str | None = None


@dataclass
class Paper:
    number: int
    directory: Path
    category: str
    submitter: str
    created: dt.date
    license: str
    gated: bool
    v1_sha256: str
    version_sha256: dict[str, str] = field(default_factory=dict)
    track: str = "human-prompted"
    maintainers: list[str] = field(default_factory=list)
    cross_list: list[str] = field(default_factory=list)
    promoted_from: str | None = None
    forked_from: str | None = None
    status: str = "admitted"
    withdrawal: dict | None = None
    removal: dict | None = None
    community_maintained_since: dt.date | None = None
    versions: list[Version] = field(default_factory=list)
    verifications: list[Verification] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)
    predictions: list[Prediction] = field(default_factory=list)
    tallies: list[ReaderTally] = field(default_factory=list)
    contests: list[Contest] = field(default_factory=list)
    declarations: list[Declaration] = field(default_factory=list)  # restatements after v1.0
    graduations: list[Graduation] = field(default_factory=list)

    @property
    def id(self) -> Identifier:
        return Identifier("paper", self.number)

    @property
    def current(self) -> Version:
        return self.versions[-1]

    def version(self, number: VersionNumber) -> Version | None:
        for v in self.versions:
            if v.number == number:
                return v
        return None

    def series(self, major: int) -> Version | None:
        """Latest minor version within a major (SPEC §2.3.3, OQ-3)."""
        found = [v for v in self.versions if v.number.major == major]
        return found[-1] if found else None

    def exact_id(self, number: VersionNumber) -> Identifier:
        return exact("paper", self.number, number)

    def parent(self, version: Version) -> Version | None:
        i = self.versions.index(version)
        return self.versions[i - 1] if i > 0 else None

    def declaration_for(self, number: VersionNumber) -> Declaration:
        """Current declaration of a version: the latest restatement, else the one in meta."""
        restated = [d for d in self.declarations if d.version == number]
        if restated:
            return sorted(restated, key=lambda d: d.date)[-1]
        v = self.version(number)
        assert v is not None
        return v.declaration

    def declaration_history(self, number: VersionNumber) -> list[Declaration]:
        v = self.version(number)
        assert v is not None
        rest = [d for d in self.declarations if d.version == number]
        return [v.declaration] + sorted(rest, key=lambda d: d.date)


@dataclass
class NoveltyCheck:
    id: str
    outcome: str  # N1 | N2 | N3
    checker: str
    date: dt.date
    summary: str = ""
    sources: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    closest: list[dict] = field(default_factory=list)
    prior_work: list[dict] = field(default_factory=list)
    tractability: str = ""
    status: str = "active"
    time_spent_minutes: int | None = None
    model_use: str | None = None
    loop_label: dict | None = None  # stored by hand, or derived at load (garleak_archive.ledger)
    intake: dict | None = None


@dataclass
class Claim:
    by: str
    date: dt.date
    expires: dt.date | None = None
    intake: dict | None = None


@dataclass
class Sketch:
    number: int
    path: Path
    category: str
    author: str
    date: dt.date
    statement: str
    detail: str = ""
    models: list[ModelUse] = field(default_factory=list)
    assistance: dict | None = None  # {writing, analysis or None}
    v1_sha256: str = ""
    content_sha256: str = ""  # recomputed from the file on load
    license: str = "CC-BY-4.0"
    gated: bool = False
    status: str = "admitted"
    track: str = "human-prompted"
    withdrawal: dict | None = None
    removal: dict | None = None
    checks: list[NoveltyCheck] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    promoted_to: list[int] = field(default_factory=list)
    intake: dict | None = None

    @property
    def id(self) -> Identifier:
        return Identifier("sketch", self.number)

    @property
    def exact_id(self) -> Identifier:
        return Identifier("sketch", self.number, 1, 0)


@dataclass
class ScreeningRecord:
    """The public part of a rejection that keeps its credit charge (SPEC §5.4.5, §11.15).
    The reason, the moderator and the automated scores are restricted and never stored."""

    id: str
    decision: str  # reject
    criterion: int
    date: dt.date
    object: str  # paper | sketch
    category: str
    submitter: str
    path: Path | None = None
    intake: dict | None = None
    moderator: str | None = None  # restricted (SPEC §11.15); never in the Phase 1 schema


@dataclass
class Archive:
    root: Path
    name: str = "Garleak archive"
    example: bool = False
    as_of: dt.date | None = None
    recent_count: int = 50
    config_version: str = "0.1"
    spec_version: str = "0.2"
    threshold: int = 5
    fields: list[Field] = field(default_factory=list)
    categories: dict[str, Category] = field(default_factory=dict)
    accounts: dict[str, Account] = field(default_factory=dict)
    papers: dict[int, Paper] = field(default_factory=dict)
    sketches: dict[int, Sketch] = field(default_factory=dict)
    rubrics: RubricSet = field(default_factory=lambda: RubricSet([]))
    issues: list[Issue] = field(default_factory=list)
    config: dict | None = None  # config.yaml, the versioned instrument configuration (SPEC §10.4)
    screening: list[ScreeningRecord] = field(default_factory=list)

    def account(self, handle: str) -> Account | None:
        return self.accounts.get(handle)

    def name_of(self, handle: str) -> str:
        a = self.accounts.get(handle)
        return a.display_name if a else handle

    def field_of(self, category: str) -> str | None:
        cat = self.categories.get(category)
        return cat.field_code if cat else None

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]
