# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stage derivation (SPEC §2.4, §2.5, §6.3, §7.1) and visibility (§9).

Stages belong to versions. For each version the active verifications that count on it
are its own plus, after a minor bump, every active record carried from the parent. A
major bump carries nothing, so the new version starts at T0. Carried records whose items
were reopened by the bump (items the version lists in `reopens`, or items a merged fix
says it addresses) are pending until a verification on the new version passes them.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .ids import VersionNumber
from .models import Archive, Paper, Sketch, Verification, Version
from .rubrics import RubricSet

TIERS = ["T1", "T2", "T3", "T4"]
TIER_NAMES = {
    "T0": "unverified",
    "T1": "citations checked",
    "T2": "claims checked",
    "T3": "partially reproduced",
    "T4": "independently reproduced",
}
N_NAMES = {
    "N0": "posted",
    "N1": "no prior work found",
    "N2": "prior work linked",
    "N3": "judged tractable",
}
CITATIONS = "citations"


@dataclass
class Effective:
    """A verification as it counts on one version."""

    v: Verification
    carried: bool
    reopened: frozenset[str] = frozenset()
    unresolved: frozenset[str] = frozenset()
    outcome: str = ""  # pass | fail | pending | inactive


@dataclass
class VersionState:
    number: VersionNumber
    tier: str
    pending: bool
    statuses: dict[str, str]
    effective: list[Effective]
    since: dt.date | None = None

    @property
    def index(self) -> int:
        return int(self.tier[1])

    @property
    def qualifier(self) -> str:
        """What happened at the next tier up, if anything worth saying: 'T2 failed'."""
        for t in TIERS[self.index:]:
            s = self.statuses.get(t, "none")
            if s in ("failed", "contested"):
                return f"{t} {s}"
            if s == "none":
                return ""
        return ""

    def verifiers(self) -> list[str]:
        """Distinct verifiers whose counting records support this version's tier."""
        seen: list[str] = []
        for e in self.effective:
            if e.outcome in ("pass", "pending") and int(e.v.tier[1]) <= self.index and e.v.verifier not in seen:
                seen.append(e.v.verifier)
        return seen

    def counting_ids(self) -> set[str]:
        return {e.v.id for e in self.effective if e.outcome != "inactive"}


def _required(rubrics: RubricSet, v: Verification) -> set[str] | None:
    r = rubrics.get(v.rubric_id, v.rubric_version)
    return None if r is None else {i.id for i in r.required_at(v.tier)}


def _outcome(e: Effective, rubrics: RubricSet) -> str:
    v = e.v
    if v.status != "active":
        return "inactive"
    req = _required(rubrics, v)
    failing = {i.item_id for i in v.items if i.verdict == "fail" and (req is None or i.item_id in req)}
    if not failing and v.result == "failed" and req is None:
        failing = {"(record)"}
    failing -= e.reopened
    if failing:
        return "fail"
    if e.unresolved:
        return "pending"
    return "pass"


def _status(records: list[Effective]) -> str:
    outs = {e.outcome for e in records}
    good = bool(outs & {"pass", "pending"})
    if good and "fail" in outs:
        return "contested"
    if "fail" in outs:
        return "failed"
    if "pending" in outs:
        return "pending"
    if "pass" in outs:
        return "passed"
    return "none"


def _combine(statuses: list[str]) -> str:
    if not statuses:
        return "none"
    if "contested" in statuses:
        return "contested"
    if all(s in ("passed", "pending") for s in statuses):
        return "pending" if "pending" in statuses else "passed"
    if "failed" in statuses:
        return "failed"
    return "none"


def _counts_at(e: Effective, tier: str) -> bool:
    if e.v.tier != tier:
        return False
    if tier == "T4" and (e.v.loop_label or not e.v.recorded_independent):
        return False  # §2.4.7, §5.6.4: T4 needs an independent, loop-free record
    return True


