# SPDX-License-Identifier: AGPL-3.0-or-later
"""View models: one archive as the templates see it.

Everything a page shows is derived here from garleak_archive, so the templates stay free
of rules. Stages, pct_original, visibility and indexing all come from the archive
library; this module only arranges them.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property

from garleak_archive import assistance as asst
from garleak_archive.ids import VersionNumber
from garleak_archive.models import Archive, Paper, Sketch, Verification
from garleak_archive.pct import PctResult, po1, rendition
from garleak_archive.stages import (
    N_NAMES,
    TIER_NAMES,
    active_claims,
    compute_paper,
    contributors,
    graduated,
    graduation_check,
    highest_held,
    relation,
    sketch_indexable,
    sketch_stage,
    sketch_visible,
    standing,
    version_indexable,
    version_visible,
)

RUBRIC_URL = "https://github.com/{repo}/blob/main/packages/rubrics/{id}/v{version}.yaml"


# ---------------------------------------------------------------- formatting


def longdate(d: dt.date | None) -> str:
    return "" if d is None else f"{d.day} {d.strftime('%B')} {d.year}"


def dayname(d: dt.date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')} {d.year}"


def shortdate(d: dt.date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def monthname(ym: str) -> str:
    y, m = (int(x) for x in ym.split("-"))
    return f"{dt.date(y, m, 1).strftime('%B')} {y}"


def join_names(names: list[str]) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"


def month_key(d: dt.date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_end(ym: str) -> dt.date:
    y, m = (int(x) for x in ym.split("-"))
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


# ---------------------------------------------------------------- people


@dataclass
class Person:
    handle: str
    name: str
    is_agent: bool = False
    operator: Person | None = None
    pseudonymous: bool = False


# ---------------------------------------------------------------- assistance


@dataclass
class AxisView:
    axis: str
    name: str
    codes: list[str]
    declared: str | None
    declared_by: str = ""
    prediction: asst.Interval | None = None
    classifier: str = ""
    reads: str = ""
    contests: list = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    median: asst.Median | None = None

    @property
    def votes(self) -> int:
        return sum(self.counts.values())

    @property
    def hist(self) -> list[tuple[str, int, int, bool]]:
        top = max(self.counts.values(), default=0) or 1
        med = set()
        if self.median:
            lo, hi = self.codes.index(self.median.low), self.codes.index(self.median.high)
            med = set(self.codes[lo : hi + 1])
        return [(c, self.counts.get(c, 0), round(100 * self.counts.get(c, 0) / top), c in med) for c in self.codes]

    @property
    def vote_label(self) -> str:
        return ", ".join(f"{c} {self.counts.get(c, 0) or 'none'}" for c in self.codes)


LICENSES = [
    ("CC-BY-4.0", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/",
     "Anyone may share it and build on it, with credit."),
    ("CC-BY-SA-4.0", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/",
     "As CC BY, and work built on it carries the same license."),
    ("CC0-1.0", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/",
     "You place it in the public domain and keep no conditions."),
    ("CC-BY-NC-4.0", "CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/",
     "Credit required, and no commercial use."),
]
_LICENSE = {code: (name, url) for code, name, url, _ in LICENSES}


def license_name(code: str) -> str:
    return _LICENSE.get(code, (code, ""))[0]


def license_url(code: str) -> str:
    return _LICENSE.get(code, ("", ""))[1]


def gloss(code: str | None) -> str:
    return "No analysis" if code is None else asst.gloss(code)


# ---------------------------------------------------------------- verification rows


@dataclass
class VRow:
    rec: Verification
    version_label: str
    tier_index: int
    checker: str
    standing: int | None
    rubric: str
    rubric_url: str
    summary: str
    failed_items: list[tuple[str, str, str]]
    na_items: list[tuple[str, str]]
    notes: list[str]
    result: str
    failed: bool
    muted: bool


# ---------------------------------------------------------------- papers


class VersionView:
    def __init__(self, pv: PaperView, index: int):
        self.pv = pv
        self.site = pv.site
        self.v = pv.p.versions[index]
        self.index = index
        self.number: VersionNumber = self.v.number
        self.state = pv.states[self.number]

    # identity
    @property
    def key(self) -> str:
        return f"{self.pv.number}v{self.number}"

    @property
    def short(self) -> str:
        n = self.number
        return f"{self.pv.number}v{n.major}" if n.minor == 0 else self.key

    @property
    def ident(self) -> str:
        return f"paper:{self.key}"

    @property
    def label(self) -> str:
        return f"v{self.number}"

    @property
    def url(self) -> str:
        return self.site.url(f"/abs/{self.key}/")

    @property
    def text_url(self) -> str:
        return self.site.url(f"/text/{self.key}/")

    @property
    def src_dir(self) -> str:
        return self.site.url(f"/src/{self.key}/")

    @property
    def pdf_url(self) -> str | None:
        return self.site.url(f"/pdf/{self.key}.pdf") if self.v.pdf else None

    def diff_url(self, other: VersionView) -> str:
        a, b = sorted([self, other], key=lambda x: x.number)
        return self.site.url(f"/diff/{self.pv.number}/{a.number}..{b.number}/")

    @property
    def is_current(self) -> bool:
        return self is self.pv.current

    @property
    def is_major(self) -> bool:
        return self.v.change in ("initial", "major")

    # state
    @property
    def tier(self) -> str:
        return self.state.tier

    @property
    def tier_index(self) -> int:
        return self.state.index

    @property
    def tier_name(self) -> str:
        return TIER_NAMES[self.tier]

    @property
    def visible(self) -> bool:
        return version_visible(self.pv.p, self.state)

    @property
    def indexable(self) -> bool:
        return version_indexable(self.pv.p, self.state) and not self.site.example

    @cached_property
    def pct(self) -> PctResult:
        return po1(self.pv.v1_text, rendition(self.v.title, self.v.abstract, self.v.body), is_v1=self.index == 0)

    @property
    def stage_rubrics(self) -> list[str]:
        """Rubric id and version behind each tier this version holds (§9.2.3)."""
        return sorted({
            f"{e.v.rubric_id} {e.v.rubric_version}" for e in self.state.effective
            if e.outcome in ("pass", "pending") and int(e.v.tier[1]) <= self.tier_index
        })

    @property
    def verifiers(self) -> list[Person]:
        return [self.site.person(h) for h in self.state.verifiers()]

    @property
    def any_records(self) -> bool:
        return bool(self.state.effective)

    @property
    def carried(self) -> bool:
        return any(e.carried for e in self.state.effective)

    @property
    def graduation(self):
        g = graduated(self.pv.p, self.number)
        return g if g and g.state == "graduated" else None

    @property
    def graduation_record(self):
        return graduated(self.pv.p, self.number)

    @cached_property
    def graduation_blockers(self) -> list[str]:
        return graduation_check(self.site.a, self.pv.p, self.v, self.state, self.graduation_record)

    @property
    def kind_text(self) -> str:
        if self.index == 0:
            return "first submission"
        return f"{self.v.change}, {self.v.note[:1].lower() + self.v.note[1:]}" if self.v.note else self.v.change

    @property
    def change_fact(self) -> str:
        """What a new version did to the verification record, for listing rows."""
        if self.index == 0:
            return ""
        parent = self.pv.versions[self.index - 1]
        if self.v.change == "minor":
            return "minor version, verifications carried" if self.carried else "minor version"
        if parent.tier_index:
            return f"major version, {parent.tier} on {parent.label} cleared"
        return "major version"

    # people
    @property
    def authors(self) -> list[Person]:
        return [self.site.person(h) for h in self.v.authors]

    @property
    def submitter(self) -> Person:
        return self.site.person(self.v.submitted_by)

    @property
    def contributors(self) -> list[Person]:
        return [self.site.person(h) for h in contributors(self.pv.p, self.v)]

    @property
    def new_contributors(self) -> list[tuple[Person, str]]:
        """Contributors who joined after v1.0, with the version they joined at (§6.5.3)."""
        first = set(contributors(self.pv.p, self.pv.p.versions[0]))
        out = []
        for h in contributors(self.pv.p, self.v):
            if h in first:
                continue
            joined = next(vv for vv in self.pv.versions if h in contributors(self.pv.p, vv.v))
            out.append((self.site.person(h), joined.label))
        return out

    @property
    def models(self):
        return self.v.declaration.models

    @property
    def model_names(self) -> list[str]:
        return [m.name for m in self.v.declaration.models]

    @property
    def merged_fixes(self):
        return [f for f in self.pv.p.fixes if f.status == "merged" and f.merged_into == self.number]

    # assistance
    @property
    def declaration(self):
        return self.pv.p.declaration_for(self.number)

    @property
    def declaration_history(self):
        return self.pv.p.declaration_history(self.number)

    @property
    def declared_codes(self) -> str:
        d = self.declaration
        return f"{d.writing} {d.analysis}" if d.analysis else d.writing

    @cached_property
    def axes(self) -> list[AxisView]:
        p, n = self.pv.p, self.number
        d = self.declaration
        preds = sorted((x for x in p.predictions if x.version == n), key=lambda x: x.date)
        pred = preds[-1] if preds else None
        tallies = sorted((x for x in p.tallies if x.version == n), key=lambda x: x.date)
        tally = tallies[-1] if tallies else None
        out = []
        for axis in ("writing", "analysis"):
            av = AxisView(axis, asst.AXIS_NAMES[axis], asst.codes(axis), getattr(d, axis),
                          declared_by=self.site.person(d.declared_by).name)
            if pred and pred.probabilities.get(axis):
                av.prediction = asst.predicted_interval(axis, pred.probabilities[axis])
                av.classifier = f"{pred.classifier_id} {pred.classifier_version}"
                av.reads = pred.reads
                av.contests = [
                    (c, self.site.person(c.by)) for c in p.contests
                    if c.version == n and c.prediction == pred.id and c.axis == axis
                ]
            if tally:
                av.counts = {c: int(tally.counts.get(axis, {}).get(c, 0)) for c in av.codes}
                av.median = asst.median(axis, av.counts)
            out.append(av)
        return out

    # the verification table
    @cached_property
    def vrows(self) -> list[VRow]:
        p, site = self.pv.p, self.site
        rows = []
        for rec in sorted(p.verifications, key=lambda r: (r.date, r.id), reverse=True):
            rel = relation(p, self.pv.states, rec, self.number)
            eff = next((e for e in self.state.effective if e.v.id == rec.id), None)
            rub = site.a.rubrics.get(rec.rubric_id, rec.rubric_version)

            def title(item_id: str) -> str:
                it = rub.items.get(item_id) if rub else None
                return it.title if it else ""

            base = "Passed" if rec.result == "passed" else "Failed"
            if rec.status != "active":
                result = f"{base}, then {rec.status}"
            elif eff is not None and eff.outcome == "pending":
                result = "Passed, re-check pending"
            else:
                result = base
            who = [f"{a['tool']} {a['version']}" for a in rec.automated]
            checker = (", ".join(who) + ", then " if who else "") + site.person(rec.verifier).name
            notes = [rel.note] if rel.note else []
            if rec.conflict_flags:
                notes.append("Conflict flag: " + ", ".join(rec.flag_types) + ".")
            if rec.loop_label:
                notes.append(f"Reciprocal loop of length {rec.loop_label['length']}.")
            if rec.t4_attestation:
                notes.append(f"Independence attested on {longdate(dt.date.fromisoformat(str(rec.t4_attestation['date'])[:10]))}.")
            for h in rec.status_history:
                notes.append(f"{h.status.capitalize()} by {site.person(h.by).name} on {longdate(h.date)}. {h.reason}".strip())
            rows.append(VRow(
                rec=rec,
                version_label=f"v{rec.version}",
                tier_index=int(rec.tier[1]),
                checker=checker,
                standing=site.standing(rec.verifier, self.pv.field_code),
                rubric=f"{rec.rubric_id} {rec.rubric_version}",
                rubric_url=RUBRIC_URL.format(repo=site.config["repo"], id=rec.rubric_id, version=rec.rubric_version),
                summary=rec.summary,
                failed_items=[(i.item_id, title(i.item_id), i.note) for i in rec.items if i.verdict == "fail"],
                na_items=[(i.item_id, i.note) for i in rec.items if i.verdict == "na"],
                notes=notes,
                result=result,
                failed=rec.result == "failed",
                muted=rel.muted,
            ))
        return rows

    # citation
    @property
    def citation(self) -> str:
        names = ", ".join(a.name for a in self.authors)
        url = self.site.abs_url(self.key)
        g = self.graduation
        if g:
            return f"{names}. {self.v.title}. Garleak {self.ident}, Graduated {g.date.isoformat()} ({self.tier})."
        stage = f"Verified {self.tier}" if self.tier_index else "T0, unverified"
        return (f"{names}. {self.v.title}. Garleak {self.ident} ({stage}, not peer reviewed, "
                f"stage as of {self.site.today.isoformat()}). {url}")

    @property
    def stamp_lines(self) -> list[str]:
        lines = [
            f"Not peer reviewed. Garleak {self.ident}, stage {self.tier} as of {self.site.today.isoformat()}. "
            "Admission is not endorsement; screening checks scope and form only.",
            f"Current record: {self.site.abs_url(self.key)}",
        ]
        if self.site.example:
            lines[1] += "   Example record. Every paper, person and number in it is invented."
        return lines


class PaperView:
    def __init__(self, site: Site, p: Paper):
        self.site = site
        self.p = p
        self.number = p.number
        self.states = compute_paper(p, site.a.rubrics)
        v1 = p.versions[0]
        self.v1_text = rendition(v1.title, v1.abstract, v1.body)
        self.versions = [VersionView(self, i) for i in range(len(p.versions))]
        self.current = self.versions[-1]
        self.category = site.a.categories.get(p.category)

    @property
    def field_code(self) -> str:
        return self.category.field_code if self.category else ""

    @property
    def field_name(self) -> str:
        return self.category.field_name if self.category else ""

    @property
    def removed(self) -> bool:
        return self.p.status == "removed"

    @property
    def withdrawn(self) -> bool:
        return self.p.status == "withdrawn"

    @property
    def listed(self) -> bool:
        return not self.removed and self.current.visible

    @property
    def concept_url(self) -> str:
        return self.site.url(f"/abs/{self.number}/")

    def view(self, number: VersionNumber) -> VersionView:
        return next(v for v in self.versions if v.number == number)

    @property
    def series(self) -> dict[int, VersionView]:
        out: dict[int, VersionView] = {}
        for v in self.versions:
            out[v.number.major] = v
        return out

    def as_of(self, day: dt.date) -> VersionView | None:
        found = [v for v in self.versions if v.v.date <= day]
        return found[-1] if found else None

    @property
    def highest(self) -> VersionView | None:
        s = highest_held(self.states)
        return self.view(s.number) if s else None

    @property
    def open_fixes(self):
        return [f for f in self.p.fixes if f.status == "open"]

    @property
    def fixes(self):
        return self.p.fixes

    @property
    def maintainers(self) -> list[Person]:
        return [self.site.person(h) for h in self.p.maintainers]

    @property
    def promoted_from(self):
        """(identifier, sketch view or None) for a promoted paper."""
        if not self.p.promoted_from:
            return None
        n = int(self.p.promoted_from.split(":")[1].split("v")[0])
        return self.p.promoted_from, self.site.sketch_by_n.get(n)

    @property
    def pairs(self) -> list[tuple[VersionView, list[VersionView]]]:
        vis = [v for v in self.versions if v.visible]
        return [(a, vis[i + 1:]) for i, a in enumerate(vis[:-1])]


# ---------------------------------------------------------------- sketches


class SketchView:
    def __init__(self, site: Site, s: Sketch):
        self.site = site
        self.s = s
        self.number = s.number
        self.stage, self.path = sketch_stage(s)
        self.category = site.a.categories.get(s.category)

    @property
    def stage_index(self) -> int:
        return int(self.stage[1])

    @property
    def stage_name(self) -> str:
        if self.stage == "N3" and self.path:
            return f"judged tractable, {self.path}"
        return N_NAMES[self.stage]

    @property
    def key(self) -> str:
        return str(self.number)

    @property
    def ident(self) -> str:
        return f"sketch:{self.number}v1.0"

    @property
    def url(self) -> str:
        return self.site.url(f"/sketch/{self.number}/")

    @property
    def visible(self) -> bool:
        return sketch_visible(self.s)

    @property
    def indexable(self) -> bool:
        return sketch_indexable(self.s) and not self.site.example

    @property
    def listed(self) -> bool:
        return self.visible

    @property
    def author(self) -> Person:
        return self.site.person(self.s.author)

    @property
    def claims(self):
        return [(c, self.site.person(c.by)) for c in active_claims(self.s, self.site.today)]

    @property
    def claim_text(self) -> str:
        c = self.claims
        if not c:
            return "unclaimed"
        if len(c) == 1:
            return f"claimed by {c[0][1].name}"
        return f"{len(c)} active claims"

    @property
    def promoted_to(self):
        return [self.site.paper_by_n[n] for n in self.s.promoted_to if n in self.site.paper_by_n]

    @property
    def declared_codes(self) -> str:
        a = self.s.assistance or {}
        return f"{a.get('writing')} {a['analysis']}" if a.get("analysis") else str(a.get("writing"))

    @property
    def checks(self):
        return [(c, self.site.person(c.checker)) for c in self.s.checks]

    @property
    def check_fact(self) -> str:
        active = [c for c in self.s.checks if c.status == "active"]
        if not active:
            return ""
        last = next((c for c in reversed(active) if c.outcome in ("N1", "N2")), None)
        if last and last.outcome == "N1" and self.stage == "N1":
            return f"searched {join_names(last.sources)}, {plural(len(last.queries), 'query', 'queries')} listed"
        if last and last.outcome == "N2" and self.stage == "N2":
            return f"{plural(len(last.prior_work), 'related paper')} linked by the checker"
        n3 = next((c for c in reversed(active) if c.outcome == "N3"), None)
        if n3 and n3.tractability:
            return n3.tractability
        return ""

    @property
    def citation(self) -> str:
        return (f"{self.author.name}. “{self.s.statement.rstrip(' .')}”. Garleak {self.ident}, idea record, "
                f"not a result, posted {self.s.date.isoformat()}. {self.site.base_url}{self.url}")


# ---------------------------------------------------------------- the archive


@dataclass
class Listing:
    new: list = field(default_factory=list)
    cross: list = field(default_factory=list)
    versions: list = field(default_factory=list)

    @property
    def rows(self) -> list:
        return self.new + self.cross + self.versions

    @property
    def empty(self) -> bool:
        return not self.rows

    def strip(self) -> list[tuple[int, int]]:
        c = Counter(r.tier_index if hasattr(r, "tier_index") else r.stage_index for r in self.rows)
        return [(i, c.get(i, 0)) for i in sorted(c)]


class Site:
    """One archive, built at a URL prefix ("" for the real archive, "/example")."""

    def __init__(self, archive: Archive, prefix: str, example: bool, today: dt.date, config: dict):
        self.a = archive
        self.prefix = prefix
        self.example = example
        self.today = today
        self.config = config
        self.base_url = config["site_url"].rstrip("/")
        self._people: dict[str, Person] = {}
        self._standing: dict[tuple[str, str], int] = {}
        self.sketch_by_n: dict[int, SketchView] = {}
        self.papers = [PaperView(self, p) for p in sorted(archive.papers.values(), key=lambda p: p.number)]
        self.paper_by_n = {pv.number: pv for pv in self.papers}
        self.sketches = [SketchView(self, s) for s in sorted(archive.sketches.values(), key=lambda s: s.number)]
        self.sketch_by_n.update({sv.number: sv for sv in self.sketches})
        self.recent_count = archive.recent_count

    # urls
    def url(self, path: str) -> str:
        return self.prefix + path

    def abs_url(self, key: str) -> str:
        return f"{self.base_url}{self.url(f'/abs/{key}/')}"

    # people
    def person(self, handle: str) -> Person:
        if handle not in self._people:
            acc = self.a.accounts.get(handle)
            if acc is None:
                self._people[handle] = Person(handle, handle)
            else:
                op = self.person(acc.operator) if acc.is_agent and acc.operator else None
                self._people[handle] = Person(handle, acc.display_name, acc.is_agent, op, acc.pseudonymous)
        return self._people[handle]

    def standing(self, handle: str, field_code: str) -> int:
        k = (handle, field_code)
        if k not in self._standing:
            self._standing[k] = standing(self.a, handle, field_code, self.today)
        return self._standing[k]

    # categories and counts
    @property
    def fields(self):
        return self.a.fields

    def cat_papers(self, code: str) -> list[PaperView]:
        return [pv for pv in self.papers if pv.p.category == code and pv.listed]

    def cat_sketches(self, code: str) -> list[SketchView]:
        return [sv for sv in self.sketches if sv.s.category == code and sv.listed]

    def cat_count(self, code: str) -> int:
        return len(self.cat_papers(code)) + len(self.cat_sketches(code))

    def shown(self, code: str) -> bool:
        """At or above the visibility threshold, a category shows counts, else an invitation."""
        cat = self.a.categories[code]
        return self.cat_count(code) >= cat.threshold

    # paper listings
    def paper_recent(self, code: str) -> Listing:
        """The newest entries in a category, capped at recent_count.

        A submission and a later version are separate events. A paper appears once, filed
        by its newest event, so a paper revised since it was submitted lists as a new
        version rather than a new paper.
        """
        events = []
        for pv in self.papers:
            if not pv.listed:
                continue
            v1 = pv.p.versions[0]
            cur = pv.as_of(self.today)
            if cur is None:
                continue
            if pv.p.category == code:
                events.append((v1.date, pv.number, "new", cur))
                if cur.v.date != v1.date:
                    events.append((cur.v.date, pv.number, "versions", cur))
            elif code in pv.p.cross_list:
                events.append((v1.date, pv.number, "cross", cur))
        events.sort(key=lambda e: (e[0], e[1]), reverse=True)
        order, picked = [], {}
        for _, number, bucket, view in events[: self.recent_count]:
            if number not in picked:
                order.append(number)
                picked[number] = (bucket, view)
        out = Listing()
        for number in order:
            bucket, view = picked[number]
            getattr(out, bucket).append(view)
        return out

    def paper_month(self, code: str, ym: str) -> Listing:
        end = min(month_end(ym), self.today)
        out = Listing()
        for pv in self.papers:
            if not pv.listed:
                continue
            v1 = pv.p.versions[0]
            if month_key(v1.date) == ym:
                cur = pv.as_of(end)
                if pv.p.category == code:
                    out.new.append(cur)
                elif code in pv.p.cross_list:
                    out.cross.append(cur)
            elif pv.p.category == code:
                inside = [v for v in pv.versions if month_key(v.v.date) == ym]
                if inside:
                    out.versions.append(inside[-1])
        return out

    def months(self, code: str) -> list[str]:
        dates = [v.date for pv in self.papers if pv.p.category == code or code in pv.p.cross_list for v in pv.p.versions]
        dates += [sv.s.date for sv in self.sketches if sv.s.category == code]
        now = month_key(self.today)
        if not dates:
            return [now]
        y, m = min(dates).year, min(dates).month
        out = []
        while f"{y:04d}-{m:02d}" <= now:
            out.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return list(reversed(out))

    # sketch listings
    def sketch_recent(self, code: str) -> Listing:
        rows = sorted(self.cat_sketches(code), key=lambda sv: (sv.s.date, sv.number), reverse=True)
        return Listing(new=rows[: self.recent_count])

    def sketch_month(self, code: str, ym: str) -> Listing:
        return Listing(new=[sv for sv in self.cat_sketches(code) if month_key(sv.s.date) == ym])

    # other lists
    @property
    def graduated(self) -> list[VersionView]:
        return [v for pv in self.papers if not pv.removed for v in pv.versions if v.graduation and v.visible]

    @property
    def queue(self) -> list[tuple[object, str]]:
        """What needs a check next, lowest stage first."""
        out = []
        for pv in self.papers:
            if not pv.listed or pv.withdrawn:
                continue
            v = pv.current
            fams = v.v.rubric_families
            if v.state.pending:
                need = "Re-check the items a minor version reopened"
            elif v.tier_index == 0:
                need = "Needs T1, citations checked (rubric citations 1.0.0)"
                if v.state.statuses.get("T1") in ("failed", "contested"):
                    need = f"T1 {v.state.statuses['T1']}; needs a fix or a new T1 check"
            elif v.tier_index < 4 and fams and all(f in self.a.rubrics.ids() for f in fams):
                nxt = f"T{v.tier_index + 1}"
                status = v.state.statuses.get(nxt, "none")
                need = f"Needs {nxt}, {TIER_NAMES[nxt]} ({', '.join(fams)})"
                if status in ("failed", "contested"):
                    need = f"{nxt} {status}; open to a fix or a further check"
            else:
                continue
            out.append((v, need))
        for sv in self.sketches:
            if sv.listed and sv.stage == "N0":
                out.append((sv, "Needs a novelty check"))
        return sorted(out, key=lambda x: (getattr(x[0], "tier_index", getattr(x[0], "stage_index", 0)), -x[0].pv.number if hasattr(x[0], "pv") else -x[0].number))

    # identifiers, for the 404 page
    def issued(self) -> dict:
        return {
            "paper": {str(pv.number): [str(v.number) for v in pv.versions] for pv in self.papers},
            "sketch": {str(sv.number): ["1.0"] for sv in self.sketches},
        }
