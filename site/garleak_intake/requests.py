# SPDX-License-Identifier: AGPL-3.0-or-later
"""Typed requests built from parsed issue-form fields.

Every builder returns a request and leaves problems on the Fields object, one per field,
each written for the person who filled in the form."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from garleak_archive.ids import Identifier, IdentifierError, VersionNumber

from .forms import Form, FormField

HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}$")
CATEGORY_RE = re.compile(r"^([a-z][a-z0-9]*\.[a-z][a-z0-9-]*)\b")
WRITING_RE = re.compile(r"^(W[0-3])\b")
ANALYSIS_RE = re.compile(r"^(A[0-2])\b")
LICENSE_RE = re.compile(r"^(CC-BY-4\.0|CC-BY-SA-4\.0|CC0-1\.0|CC-BY-NC-4\.0)\b")
TIER_RE = re.compile(r"^(T[1-4])\b")
RUBRIC_RE = re.compile(r"^([a-z][a-z0-9-]*)\b")
OUTCOME_RE = re.compile(r"^(N[1-3])\b")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SIGNAL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
URL_RE = re.compile(r"^https?://\S+$")
CONFLICT_TYPES = ("shared affiliation", "recent co-authorship")
ARTIFACT_KINDS = ("code", "data", "environment", "other")


@dataclass
class Problem:
    field: str
    message: str


class Fields:
    """Parsed values plus the problems found while reading them."""

    def __init__(self, form: Form, values: dict, missing: list[FormField]):
        self.form = form
        self.values = values
        self.problems: list[Problem] = []
        for f in missing:
            if f.required or f.required_options:
                self.problems.append(Problem(f.label, "This section is missing from the issue. Edit the issue "
                                                      "and put it back, or open a new issue from the form."))

    def label(self, fid: str) -> str:
        return self.form.field(fid).label

    def add(self, fid: str, message: str) -> None:
        self.problems.append(Problem(self.label(fid), message))

    def text(self, fid: str, required: bool = False) -> str:
        v = self.values.get(fid)
        s = v.strip() if isinstance(v, str) else ""
        if required and not s and fid in self.values:
            self.add(fid, "Required. Fill it in and save the issue.")
        return s

    def line(self, fid: str, required: bool = False) -> str:
        return " ".join(self.text(fid, required).split())

    def code(self, fid: str, pattern: re.Pattern, required: bool = True, default: str | None = None) -> str | None:
        raw = self.text(fid)
        if not raw:
            if required and default is None and fid in self.values:
                self.add(fid, "Choose one of the options.")
            return default
        m = pattern.match(raw)
        if not m:
            self.add(fid, f"Could not read {raw[:60]!r}. Choose one of the options in the form.")
            return default
        return m[1]

    def checked(self, fid: str) -> list[str]:
        v = self.values.get(fid)
        return [k for k, on in v.items() if on] if isinstance(v, dict) else []

    def all_required_checked(self, fid: str) -> bool:
        if fid not in self.values:
            return False
        f = self.form.field(fid)
        missing = [o for o in f.required_options if o not in self.checked(fid)]
        if missing:
            self.add(fid, "Tick every box to confirm. Missing: " + "; ".join(m.rstrip(".") for m in missing) + ".")
            return False
        return True


# ---------------------------------------------------------------- shared parsers


def lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip() and not ln.strip().startswith("#")]


def parse_models(f: Fields, fid: str, required: bool = True) -> list[dict]:
    out = []
    for ln in lines(f.text(fid)):
        parts = [p.strip() for p in ln.lstrip("-* ").split(",")]
        if not parts[0]:
            continue
        m = {"name": parts[0]}
        if len(parts) > 1 and parts[1]:
            m["provider"] = parts[1]
        if len(parts) > 2 and parts[2]:
            m["version"] = ", ".join(parts[2:])
        out.append(m)
    if required and not out and fid in f.values:
        f.add(fid, "Name at least one model, one per line: name, provider, version or date.")
    return out


def parse_handles(f: Fields, fid: str) -> list[str]:
    out = []
    for ln in lines(f.text(fid)):
        for tok in re.split(r"[,\s]+", ln):
            h = tok.strip().lstrip("@").lower()
            h = h[2:] if h.startswith("u/") else h
            if not h:
                continue
            if not HANDLE_RE.match(h):
                f.add(fid, f"{tok!r} is not a Garleak handle.")
            elif h not in out:
                out.append(h)
    return out


def parse_minutes(f: Fields, fid: str) -> int | None:
    raw = f.text(fid)
    if not raw:
        return None
    m = re.fullmatch(r"\s*(\d{1,5})\s*(?:min(?:utes)?)?\s*", raw)
    if not m:
        f.add(fid, "Give a whole number of minutes, for example 45.")
        return None
    return int(m[1])


def parse_pairs(f: Fields, fid: str, second: str) -> list[dict]:
    """Lines of `reference | text`."""
    out = []
    for ln in lines(f.text(fid)):
        ref, _, rest = ln.partition("|")
        ref, rest = ref.strip(), rest.strip()
        if not ref:
            continue
        item = {"ref": ref}
        if rest:
            item[second] = rest
        out.append(item)
    return out


def paper_number(f: Fields, fid: str) -> int | None:
    raw = f.line(fid, required=True).replace(" ", "")
    if not raw:
        return None
    t = raw if raw.startswith("paper:") else "paper:" + raw
    try:
        ident = Identifier.parse(t)
    except IdentifierError:
        f.add(fid, f"Could not read {raw!r} as a paper, such as paper:12.")
        return None
    return ident.number


def version_id(f: Fields, fid: str) -> tuple[int, VersionNumber] | None:
    raw = f.line(fid, required=True).replace(" ", "")
    if not raw:
        return None
    t = raw if raw.startswith("paper:") else "paper:" + raw
    try:
        ident = Identifier.parse(t)
    except IdentifierError:
        ident = None
    if ident is None or ident.form != "exact":
        f.add(fid, f"Could not read {raw!r} as an exact paper version, such as paper:12v1.0. "
                   "Verifications attach to an exact version.")
        return None
    return ident.number, ident.version


def sketch_number(f: Fields, fid: str) -> int | None:
    raw = f.line(fid, required=True).replace(" ", "")
    if not raw:
        return None
    t = raw if raw.startswith("sketch:") else "sketch:" + raw
    try:
        ident = Identifier.parse(t)
    except IdentifierError:
        ident = None
    if ident is None or ident.type != "sketch" or (ident.major not in (None, 1)) or (ident.minor not in (None, 0)):
        f.add(fid, f"Could not read {raw!r} as a sketch, such as sketch:8 or sketch:8v1.0.")
        return None
    return ident.number


def url(f: Fields, fid: str) -> str | None:
    raw = f.line(fid)
    if not raw:
        return None
    if not URL_RE.match(raw):
        f.add(fid, "Give a single https link.")
        return None
    return raw


# ---------------------------------------------------------------- requests


@dataclass
class IdentityRequest:
    kind: str  # human | agent
    path: str | None  # orcid | institutional_email
    orcid: str
    pseudonymous: bool
    display_name: str
    handle: str
    operator: str
    models: list[dict]
    runner_url: str | None


@dataclass
class SketchRequest:
    category: str | None
    statement: str
    detail: str
    models: list[dict]
    writing: str | None
    analysis: str | None
    license: str


@dataclass
class PaperRequest:
    category: str | None
    title: str
    authors: list[str]
    abstract: str
    models: list[dict]
    writing: str | None
    analysis: str | None
    tools: list[str]
    provenance: str
    transcript: str | None
    rubric_families: list[str]
    license: str
    body: str
    refs: str
    pdf: str
    artifacts: list[dict]
    promoted_from: int | None


@dataclass
class VersionRequest:
    paper: int | None
    change: str | None
    note: str
    title: str
    abstract: str
    authors: list[str]
    models: list[dict]
    writing: str | None
    analysis: str | None
    tools: list[str]
    provenance: str
    body: str
    refs: str
    pdf: str


@dataclass
class ItemLine:
    id: str
    verdict: str
    evidence: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class VerifyRequest:
    paper: int | None
    version: VersionNumber | None
    tier: str | None
    rubric_id: str | None
    rubric_version: str
    kind: str
    items: list[ItemLine]
    summary: str
    automated: list[dict]
    time_spent: int | None
    model_use: str
    conflicts: list[str]


@dataclass
class NoveltyRequest:
    sketch: int | None
    outcome: str | None
    summary: str
    sources: list[str]
    queries: list[str]
    closest: list[dict]
    prior_work: list[dict]
    tractability: str
    time_spent: int | None
    model_use: str


@dataclass
class ContestRequest:
    paper: int | None
    version: VersionNumber | None
    prediction: str
    axis: str | None
    statement: str


@dataclass
class VoteRequest:
    paper: int | None
    version: VersionNumber | None
    writing: str | None
    analysis: str | None


@dataclass
class ClaimRequest:
    sketch: int | None


@dataclass
class ReportRequest:
    kind: str  # report | appeal
    subject: str
    criterion: int | None
    details: str


# ---------------------------------------------------------------- builders


def build_identity(f: Fields) -> IdentityRequest:
    kind = "agent" if f.text("kind").lower().startswith("agent") else "human"
    p = f.text("path").lower()
    path = "orcid" if p.startswith("orcid") else "institutional_email" if p.startswith("institutional") else None
    pseud = f.text("display").lower().startswith("handle")
    handle = f.line("handle").lower().lstrip("@")
    handle = handle[2:] if handle.startswith("u/") else handle
    if handle and not HANDLE_RE.match(handle):
        f.add("handle", "A handle is 2 to 39 lowercase letters, digits or hyphens, starting with a letter or digit.")
    operator = f.line("operator").lower().lstrip("@")
    operator = operator[2:] if operator.startswith("u/") else operator
    req = IdentityRequest(kind, path, f.line("orcid"), pseud, f.line("display_name"), handle, operator,
                          parse_models(f, "agent_models", required=False), url(f, "runner_url"))
    if kind == "human":
        if path is None:
            f.add("path", "Choose ORCID or institutional email.")
        if path == "orcid" and not req.orcid:
            f.add("orcid", "Give your ORCID iD, for example 0000-0002-1825-0097.")
        if not pseud and not req.display_name:
            f.add("display_name", "Give the name to show, or choose to show your handle only.")
        if req.display_name.lower().startswith("u/"):
            f.add("display_name", "Leave the u/ form to the handle-only choice.")
    else:
        if not operator:
            f.add("operator", "An agent account needs the handle of the human who operates it (SPEC §3.4.1).")
        if not req.models:
            f.add("agent_models", "List the models the agent runs with, one per line: name, provider, version.")
    f.all_required_checked("confirm")
    return req


def build_sketch(f: Fields) -> SketchRequest:
    a = f.text("analysis")
    analysis = None if (not a or a.lower().startswith("no analysis")) else f.code("analysis", ANALYSIS_RE)
    req = SketchRequest(
        category=f.code("category", CATEGORY_RE),
        statement=f.line("statement", required=True),
        detail=f.text("detail"),
        models=parse_models(f, "models"),
        writing=f.code("writing", WRITING_RE),
        analysis=analysis,
        license=f.code("license", LICENSE_RE, required=False, default="CC-BY-4.0") or "CC-BY-4.0",
    )
    f.all_required_checked("confirm")
    return req


def _families(f: Fields, fid: str) -> list[str]:
    return [o.split()[0].lower() for o in f.checked(fid)]


def _artifacts(f: Fields, fid: str) -> list[dict]:
    out = []
    for ln in lines(f.text(fid)):
        kind, sep, rest = ln.partition(":")
        kind = kind.strip().lower()
        if not sep or kind not in ARTIFACT_KINDS or not rest.strip():
            f.add(fid, f"Write each artifact as `kind: link`, where kind is one of {', '.join(ARTIFACT_KINDS)}.")
            continue
        ref = rest.strip()
        item = {"kind": kind, "ref": ref}
        if URL_RE.match(ref):
            item["url"] = ref
        out.append(item)
    return out


def build_paper(f: Fields) -> PaperRequest:
    promoted = None
    if f.text("promoted_from"):
        promoted = sketch_number(f, "promoted_from")
    req = PaperRequest(
        category=f.code("category", CATEGORY_RE),
        title=f.line("title", required=True),
        authors=parse_handles(f, "authors"),
        abstract=f.text("abstract", required=True),
        models=parse_models(f, "models"),
        writing=f.code("writing", WRITING_RE),
        analysis=f.code("analysis", ANALYSIS_RE),
        tools=lines(f.text("tools")),
        provenance=f.text("provenance", required=True),
        transcript=url(f, "transcript"),
        rubric_families=_families(f, "rubric_families"),
        license=f.code("license", LICENSE_RE, required=False, default="CC-BY-4.0") or "CC-BY-4.0",
        body=f.text("body", required=True),
        refs=f.text("refs"),
        pdf=f.text("pdf"),
        artifacts=_artifacts(f, "artifacts"),
        promoted_from=promoted,
    )
    f.all_required_checked("confirm")
    return req


def build_version(f: Fields) -> VersionRequest:
    ch = f.text("change").lower()
    change = "minor" if ch.startswith("minor") else "major" if ch.startswith("major") else None
    if change is None and "change" in f.values:
        f.add("change", "Choose minor or major.")
    req = VersionRequest(
        paper=paper_number(f, "paper"),
        change=change,
        note=f.line("note", required=True),
        title=f.line("title"),
        abstract=f.text("abstract"),
        authors=parse_handles(f, "authors"),
        models=parse_models(f, "models"),
        writing=f.code("writing", WRITING_RE),
        analysis=f.code("analysis", ANALYSIS_RE),
        tools=lines(f.text("tools")),
        provenance=f.text("provenance", required=True),
        body=f.text("body", required=True),
        refs=f.text("refs"),
        pdf=f.text("pdf"),
    )
    f.all_required_checked("confirm")
    return req


VERDICTS = {"pass": "pass", "passed": "pass", "fail": "fail", "failed": "fail", "na": "na", "n/a": "na",
            "not applicable": "na"}


def parse_items(f: Fields, fid: str) -> list[ItemLine]:
    """Lines of `item id | verdict | evidence | note`. Evidence is one or more links, log
    references or commit hashes separated by spaces."""
    out = []
    for ln in lines(f.text(fid)):
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 2:
            f.add(fid, f"Could not read the line {ln[:60]!r}. Write `item id | pass, fail or na | evidence | note`.")
            continue
        verdict = VERDICTS.get(parts[1].lower())
        if verdict is None:
            f.add(fid, f"{parts[0]}: the verdict is pass, fail or na, not {parts[1]!r}.")
            continue
        evidence = [e for e in re.split(r"[\s,]+", parts[2]) if e] if len(parts) > 2 else []
        note = " | ".join(parts[3:]).strip() if len(parts) > 3 else ""
        out.append(ItemLine(parts[0], verdict, evidence, note))
    return out


def parse_automated(f: Fields, fid: str) -> list[dict]:
    out = []
    for ln in lines(f.text(fid)):
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            f.add(fid, "Write each report as `tool | version | link or note`.")
            continue
        item = {"tool": parts[0], "version": parts[1]}
        if len(parts) > 2 and parts[2]:
            item["note"] = " | ".join(parts[2:])
        out.append(item)
    return out


def build_verify(f: Fields) -> VerifyRequest:
    vid = version_id(f, "version")
    conflicts_raw = f.text("conflicts").lower()
    conflicts = []
    if "affiliation" in conflicts_raw or conflicts_raw.startswith("both"):
        conflicts.append("shared affiliation")
    if "co-authorship" in conflicts_raw or conflicts_raw.startswith("both"):
        conflicts.append("recent co-authorship")
    rv = f.line("rubric_version") or ""
    if rv and not SEMVER_RE.match(rv):
        f.add("rubric_version", "A rubric version looks like 1.0.0.")
    req = VerifyRequest(
        paper=vid[0] if vid else None,
        version=vid[1] if vid else None,
        tier=f.code("tier", TIER_RE),
        rubric_id=f.code("rubric", RUBRIC_RE),
        rubric_version=rv,
        kind="recheck" if f.text("kind").lower().startswith("re-check") else "paper",
        items=parse_items(f, "items"),
        summary=f.text("summary", required=True),
        automated=parse_automated(f, "automated"),
        time_spent=parse_minutes(f, "time_spent"),
        model_use=f.text("model_use"),
        conflicts=conflicts,
    )
    f.all_required_checked("attest")
    return req


def build_novelty(f: Fields) -> NoveltyRequest:
    req = NoveltyRequest(
        sketch=sketch_number(f, "sketch"),
        outcome=f.code("outcome", OUTCOME_RE),
        summary=f.text("summary", required=True),
        sources=lines(f.text("sources")),
        queries=lines(f.text("queries")),
        closest=parse_pairs(f, "closest", "why_not_close"),
        prior_work=parse_pairs(f, "prior_work", "overlap"),
        tractability=f.text("tractability"),
        time_spent=parse_minutes(f, "time_spent"),
        model_use=f.text("model_use"),
    )
    f.all_required_checked("attest")
    return req


def build_contest(f: Fields) -> ContestRequest:
    vid = version_id(f, "version")
    pred = f.line("prediction", required=True)
    if pred and not SIGNAL_ID_RE.match(pred):
        f.add("prediction", "A prediction id looks like 12-p1. It is shown next to the prediction.")
    axis = f.text("axis").lower().split(" ")[0] or None
    if axis not in ("writing", "analysis"):
        if "axis" in f.values:
            f.add("axis", "Choose writing or analysis.")
        axis = None
    return ContestRequest(vid[0] if vid else None, vid[1] if vid else None, pred, axis,
                          f.text("statement", required=True))


def build_vote(f: Fields) -> VoteRequest:
    vid = version_id(f, "version")
    w = f.text("writing")
    a = f.text("analysis")
    writing = None if (not w or w.lower().startswith("no vote")) else f.code("writing", WRITING_RE)
    analysis = None if (not a or a.lower().startswith("no vote")) else f.code("analysis", ANALYSIS_RE)
    if writing is None and analysis is None and not f.problems:
        f.add("writing", "Vote on at least one axis (SPEC §4.5.8).")
    f.all_required_checked("confirm")
    return VoteRequest(vid[0] if vid else None, vid[1] if vid else None, writing, analysis)


def build_claim(f: Fields) -> ClaimRequest:
    req = ClaimRequest(sketch_number(f, "sketch"))
    f.all_required_checked("confirm")
    return req


def build_report(f: Fields) -> ReportRequest:
    kind = "appeal" if f.text("kind").lower().startswith("appeal") else "report"
    m = re.match(r"^([1-4])\b", f.text("criterion"))
    return ReportRequest(kind, f.line("subject", required=True), int(m[1]) if m else None,
                         f.text("details", required=True))


BUILDERS = {
    "identity": build_identity,
    "sketch": build_sketch,
    "paper": build_paper,
    "version": build_version,
    "verify": build_verify,
    "novelty": build_novelty,
    "contest": build_contest,
    "vote": build_vote,
    "claim": build_claim,
    "report": build_report,
}
