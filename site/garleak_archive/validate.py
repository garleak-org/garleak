# SPDX-License-Identifier: AGPL-3.0-or-later
"""The archive rules that go beyond file shape. Schema errors are reported by the loader;
this module checks references between records, the immutability guard, rubric use,
version numbering, and the stage rules the build relies on."""

from __future__ import annotations

from pathlib import Path

from .assistance import ANALYSIS, WRITING
from .hashing import tree_sha256
from .ids import Identifier, IdentifierError, VersionNumber
from .loader import load_archive
from .models import Archive, Issue, Paper
from .stages import CITATIONS, compute_paper, contributors, graduation_check, independence


class _V:
    def __init__(self, a: Archive):
        self.a = a
        self.issues: list[Issue] = []

    def rel(self, p: Path | str) -> str:
        p = Path(p)
        try:
            return p.relative_to(self.a.root.parent).as_posix()
        except ValueError:
            return str(p)

    def err(self, path, msg: str) -> None:
        self.issues.append(Issue("error", self.rel(path), msg))

    def warn(self, path, msg: str) -> None:
        self.issues.append(Issue("warning", self.rel(path), msg))

    def account(self, path, handle: str, what: str, human: bool = False) -> bool:
        acc = self.a.accounts.get(handle)
        if acc is None:
            self.err(path, f"{what} '{handle}' has no file in accounts/")
            return False
        if human and acc.is_agent:
            self.err(path, f"{what} '{handle}' must be a human account")
            return False
        return True


def validate(archive: Archive) -> list[Issue]:
    v = _V(archive)
    a = archive
    _accounts(v)
    seen_ids: dict[str, str] = {}

    def unique(kind: str, id_: str, path) -> None:
        key = f"{kind}:{id_}"
        if key in seen_ids:
            v.err(path, f"{kind} id '{id_}' is also used in {seen_ids[key]}")
        else:
            seen_ids[key] = v.rel(path)

    for p in a.papers.values():
        _paper(v, p, unique)
    for s in a.sketches.values():
        path = s.path
        if s.v1_sha256 != s.content_sha256:
            v.err(path, f"the content fields do not match v1_sha256 (got {s.content_sha256}). "
                  "A sketch's v1.0 is immutable (§6.1.1)")
        if s.category not in a.categories:
            v.err(path, f"unknown category '{s.category}'")
        elif a.categories[s.category].gated != s.gated:
            v.err(path, f"gated must be {a.categories[s.category].gated} in category {s.category}")
        v.account(path, s.author, "author")
        author = a.accounts.get(s.author)
        if author and author.is_agent and s.gated:
            v.err(path, "agent accounts are excluded from gated categories (§3.4.5)")
        if author and (s.track == "autonomous") != author.is_agent:
            v.err(path, "track must be 'autonomous' exactly when the author is an agent account (§3.5.1)")
        if s.assistance:
            _codes(v, path, s.assistance, analysis_optional=True)
        earlier_base = False
        for ch in s.checks:
            unique("check", ch.id, path)
            if v.account(path, ch.checker, "checker", human=True) and ch.checker == s.author:
                v.err(path, f"check {ch.id}: an author may not check their own sketch (§4.4.3)")
            if ch.outcome == "N1" and not (ch.sources and (ch.queries or ch.summary)):
                v.err(path, f"check {ch.id}: N1 needs the sources searched and the queries (§2.5.2)")
            if ch.outcome == "N2" and not ch.prior_work:
                v.err(path, f"check {ch.id}: N2 needs at least one prior work with its overlap (§2.5.3)")
            if ch.outcome == "N3":
                if not ch.tractability:
                    v.err(path, f"check {ch.id}: N3 needs a tractability note (§2.5.5)")
                if not earlier_base:
                    v.err(path, f"check {ch.id}: N3 needs an earlier N1 or N2 check (§2.5.5)")
            if ch.outcome in ("N1", "N2") and ch.status == "active":
                earlier_base = True
        for c in s.claims:
            v.account(path, c.by, "claim by")
        for n in s.promoted_to:
            p = a.papers.get(n)
            if p is None:
                v.err(path, f"promoted_to paper:{n} does not exist")
            elif not (p.promoted_from or "").startswith(f"sketch:{s.number}v"):
                v.err(path, f"paper:{n} does not carry promoted_from sketch:{s.number} (§2.6.2)")
    return archive.issues + v.issues