def compute_paper(paper: Paper, rubrics: RubricSet) -> dict[VersionNumber, VersionState]:
    states: dict[VersionNumber, VersionState] = {}
    prev: Version | None = None
    for ver in paper.versions:
        own = [v for v in paper.verifications if v.version == ver.number]
        carried: list[Effective] = []
        if prev is not None and ver.change == "minor":
            fix_items: dict[str, set[str]] = {}
            for fx in paper.fixes:
                if fx.status == "merged" and fx.merged_into == ver.number:
                    for vid, item in fx.addresses:
                        fix_items.setdefault(vid, set()).add(item)
            for e in states[prev.number].effective:
                if e.v.status != "active":
                    continue
                items = {i.item_id for i in e.v.items}
                reopened = (set(ver.reopens) | fix_items.get(e.v.id, set())) & items
                carried.append(Effective(e.v, True, e.reopened | reopened, e.unresolved | reopened))
        for e in carried:
            unresolved = set(e.unresolved)
            for r in own:
                if r.status == "active" and r.tier == e.v.tier and r.rubric_id == e.v.rubric_id:
                    for it in r.items:
                        if it.verdict in ("pass", "na"):
                            unresolved.discard(it.item_id)
            e.unresolved = frozenset(unresolved)
        effective = carried + [Effective(v, False) for v in own]
        for e in effective:
            e.outcome = _outcome(e, rubrics)

        statuses: dict[str, str] = {}
        for t in TIERS:
            families = [CITATIONS] if t == "T1" else list(ver.rubric_families)
            per = [_status([e for e in effective if _counts_at(e, t) and e.v.rubric_id == f]) for f in families]
            statuses[t] = _combine(per) if families else "none"
        n = 0
        for i, t in enumerate(TIERS, start=1):
            if statuses[t] in ("passed", "pending"):
                n = i
            else:
                break
        tier = f"T{n}"
        pending = any(statuses[t] == "pending" for t in TIERS[:n])
        since = None
        if n:
            dates = [e.v.date for e in effective if e.v.tier == tier and e.outcome in ("pass", "pending")]
            since = max(dates) if dates else None
        states[ver.number] = VersionState(ver.number, tier, pending, statuses, effective, since)
        prev = ver
    return states


def highest_held(states: dict[VersionNumber, VersionState]) -> VersionState | None:
    best = None
    for s in states.values():
        if best is None or s.index > best.index or (s.index == best.index and s.number > best.number):
            best = s
    return best


@dataclass
class RecordRelation:
    """How a verification relates to the version being viewed, for the table."""

    kind: str  # counts | carried | cleared | earlier-minor | later | inactive
    note: str = ""
    muted: bool = False


def relation(paper: Paper, states: dict[VersionNumber, VersionState], rec: Verification, viewing: VersionNumber) -> RecordRelation:
    st = states[viewing]
    eff = next((e for e in st.effective if e.v.id == rec.id), None)
    if rec.status != "active":
        last = rec.status_history[-1] if rec.status_history else None
        why = f" {last.reason}" if last and last.reason else ""
        return RecordRelation("inactive", f"{rec.status.capitalize()}.{why}", muted=False)
    if eff is not None:
        if not eff.carried:
            if eff.outcome == "pending":
                return RecordRelation("counts", "Pending re-check of reopened items.")
            return RecordRelation("counts")
        parts = [f"Made on v{rec.version}, carried to v{viewing} by a minor version."]
        if eff.reopened:
            done = eff.reopened - eff.unresolved
            if done:
                parts.append(f"Reopened items passed on re-check: {', '.join(sorted(done))}.")
            if eff.unresolved:
                parts.append(f"Awaiting re-check: {', '.join(sorted(eff.unresolved))}.")
        return RecordRelation("carried", " ".join(parts))
    if rec.version > viewing:
        return RecordRelation("later", f"Recorded on a later version, v{rec.version}.", muted=True)
    # recorded on an earlier version and not carried: a major bump cleared it
    majors = [v for v in paper.versions if rec.version < v.number <= viewing and v.change == "major"]
    if majors:
        return RecordRelation("cleared", f"Cleared by {majors[0].label}, which changed a claim.", muted=True)
    return RecordRelation("earlier-minor", f"Recorded on v{rec.version}.", muted=True)


# ---------------------------------------------------------------- sketches


def sketch_stage(s: Sketch) -> tuple[str, str]:
    """Stage and, for N3, the path that led there (§2.5.4, §2.5.5)."""
    active = [c for c in s.checks if c.status == "active"]
    base = [c for c in active if c.outcome in ("N1", "N2")]
    latest = base[-1].outcome if base else None
    if latest and any(c.outcome == "N3" and c.date >= base[0].date for c in active):
        return "N3", "no prior work found" if latest == "N1" else "prior work linked"
    if latest:
        return latest, ""
    return "N0", ""


def active_claims(s: Sketch, today: dt.date) -> list:
    return [c for c in s.claims if c.expires is None or c.expires >= today]


# ---------------------------------------------------------------- contributors, independence


def contributors(paper: Paper, upto: Version) -> list[str]:
    """Contributor handles of a version: submitters, listed authors and merged fix authors
    of this and every earlier version (§6.5.2)."""
    out: list[str] = []

    def add(h: str) -> None:
        if h not in out:
            out.append(h)

    for v in paper.versions:
        if v.number > upto.number:
            break
        add(v.submitted_by)
        for a in v.authors:
            add(a)
        for fx in paper.fixes:
            if fx.status == "merged" and fx.merged_into == v.number:
                add(fx.author)
    return out


def _responsible(archive: Archive, handle: str) -> str:
    a = archive.accounts.get(handle)
    return a.operator if a and a.is_agent and a.operator else handle


