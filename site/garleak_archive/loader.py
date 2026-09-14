# SPDX-License-Identifier: AGPL-3.0-or-later
"""Load an archive directory into models. Problems become Issues, never exceptions, so
one bad file does not hide the others; call validate() for the full rule set."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import yaml

from . import schema
from .hashing import scratch_content_sha256
from .ids import IdentifierError, VersionNumber
from .models import (
    Account,
    Archive,
    Category,
    Claim,
    Contest,
    Declaration,
    Field,
    Fix,
    Graduation,
    Issue,
    ItemResult,
    ModelUse,
    NoveltyCheck,
    Paper,
    Prediction,
    ReaderTally,
    Scratch,
    ScreeningRecord,
    StatusChange,
    Verification,
    Version,
)
from .rubrics import RubricSet

VERSION_DIR = re.compile(r"^v([1-9][0-9]*\.(?:0|[1-9][0-9]*))$")


class _Ctx:
    def __init__(self, archive: Archive):
        self.a = archive

    def rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.a.root.parent).as_posix()
        except ValueError:
            return str(path)

    def issue(self, path: Path, msg: str, level: str = "error") -> None:
        self.a.issues.append(Issue(level, self.rel(path), msg))

    def read(self, path: Path, schema_name: str | None) -> dict | None:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as e:
            self.issue(path, f"cannot read YAML: {e}")
            return None
        if not isinstance(data, dict):
            self.issue(path, "expected a mapping at the top level")
            return None
        if schema_name:
            errs = schema.check(schema_name, data)
            for e in errs:
                self.issue(path, e)
            if errs:
                return None
        return data


def _date(v: Any) -> dt.date:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


def _opt_date(v: Any) -> dt.date | None:
    return None if v in (None, "") else _date(v)


def _models(items: list | None) -> list[ModelUse]:
    out = []
    for m in items or []:
        if isinstance(m, str):
            out.append(ModelUse(m))
        else:
            out.append(ModelUse(m["name"], m.get("provider"), None if m.get("version") is None else str(m.get("version"))))
    return out


def _version(v: Any) -> VersionNumber:
    return VersionNumber.parse(v)


def default_rubrics_dir(root: Path) -> Path:
    return (root.parent / "packages" / "rubrics").resolve()


def load_archive(root: Path, rubrics_dir: Path | None = None) -> Archive:
    root = Path(root).resolve()
    a = Archive(root=root)
    c = _Ctx(a)
    if not root.is_dir():
        c.issue(root, "archive directory does not exist")
        return a

    cfg_path = root / "archive.yaml"
    if cfg_path.exists():
        cfg = c.read(cfg_path, "archive") or {}
        a.name = cfg.get("name", a.name)
        a.example = bool(cfg.get("example", False))
        a.as_of = _opt_date(cfg.get("as_of"))
        a.new_listing_days = int(cfg.get("new_listing_days", a.new_listing_days))
        a.config_version = str(cfg.get("config_version", a.config_version))
        a.spec_version = str(cfg.get("spec_version", a.spec_version))
        if cfg.get("rubrics") and rubrics_dir is None:
            rubrics_dir = (root / cfg["rubrics"]).resolve()
    a.rubrics = RubricSet.load(rubrics_dir or default_rubrics_dir(root))

    _load_config(c, root / "config.yaml")
    _load_categories(c, root / "categories.yaml")
    for p in sorted((root / "accounts").glob("*.yaml")):
        _load_account(c, p)
    papers_dir = root / "papers"
    if papers_dir.is_dir():
        for d in sorted(papers_dir.iterdir(), key=lambda p: p.name):
            if d.is_dir():
                _load_paper(c, d)
    for p in sorted((root / "scratches").glob("*.yaml")):
        _load_scratch(c, p)
    for p in sorted((root / "screening").glob("*.yaml")):
        _load_screening(c, p)
    _after_load(c)
    return a


def _load_config(c: _Ctx, path: Path) -> None:
    """config.yaml is optional: an archive without one (the example archive) has no ledger
    and no derived loop labels."""
    if not path.exists():
        return
    data = c.read(path, "config")
    if not data:
        return
    if str(data["config_version"]) != c.a.config_version:
        c.issue(path, f"config_version {data['config_version']} differs from archive.yaml "
                f"({c.a.config_version}); records carry the version in force (§10.4)")
    c.a.config = data


def _load_categories(c: _Ctx, path: Path) -> None:
    if not path.exists():
        c.issue(path, "categories.yaml is missing")
        return
    data = c.read(path, "categories")
    if not data:
        return
    c.a.threshold = int(data.get("visibility_threshold", 5))
    for f in data["fields"]:
        fld = Field(f["code"], f["name"])
        for cat in f.get("categories", []):
            code = cat["code"]
            if code in c.a.categories:
                c.issue(path, f"category code {code} appears twice")
                continue
            if not code.startswith(fld.code + "."):
                c.issue(path, f"category {code} must start with its field code '{fld.code}.'")
            obj = Category(
                code=code,
                name=cat["name"],
                field_code=fld.code,
                field_name=fld.name,
                description=cat.get("description", ""),
                gated=bool(cat.get("gated", False)),
                threshold=int(cat.get("visibility_threshold", c.a.threshold)),
            )
            fld.categories.append(obj)
            c.a.categories[code] = obj
        c.a.fields.append(fld)


def _load_account(c: _Ctx, path: Path) -> None:
    data = c.read(path, "account")
    if not data:
        return
    handle = data["handle"]
    if handle != path.stem:
        c.issue(path, f"handle '{handle}' must match the file name '{path.stem}'")
    if handle in c.a.accounts:
        c.issue(path, f"handle '{handle}' is used twice")
        return
    agent = data.get("agent") or {}
    c.a.accounts[handle] = Account(
        handle=handle,
        display_name=data["display_name"],
        kind=data.get("kind", "human"),
        pseudonymous=bool(data.get("pseudonymous", False)),
        identity_path=data.get("identity_path"),
        orcid=data.get("orcid"),
        github=data.get("github"),
        operator=data.get("operator"),
        models=_models(agent.get("models")),
        runner_url=agent.get("runner_url"),
        status=data.get("status", "active"),
        joined=_opt_date(data.get("joined")),
        intake=data.get("intake"),
    )


def _load_paper(c: _Ctx, d: Path) -> None:
    ppath = d / "paper.yaml"
    if not ppath.exists():
        c.issue(d, "paper directory has no paper.yaml")
        return
    data = c.read(ppath, "paper")
    if not data:
        return
    if not d.name.isdigit() or d.name.startswith("0"):
        c.issue(d, "paper directories are named by number, for example papers/4471")
        return
    number = int(d.name)
    if data["id"] != f"paper:{number}":
        c.issue(ppath, f"id {data['id']} does not match the directory (paper:{number})")
    p = Paper(
        number=number,
        directory=d,
        category=data["category"],
        submitter=data["submitter"],
        created=_date(data["created"]),
        license=data.get("license", "CC-BY-4.0"),
        gated=bool(data.get("gated", False)),
        v1_sha256=data["v1_sha256"],
        version_sha256={str(k): v for k, v in (data.get("version_sha256") or {}).items()},
        track=data.get("track", "human-prompted"),
        maintainers=list(data.get("maintainers") or []),
        cross_list=list(data.get("cross_list") or []),
        promoted_from=data.get("promoted_from"),
        forked_from=data.get("forked_from"),
        status=data.get("status", "admitted"),
        withdrawal=data.get("withdrawal"),
        removal=data.get("removal"),
        community_maintained_since=_opt_date(data.get("community_maintained_since")),
    )
    if not p.maintainers:
        # The submitter maintains a paper by default; for an agent submission it is the
        # operator (SPEC §6.8.1).
        sub = c.a.accounts.get(p.submitter)
        p.maintainers = [sub.operator] if sub and sub.is_agent and sub.operator else [p.submitter]

    for vd in sorted(d.iterdir(), key=lambda x: x.name):
        if not vd.is_dir() or vd.name in ("verifications", "fixes", "signals", "graduations"):
            continue
        m = VERSION_DIR.match(vd.name)
        if not m:
            c.issue(vd, "unexpected directory; version directories are named like v1.0 or v2.3")
            continue
        v = _load_version(c, vd, VersionNumber.parse(m[1]))
        if v:
            p.versions.append(v)
    p.versions.sort(key=lambda v: v.number)

    for vp in sorted((d / "verifications").glob("*.yaml")):
        ver = _load_verification(c, vp, number)
        if ver:
            p.verifications.append(ver)
    p.verifications.sort(key=lambda v: (v.date, v.id))

    for fp in sorted((d / "fixes").glob("*.yaml")):
        fx = c.read(fp, "fix")
        if not fx:
            continue
        try:
            p.fixes.append(
                Fix(
                    id=int(fx["id"]),
                    paper=number,
                    base_version=_version(fx["base_version"]),
                    author=fx["author"],
                    date=_date(fx["date"]),
                    title=fx["title"],
                    rationale=fx.get("rationale", ""),
                    proposed_bump=fx["proposed_bump"],
                    status=fx["status"],
                    merged_into=_version(fx["merged_into"]) if fx.get("merged_into") else None,
                    addresses=[(x["verification"], x["item"]) for x in fx.get("addresses") or []],
                    model_use=fx.get("model_use") or {},
                    decline_reason=fx.get("decline_reason", ""),
                )
            )
        except IdentifierError as e:
            c.issue(fp, str(e))
    p.fixes.sort(key=lambda f: f.id)

    for sp in sorted((d / "signals").glob("*.yaml")):
        _load_signal(c, sp, p)

    for gp in sorted((d / "graduations").glob("*.yaml")):
        g = c.read(gp, "graduation")
        if not g:
            continue
        try:
            p.graduations.append(
                Graduation(
                    id=g["id"],
                    version=_version(g["version"]),
                    state=g["state"],
                    requested_by=g["requested_by"],
                    date=_date(g["date"]),
                    pair_independent=g.get("pair_independent"),
                    withdrawn=g.get("withdrawn"),
                    doi=g.get("doi"),
                )
            )
        except IdentifierError as e:
            c.issue(gp, str(e))

    if number in c.a.papers:
        c.issue(d, f"paper number {number} is used twice")
        return
    c.a.papers[number] = p


def _load_version(c: _Ctx, vd: Path, number: VersionNumber) -> Version | None:
    mpath = vd / "meta.yaml"
    if not mpath.exists():
        c.issue(vd, "version directory has no meta.yaml")
        return None
    meta = c.read(mpath, "version")
    if not meta:
        return None
    if "version" in meta:
        try:
            if _version(meta["version"]) != number:
                c.issue(mpath, f"version field {meta['version']} does not match the directory {vd.name}")
        except IdentifierError as e:
            c.issue(mpath, str(e))
    body_path = vd / "body.md"
    body = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
    if not body_path.exists():
        c.issue(vd, "version has no body.md")
    ass = meta["assistance"]
    decl = Declaration(
        writing=ass["writing"],
        analysis=ass["analysis"],
        declared_by=meta["submitted_by"],
        date=_date(meta["date"]),
        models=_models(meta.get("models")),
        tools=list(meta.get("tools") or []),
        provenance=meta.get("provenance", ""),
        version=number,
    )
    return Version(
        number=number,
        directory=vd,
        title=" ".join(meta["title"].split()),
        authors=list(meta["authors"]),
        abstract=" ".join(str(meta.get("abstract", "")).split()),
        body=body,
        date=_date(meta["date"]),
        change=meta["change"],
        note=meta.get("note", ""),
        submitted_by=meta["submitted_by"],
        declaration=decl,
        rubric_families=list(meta.get("rubric_families") or []),
        merged_fixes=[int(x) for x in meta.get("merged_fixes") or []],
        reopens=list(meta.get("reopens") or []),
        transcript=meta.get("transcript") or {},
        artifacts=list(meta.get("artifacts") or []),
        pdf=(vd / "paper.pdf") if (vd / "paper.pdf").exists() else None,
        bib=(vd / "refs.bib") if (vd / "refs.bib").exists() else None,
        source_file=body_path if body_path.exists() else None,
        intake=meta.get("intake"),
    )


def _load_verification(c: _Ctx, path: Path, paper: int) -> Verification | None:
    v = c.read(path, "verification")
    if not v:
        return None
    if v["id"] != path.stem:
        c.issue(path, f"id '{v['id']}' must match the file name '{path.stem}'")
    try:
        version = _version(v["version"])
    except IdentifierError as e:
        c.issue(path, str(e))
        return None
    return Verification(
        id=v["id"],
        paper=paper,
        version=version,
        kind=v.get("kind", "paper"),
        tier=v["tier"],
        rubric_id=v["rubric"]["id"],
        rubric_version=str(v["rubric"]["version"]),
        verifier=v["verifier"],
        date=_date(v["date"]),
        result=v["result"],
        summary=" ".join(v.get("summary", "").split()),
        items=[
            ItemResult(i["id"], i["verdict"], i.get("note", ""), list(i.get("evidence") or []))
            for i in v.get("items") or []
        ],
        automated=list(v.get("automated") or []),
        time_spent_minutes=v.get("time_spent_minutes"),
        model_use=v.get("model_use"),
        independent=v.get("independent"),
        conflict_flags=list(v.get("conflict_flags") or []),
        loop_label=v.get("loop_label"),
        status=v.get("status", "active"),
        status_history=[
            StatusChange(s["status"], s["by"], _date(s["date"]), s.get("reason", ""))
            for s in v.get("status_history") or []
        ],
        t4_attestation=v.get("t4_attestation"),
        path=path,
        attestation=v.get("attestation"),
        intake=v.get("intake"),
    )


def _load_signal(c: _Ctx, path: Path, p: Paper) -> None:
    s = c.read(path, "signal")
    if not s:
        return
    if s["id"] != path.stem:
        c.issue(path, f"id '{s['id']}' must match the file name '{path.stem}'")
    try:
        version = _version(s["version"])
    except IdentifierError as e:
        c.issue(path, str(e))
        return
    kind = s["kind"]
    if kind == "prediction":
        p.predictions.append(
            Prediction(
                id=s["id"],
                version=version,
                classifier_id=s["classifier"]["id"],
                classifier_version=str(s["classifier"]["version"]),
                date=_date(s["date"]),
                probabilities={ax: {k: float(x) for k, x in (s.get(ax) or {}).items()} for ax in ("writing", "analysis")},
                reads=s.get("reads", ""),
            )
        )
    elif kind == "readers":
        counts = {}
        for ax in ("writing", "analysis"):
            raw = s.get(ax) or {}
            if not isinstance(raw, dict):
                c.issue(path, f"{ax}: a readers tally holds a count per code")
                raw = {}
            counts[ax] = {k: int(x) for k, x in raw.items()}
        p.tallies.append(ReaderTally(id=s["id"], version=version, date=_date(s["date"]), counts=counts,
                                     intake=s.get("intake")))
    elif kind == "contest":
        p.contests.append(
            Contest(s["id"], version, s["prediction"], s["axis"], s["by"], _date(s["date"]),
                    " ".join(s["statement"].split()), intake=s.get("intake"))
        )
    elif kind == "declaration":
        d = Declaration(
            writing=s["writing"],
            analysis=s["analysis"],
            declared_by=s["by"],
            date=_date(s["date"]),
            note=s.get("note", ""),
            source=s["id"],
            version=version,
        )
        p.declarations.append(d)


def _load_scratch(c: _Ctx, path: Path) -> None:
    s = c.read(path, "scratch")
    if not s:
        return
    if not path.stem.isdigit():
        c.issue(path, "scratch files are named by number, for example scratches/8812.yaml")
        return
    number = int(path.stem)
    if s["id"] != f"scratch:{number}":
        c.issue(path, f"id {s['id']} does not match the file name (scratch:{number})")
    obj = Scratch(
        number=number,
        path=path,
        category=s["category"],
        author=s["author"],
        date=_date(s["date"]),
        statement=" ".join(s["statement"].split()),
        detail=" ".join(str(s.get("detail", "")).split()),
        models=_models(s.get("models")),
        assistance={"writing": s["assistance"]["writing"], "analysis": s["assistance"].get("analysis")},
        v1_sha256=s["v1_sha256"],
        content_sha256=scratch_content_sha256(s),
        license=s.get("license", "CC-BY-4.0"),
        gated=bool(s.get("gated", False)),
        status=s.get("status", "admitted"),
        track=s.get("track", "human-prompted"),
        withdrawal=s.get("withdrawal"),
        removal=s.get("removal"),
        claims=[Claim(x["by"], _date(x["date"]), _opt_date(x.get("expires")), x.get("intake"))
                for x in s.get("claims") or []],
        promoted_to=[int(x) for x in s.get("promoted_to") or []],
        intake=s.get("intake"),
    )
    for ch in s.get("checks") or []:
        obj.checks.append(
            NoveltyCheck(
                id=ch["id"],
                outcome=ch["outcome"],
                checker=ch["checker"],
                date=_date(ch["date"]),
                summary=" ".join(ch.get("summary", "").split()),
                sources=list(ch.get("sources") or []),
                queries=list(ch.get("queries") or []),
                closest=list(ch.get("closest") or []),
                prior_work=list(ch.get("prior_work") or []),
                tractability=" ".join(ch.get("tractability", "").split()),
                status=ch.get("status", "active"),
                time_spent_minutes=ch.get("time_spent_minutes"),
                model_use=ch.get("model_use"),
                loop_label=ch.get("loop_label"),
                intake=ch.get("intake"),
            )
        )
    obj.checks.sort(key=lambda x: (x.date, x.id))
    if number in c.a.scratches:
        c.issue(path, f"scratch number {number} is used twice")
        return
    c.a.scratches[number] = obj


def _load_screening(c: _Ctx, path: Path) -> None:
    s = c.read(path, "screening")
    if not s:
        return
    if s["id"] != path.stem:
        c.issue(path, f"id '{s['id']}' must match the file name '{path.stem}'")
    c.a.screening.append(
        ScreeningRecord(
            id=s["id"],
            decision=s["decision"],
            criterion=int(s["criterion"]),
            date=_date(s["date"]),
            object=s["object"],
            category=s["category"],
            submitter=s["submitter"],
            path=path,
            intake=s.get("intake"),
        )
    )


def _after_load(c: _Ctx) -> None:
    """Rules for the records the intake pipeline adds, and the derived loop labels.

    Loop labels are derived from the verification graph whenever an archive with a
    config.yaml is loaded (SPEC §5.6.5), so that stages, standing and the site all see the
    same labels. Derived values are never stored (FORMAT.md)."""
    a = c.a
    ids: set[str] = set()
    for s in a.screening:
        if s.id in ids:
            c.issue(s.path or a.root, f"screening id '{s.id}' is used twice")
        ids.add(s.id)
        if s.submitter not in a.accounts:
            c.issue(s.path or a.root, f"submitter '{s.submitter}' has no file in accounts/")
        if s.category not in a.categories:
            c.issue(s.path or a.root, f"unknown category '{s.category}'")
    for p in a.papers.values():
        seen: dict[VersionNumber, str] = {}
        for t in p.tallies:
            if t.version in seen:
                c.issue(p.directory / "signals" / f"{t.id}.yaml",
                        f"v{t.version} already has a readers tally ({seen[t.version]}); a vote updates it")
            seen[t.version] = t.id
    if a.config is not None:
        from .ledger import apply_loop_labels

        apply_loop_labels(a)