def _accounts(v: _V) -> None:
    for acc in v.a.accounts.values():
        path = v.a.root / "accounts" / f"{acc.handle}.yaml"
        if acc.is_agent:
            if not acc.operator:
                v.err(path, "agent accounts need an operator (§3.4.1)")
            else:
                op = v.a.accounts.get(acc.operator)
                if op is None or op.is_agent:
                    v.err(path, f"operator '{acc.operator}' must be a human account in accounts/")
        elif acc.operator:
            v.err(path, "only agent accounts have an operator")
        if acc.is_agent and acc.identity_path:
            v.err(path, "agent accounts have no identity path; their operator does (§3.4.1)")
        if not acc.is_agent and not acc.identity_path:
            v.err(path, "a human account records how it was verified: identity_path orcid or institutional_email (§3.2.3)")
        if acc.pseudonymous and acc.display_name != f"u/{acc.handle}":
            v.err(path, f"a pseudonymous account displays as u/{acc.handle}")
        if acc.pseudonymous and acc.orcid:
            v.err(path, "a pseudonymous account must not carry an ORCID iD in the repository; "
                  "it would link the handle to a real name (§3.3.8, §3.7.3)")


def _codes(v: _V, path, ass: dict, analysis_optional: bool = False) -> None:
    if ass.get("writing") not in WRITING:
        v.err(path, f"writing must be one of {', '.join(WRITING)}")
    if ass.get("analysis") is None and analysis_optional:
        return  # a sketch with no analysis (OQ-23)
    if ass.get("analysis") not in ANALYSIS:
        v.err(path, f"analysis must be one of {', '.join(ANALYSIS)}")