def independence(archive: Archive, paper: Paper, version: Version, rec: Verification) -> tuple[bool, str]:
    """§3.6.5. The part that uses public data (contributors and operators) is computed
    here. Affiliations and co-authorships are held data, checked by moderators outside
    the repository (§3.7.5), so that part is read from the result recorded on the
    verification (`independent`, `conflict_flags`)."""
    contribs = contributors(paper, version)
    if rec.verifier in contribs:
        return False, "is a contributor"
    humans = {_responsible(archive, h) for h in contribs}
    if rec.verifier in humans:
        return False, "operates a contributing agent"
    if rec.conflict_flags:
        return False, "carries a conflict flag (" + ", ".join(rec.flag_types) + ")"
    if not rec.independent:
        return False, "has no recorded conflict check"
    if rec.independent.get("value") is not True:
        return False, "was found not independent by the recorded conflict check"
    return True, ""


def graduation_check(
    archive: Archive, paper: Paper, version: Version, state: VersionState, grad=None
) -> list[str]:
    """Return the §7.1.1 conditions that do not hold. An empty list means eligible.

    Condition 3 also asks that the two counted verifiers share no affiliation with each
    other. That uses held data, so its result is read from the graduation record
    (`pair_independent`) when there is one."""
    failed: list[str] = []
    if state.index < 3:
        failed.append("tier is below T3")
    if state.pending:
        failed.append("an item is pending re-check")
    if any(s == "contested" for s in state.statuses.values()):
        failed.append("a tier is contested")
    counting = [
        e for e in state.effective
        if e.outcome == "pass" and int(e.v.tier[1]) >= 2 and not e.v.loop_label
    ]
    indep = []
    for e in counting:
        ok, _ = independence(archive, paper, version, e.v)
        if ok and e.v.verifier not in [x.v.verifier for x in indep]:
            indep.append(e)
    pair_ok = any(
        int(a.v.tier[1]) >= 3 or int(b.v.tier[1]) >= 3
        for i, a in enumerate(indep)
        for b in indep[i + 1:]
    )
    if grad is not None and grad.pair_independent and grad.pair_independent.get("value") is False:
        pair_ok = False
    if not pair_ok:
        failed.append("needs two independent verifiers at T2 or above, one at T3 or T4, with no shared affiliation")
    open_fixes = [f for f in paper.fixes if f.status == "open" and f.base_version <= version.number]
    if open_fixes:
        failed.append("fix " + ", ".join(str(f.id) for f in open_fixes) + " is open")
    for h in contributors(paper, version):
        acc = archive.accounts.get(_responsible(archive, h))
        if acc and acc.pseudonymous:
            failed.append("a contributor shows a handle rather than a real name")
            break
    return failed


def graduated(paper: Paper, number: VersionNumber):
    gs = [g for g in paper.graduations if g.version == number]
    return gs[-1] if gs else None


# ---------------------------------------------------------------- standing (§4.6)

STANDING_AGE_DAYS = 90
STANDING_OVERTURN_WEIGHT = 3


def standing(archive: Archive, handle: str, field_code: str, today: dt.date) -> int:
    """Standing in a field, OQ-8 default: S minus 3 times O, where S counts the account's
    verifications and novelty checks in the field that have been active for at least 90
    days and never overturned (loop-labeled records left out), and O counts overturned
    ones. Recomputable from the public record."""
    s = o = 0

    def field_of(category: str) -> str | None:
        cat = archive.categories.get(category)
        return cat.field_code if cat else None

    for p in archive.papers.values():
        if field_of(p.category) != field_code:
            continue
        for v in p.verifications:
            if v.verifier != handle:
                continue
            if v.status == "overturned" or any(h.status == "overturned" for h in v.status_history):
                o += 1
            elif v.status == "active" and not v.loop_label and (today - v.date).days >= STANDING_AGE_DAYS:
                s += 1
    for sc in archive.sketches.values():
        if field_of(sc.category) != field_code:
            continue
        for ch in sc.checks:
            if ch.checker != handle:
                continue
            if ch.status == "overturned":
                o += 1
            elif ch.status == "active" and (today - ch.date).days >= STANDING_AGE_DAYS:
                s += 1
    return s - STANDING_OVERTURN_WEIGHT * o


# ---------------------------------------------------------------- visibility (§9)


def version_visible(paper: Paper, state: VersionState) -> bool:
    """Gated content is not public below T1 (§9.1.2). Removed papers show a tombstone."""
    if paper.status == "removed":
        return False
    return not paper.gated or state.index >= 1


def version_indexable(paper: Paper, state: VersionState) -> bool:
    """T0 versions and gated content below T1 carry noindex (§9.2.1)."""
    return version_visible(paper, state) and state.index >= 1


def sketch_visible(s: Sketch) -> bool:
    return s.status != "removed" and not s.gated  # gated sketches are never public (§9.1.4)


def sketch_indexable(s: Sketch) -> bool:
    return sketch_visible(s)  # OQ-18 default: non-gated sketches may be indexed


def is_agent(archive: Archive, handle: str) -> bool:
    a = archive.accounts.get(handle)
    return bool(a and a.is_agent)