def _paper(v: _V, p: Paper, unique) -> None:
    a = v.a
    ppath = p.directory / "paper.yaml"
    cat = a.categories.get(p.category)
    if cat is None:
        v.err(ppath, f"unknown category '{p.category}'")
    elif cat.gated != p.gated:
        v.err(ppath, f"gated must be {cat.gated} for category {p.category} (§9.1)")
    for cl in p.cross_list:
        if cl not in a.categories:
            v.err(ppath, f"unknown cross-list category '{cl}'")
    v.account(ppath, p.submitter, "submitter")
    sub = a.accounts.get(p.submitter)
    if sub and (p.track == "autonomous") != sub.is_agent:
        v.err(ppath, "track must be 'autonomous' exactly when the submitter is an agent account (§3.5.1)")
    for m in p.maintainers:
        v.account(ppath, m, "maintainer", human=True)

    if not p.versions:
        v.err(p.directory, "paper has no versions")
        return
    if p.versions[0].number != VersionNumber(1, 0):
        v.err(p.directory, "the first version must be v1.0")

    # immutability guard: v1.0 must hash to v1_sha256 forever (§6.1.1)
    v1dir = p.directory / "v1.0"
    if v1dir.is_dir():
        got = tree_sha256(v1dir)
        if got != p.v1_sha256:
            v.err(v1dir, f"v1.0 does not match v1_sha256 in paper.yaml (got {got}). v1.0 is immutable; "
                  "make a new version instead of editing it")
    for key, want in p.version_sha256.items():
        d = p.directory / f"v{key}"
        if not d.is_dir():
            v.err(ppath, f"version_sha256 names v{key}, which does not exist")
        elif tree_sha256(d) != want:
            v.err(d, f"v{key} does not match version_sha256 in paper.yaml; versions are immutable")
    for ver in p.versions:
        if not ver.number.is_initial and str(ver.number) not in p.version_sha256:
            v.err(ppath, f"version_sha256 has no hash for v{ver.number}; every version stores its "
                  "content hash (§6.1.2, §11.4)")

    prev = None
    for ver in p.versions:
        mpath = ver.directory / "meta.yaml"
        if prev is None:
            if ver.change != "initial":
                v.err(mpath, "v1.0 has change: initial")
        else:
            if ver.change == "minor" and ver.number != prev.number.next_minor():
                v.err(mpath, f"a minor version after v{prev.number} is v{prev.number.next_minor()}")
            elif ver.change == "major" and ver.number != prev.number.next_major():
                v.err(mpath, f"a major version after v{prev.number} is v{prev.number.next_major()}")
            elif ver.change == "initial":
                v.err(mpath, "only v1.0 has change: initial")
            if ver.date < prev.date:
                v.err(mpath, "a version cannot be dated before its parent")
            g = [x for x in p.graduations if x.version == prev.number and x.state == "graduated"]
            if g and ver.change == "minor":
                v.err(mpath, f"v{prev.number} is Graduated, so the next version must be major (§7.3.2)")
        v.account(mpath, ver.submitted_by, "submitted_by")
        for au in ver.authors:
            v.account(mpath, au, "author")
            acc = a.accounts.get(au)
            if acc and acc.is_agent and p.gated:
                v.err(mpath, "agent accounts are excluded from gated categories (§3.4.5)")
        _codes(v, mpath, {"writing": ver.declaration.writing, "analysis": ver.declaration.analysis})
        for fam in ver.rubric_families:
            if fam == CITATIONS or fam not in a.rubrics.ids():
                v.err(mpath, f"rubric family '{fam}' has no rubric in packages/rubrics")
        for fid in ver.merged_fixes:
            fx = next((f for f in p.fixes if f.id == fid), None)
            if fx is None:
                v.err(mpath, f"merged fix {fid} has no file in fixes/")
            elif fx.merged_into != ver.number:
                v.err(mpath, f"fix {fid} says it was merged into {fx.merged_into}, not v{ver.number}")
        prev = ver

    if p.promoted_from:
        try:
            ident = Identifier.parse(p.promoted_from)
            if ident.type != "sketch" or ident.form != "exact":
                raise IdentifierError("promoted_from must be an exact sketch identifier")
            s = a.sketches.get(ident.number)
            if s is None:
                v.err(ppath, f"{p.promoted_from} does not exist")
            elif p.number not in s.promoted_to:
                v.err(ppath, f"{p.promoted_from} does not list paper:{p.number} in promoted_to (§2.6.2)")
        except IdentifierError as e:
            v.err(ppath, str(e))

    numbers = {ver.number for ver in p.versions}
    for rec in p.verifications:
        path = rec.path or p.directory
        unique("verification", rec.id, path)
        if rec.version not in numbers:
            v.err(path, f"version {rec.version} does not exist; verifications attach to a version (§4.2.1)")
            continue
        ver = p.version(rec.version)
        assert ver is not None
        if rec.date < ver.date:
            v.err(path, f"dated {rec.date}, before v{ver.number} existed ({ver.date})")
        if v.account(path, rec.verifier, "verifier", human=True):
            if rec.verifier in contributors(p, ver):
                v.err(path, "a verifier may not verify a version they contributed to (§4.2.8)")
        if rec.conflict_flags and rec.independent and rec.independent.get("value") is True:
            v.err(path, "a record with a conflict flag cannot also be recorded as independent (§3.6.5)")
        rub = a.rubrics.get(rec.rubric_id, rec.rubric_version)
        if rub is None:
            v.err(path, f"rubric {rec.rubric_id} {rec.rubric_version} does not exist in packages/rubrics")
            continue
        if rec.tier not in rub.tiers:
            v.err(path, f"rubric {rub.key} does not cover {rec.tier}")
        if rec.tier == "T1" and rec.rubric_id != CITATIONS:
            v.err(path, "T1 uses the citations rubric")
        if rec.tier != "T1" and rec.rubric_id not in ver.rubric_families:
            v.err(path, f"v{ver.number} does not declare the rubric family '{rec.rubric_id}'")
        listed = {}
        for it in rec.items:
            item = rub.items.get(it.item_id)
            if item is None:
                v.err(path, f"item {it.item_id} is not in {rub.key}")
                continue
            if item.tier != rec.tier:
                v.err(path, f"item {it.item_id} belongs to {item.tier}, not {rec.tier}")
            if it.verdict == "na":
                if not item.na_allowed:
                    v.err(path, f"item {it.item_id} is never not applicable")
                if not it.note:
                    v.err(path, f"item {it.item_id}: a not-applicable verdict needs a reason (§4.2.4)")
            listed[it.item_id] = it
        required = [i.id for i in rub.required_at(rec.tier)]
        if rec.kind == "paper":
            missing = [i for i in required if i not in listed]
            if missing:
                v.err(path, f"no verdict for required item(s) {', '.join(missing)} (§4.2.4)")
        fails = [i for i in required if i in listed and listed[i].verdict == "fail"]
        want = "failed" if fails else "passed"
        if rec.result != want:
            v.err(path, f"result is '{rec.result}' but the items say '{want}' (§4.2.5)")
        if rec.tier == "T4":
            ok, why = independence(a, p, ver, rec)
            if not ok:
                v.err(path, f"a T4 verification needs an independent verifier; {rec.verifier} {why} (§2.4.7)")
            if not rec.t4_attestation:
                v.err(path, "a T4 verification needs the verifier's attestation (§3.6.9)")

    for fx in p.fixes:
        path = p.directory / "fixes"
        unique(f"fix of paper:{p.number}", str(fx.id), path)
        v.account(path, fx.author, f"fix {fx.id} author")
        if fx.base_version not in numbers:
            v.err(path, f"fix {fx.id}: base version {fx.base_version} does not exist")
        if fx.status == "merged":
            if fx.merged_into not in numbers:
                v.err(path, f"fix {fx.id}: merged_into {fx.merged_into} does not exist")
            elif fx.merged_into <= fx.base_version:
                v.err(path, f"fix {fx.id}: merged_into must be later than the base version")
        if fx.status == "declined" and not fx.decline_reason:
            v.err(path, f"fix {fx.id}: a decline gives a reason (§6.7.2)")
        for vid, _item in fx.addresses:
            if vid not in {r.id for r in p.verifications}:
                v.err(path, f"fix {fx.id} addresses unknown verification '{vid}'")

    pred_ids = {x.id for x in p.predictions}
    for pr in p.predictions:
        path = p.directory / "signals" / f"{pr.id}.yaml"
        unique("signal", pr.id, path)
        if pr.version not in numbers:
            v.err(path, f"version {pr.version} does not exist")
        for axis, table in (("writing", WRITING), ("analysis", ANALYSIS)):
            probs = pr.probabilities.get(axis) or {}
            bad = [k for k in probs if k not in table]
            if bad:
                v.err(path, f"{axis}: unknown code(s) {', '.join(bad)}")
            if probs and abs(sum(probs.values()) - 1.0) > 0.01:
                v.err(path, f"{axis}: probabilities sum to {sum(probs.values()):.3f}, not 1")
    for t in p.tallies:
        path = p.directory / "signals" / f"{t.id}.yaml"
        unique("signal", t.id, path)
        if t.version not in numbers:
            v.err(path, f"version {t.version} does not exist")
        for axis, table in (("writing", WRITING), ("analysis", ANALYSIS)):
            bad = [k for k in t.counts.get(axis, {}) if k not in table]
            if bad:
                v.err(path, f"{axis}: unknown code(s) {', '.join(bad)}")
    for c in p.contests:
        path = p.directory / "signals" / f"{c.id}.yaml"
        unique("signal", c.id, path)
        if c.prediction not in pred_ids:
            v.err(path, f"contest names unknown prediction '{c.prediction}'")
        ver = p.version(c.version)
        if ver is None:
            v.err(path, f"version {c.version} does not exist")
        elif c.by not in contributors(p, ver):
            v.err(path, "only a contributor to the version may contest its prediction (§4.5.7)")
    for d in p.declarations:
        path = p.directory / "signals" / f"{d.source}.yaml"
        unique("signal", d.source, path)
        if d.version not in numbers:
            v.err(path, f"version {d.version} does not exist")
        _codes(v, path, {"writing": d.writing, "analysis": d.analysis})

    states = compute_paper(p, a.rubrics)
    for g in p.graduations:
        path = p.directory / "graduations" / f"{g.id}.yaml"
        unique("graduation", g.id, path)
        ver = p.version(g.version)
        if ver is None:
            v.err(path, f"version {g.version} does not exist")
            continue
        if g.state == "graduated":
            missing = [m for m in graduation_check(a, p, ver, states[ver.number], g) if not m.startswith("fix ")]
            if missing:
                v.warn(path, "graduation conditions no longer hold (" + "; ".join(missing) + "), so it is withdrawn (§7.4.1)")


def validate_path(root: Path, rubrics_dir: Path | None = None) -> tuple[Archive, list[Issue]]:
    arch = load_archive(root, rubrics_dir)
    return arch, validate(arch)
