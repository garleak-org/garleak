# SPDX-License-Identifier: AGPL-3.0-or-later
"""Verifications, novelty checks, contests, reader votes, claims, reports and appeals."""

from __future__ import annotations

import datetime as dt

from garleak_archive import ledger
from garleak_archive.models import ItemResult, NoveltyCheck, Verification
from garleak_archive.stages import CITATIONS, contributors

from . import labels as L
from .assign import next_seq
from .forms import parse_body
from .requests import (
    Fields,
    build_claim,
    build_contest,
    build_novelty,
    build_report,
    build_verify,
    build_vote,
)

ATTEST = ("I did not contribute to this version or to an earlier version of this paper, and I do not operate "
          "an agent that did. I declared every shared affiliation and recent co-authorship with a contributor "
          "that I know of.")
ATTEST_T4 = ("I know of no shared affiliation, co-authorship within the conflict window, or other close working "
             "relationship with any contributor that the automated check could have missed (SPEC §3.6.9).")


def current_rubric(rubrics, rid: str):
    found = [r for r in rubrics if r.id == rid]
    if not found:
        return None
    active = [r for r in found if r.status == "active"]
    return max(active or found, key=lambda r: tuple(int(x) for x in r.version.split(".")))


class RecordMixin:
    # -------------------------------------------------------- shared

    def _rate(self, acc, kind: str) -> None:
        lim = self.cfg["limits"]
        key, attr, word = (("verifications_per_day", "verifications", "paper verifications") if kind == "verification"
                           else ("novelty_checks_per_day", "novelty_checks", "novelty checks"))
        n = getattr(ledger.daily_counts(self.a, [acc.handle], self.day, self.pending), attr)
        if n >= lim["human"][key]:
            self.res.fail("rate", "Daily limit", f"You have recorded {n} {word} today (UTC); the limit is "
                          f"{lim['human'][key]}. Careful checking is slow, and a burst is a signal.",
                          "SPEC §5.6.6 (OQ-12)")
        else:
            self.res.ok("rate", "Daily limit", f"{n + 1} of {lim['human'][key]} {word} today")
        b = lim["burst"]
        recent = ledger.recent_records(self.a, acc.handle, self.created, b["window_minutes"], self.pending)
        if recent >= b["records"]:
            self.res.flag("burst", "Burst", f"{recent + 1} records within {b['window_minutes']} minutes. This is "
                          "flagged for a moderator and not blocked.", "SPEC §5.6.6")
            self.res.labels_add.append(L.FLAGS["burst"])

    def _loop(self, ref: str, t4: bool) -> dict | None:
        labels = ledger.loop_labels(self.a)
        lab = labels.get(ref)
        if lab is None:
            self.res.ok("loop", "Reciprocal loops", "not part of a loop in the verification graph")
            return None
        if t4:
            self.res.fail("loop", "Reciprocal loop", f"This would close a reciprocal loop of length {lab.length}, and a "
                          "loop-labeled verification never counts toward T4.", "SPEC §2.4.7, §5.6.4")
        else:
            self.res.flag("loop", "Reciprocal loop", f"This closes a reciprocal loop of length {lab.length}. It is "
                          "recorded and counts toward T1 to T3 with the label shown, but earns no credit and never "
                          "counts toward T4, graduation or standing.", "SPEC §5.6.3, §5.6.4")
            self.res.labels_add.append(L.FLAGS["loop"])
        return lab.as_record()

    def _earn(self, acc, field_code: str, field_name: str, amount, loop) -> None:
        from .process import fmt

        before = ledger.balance(self.a, acc.handle, field_code, self.pending)
        gain = 0 if loop else amount
        after = before + ledger.dec(gain)
        self.res.balance = {"account": acc.handle, "field": field_name, "before": fmt(before), "after": fmt(after),
                            "floor": fmt(self.cfg["credits"]["balance_floor"])}

    def _not_contributor(self, acc, paper, ver) -> None:
        contribs = contributors(paper, ver)
        if acc.handle in contribs:
            self.res.fail("independence", "Not a contributor", f"You contributed to v{ver.number} or an earlier "
                          "version of this paper, so you cannot verify it.", "SPEC §4.2.8")
        elif acc.handle in {ledger.responsible(self.a, h) for h in contribs}:
            self.res.fail("independence", "Not a contributor", "You operate an agent that contributed to this "
                          "version.", "SPEC §3.6.5, §4.2.8")
        else:
            self.res.ok("independence", "Not a contributor", f"checked against the contributor list of v{ver.number}")

    def _version(self, number, version):
        if number is None or version is None:
            return None, None
        p = self.a.papers.get(number)
        ver = p.version(version) if p else None
        if p is None:
            self.res.fail("version", "Version", f"paper:{number} does not exist.", "SPEC §2.3.7")
        elif ver is None:
            self.res.fail("version", "Version", f"paper:{number} has no v{version}. Verifications, votes and "
                          "contests attach to an exact version that exists.", "SPEC §4.2.1")
        elif p.status != "admitted":
            self.res.fail("version", "Version", f"paper:{number} is {p.status}, which stops new records on it.",
                          "SPEC §9.7.1")
        else:
            self.res.ok("version", "Version", f"paper:{number}v{version}")
            return p, ver
        return None, None

    def _scratch(self, number):
        if number is None:
            return None
        s = self.a.scratches.get(number)
        if s is None:
            self.res.fail("scratch", "Scratch", f"scratch:{number} does not exist.", "SPEC §2.3.7")
        elif s.status != "admitted":
            self.res.fail("scratch", "Scratch", f"scratch:{number} is {s.status}.", "SPEC §9.7.1")
        else:
            self.res.ok("scratch", "Scratch", f"scratch:{number}v1.0")
            return s
        return None

    def _problems(self, f: Fields) -> None:
        for p in f.problems:
            self.res.fail("form", f"Form: {p.field}", p.message, "the issue form")

    # -------------------------------------------------------- verification (§4.2)

    def do_verify(self, f: Fields):
        req = build_verify(f)
        acc = self.need_account(human_only=True)
        self._problems(f)
        p, ver = self._version(req.paper, req.version)
        if acc and ver:
            self._not_contributor(acc, p, ver)
        rub = None
        if req.rubric_id and req.tier and ver:
            cur = current_rubric(self.a.rubrics, req.rubric_id)
            crit = "SPEC §10.3.2"
            if cur is None:
                self.res.fail("rubric", "Rubric", f"There is no rubric {req.rubric_id!r}.", "SPEC §10.3")
            elif req.rubric_version and req.rubric_version != cur.version:
                self.res.fail("rubric", "Rubric", f"New verifications use the current version of each rubric, "
                              f"{cur.id} {cur.version}, not {req.rubric_version}.", crit)
            elif req.tier not in cur.tiers:
                self.res.fail("rubric", "Rubric", f"{cur.id} {cur.version} does not cover {req.tier}.", "SPEC §4.2.2")
            elif req.tier == "T1" and cur.id != CITATIONS:
                self.res.fail("rubric", "Rubric", "T1 uses the citations rubric in every field.", "SPEC §4.2.2")
            elif req.tier != "T1" and cur.id not in ver.rubric_families:
                fams = ", ".join(ver.rubric_families) or "no rubric family"
                self.res.fail("rubric", "Rubric", f"v{ver.number} declares {fams}, so it cannot be verified at "
                              f"{req.tier} against {cur.id}.", "SPEC §2.4.8, §2.4.9")
            else:
                rub = cur
                self.res.ok("rubric", "Rubric", f"{cur.id} {cur.version} at {req.tier}")
        result = "passed"
        if rub is not None:
            bad, listed = [], {}
            for it in req.items:
                item = rub.items.get(it.id)
                if item is None:
                    bad.append(f"{it.id} is not an item of {rub.id} {rub.version}")
                elif item.tier != req.tier:
                    bad.append(f"{it.id} belongs to {item.tier}, not {req.tier}")
                elif it.id in listed:
                    bad.append(f"{it.id} is listed twice")
                elif it.verdict == "na" and not item.na_allowed:
                    bad.append(f"{it.id} is never not applicable")
                elif it.verdict == "na" and not it.note:
                    bad.append(f"{it.id}: a not-applicable verdict needs a reason in the note")
                elif it.verdict in ("pass", "fail") and not it.evidence:
                    bad.append(f"{it.id}: give the evidence the item asks for (a link, a log or a commit hash)")
                else:
                    listed[it.id] = it
            required = [i.id for i in rub.required_at(req.tier)]
            missing = [i for i in required if i not in listed]
            if req.kind == "paper" and missing:
                bad.append("no verdict for the required item(s) " + ", ".join(missing))
            if req.kind == "recheck" and not listed:
                bad.append("a re-check gives a verdict for at least one reopened item")
            if bad:
                self.res.fail("items", "Rubric items", "; ".join(bad[:6]) + ".", "SPEC §4.2.4")
            else:
                fails = [i for i in required if i in listed and listed[i].verdict == "fail"]
                result = "failed" if fails else "passed"
                self.res.ok("items", "Rubric items", f"{len(listed)} verdicts, result {result}"
                            + (f" ({', '.join(fails)} failed)" if fails else ""))
        if acc:
            self._rate(acc, "verification")
        independent = None
        if req.tier == "T4" and not self.res.failed:
            if req.conflicts:
                self.res.fail("conflict", "Independence", "T4 needs a verifier with no shared affiliation or recent "
                              "co-authorship with any contributor. You declared one, so record this at T3.",
                              "SPEC §2.4.7, §5.6.8")
            else:
                cc = self.last("conflict-check", moderator=True)
                if cc is None:
                    return self.waiting(
                        "Waiting for the moderators' conflict check.",
                        "A T4 verification needs a verifier independent of every contributor (SPEC §2.4.7). The "
                        "moderators check shared affiliation and co-authorship against held data that never enters "
                        "the repository, then comment /conflict-check here. Only the result is recorded.")
                if cc.args[:1] == ["independent"]:
                    independent = {"value": True, "computed_at": cc.at.date().isoformat(),
                                   "sources": [f"contributor list of v{ver.number} (public)", "verifier declaration",
                                               "declared affiliations and co-authorships, held by moderators"]}
                    self.res.ok("conflict", "Conflict check", "independent, checked by the moderators on held data")
                else:
                    self.res.fail("conflict", "Conflict check", "The moderators' conflict check found a conflict, "
                                  "so this cannot count as T4. It can be recorded at T3 with a flag.",
                                  "SPEC §2.4.7, §3.6.5")
        elif req.conflicts:
            self.res.info("conflict", "Conflict declared", "recorded as a public flag: " + ", ".join(req.conflicts)
                          + ". Allowed below T4, and it names no party (SPEC §3.3.7, §3.6.6).")
        if self.res.failed or rub is None:
            return self.refuse()
        vid = next_seq(f"{p.number}-", [v.id for v in p.verifications], self.taken.get("verification", set()), 2,
                       self.mine.get("verification", ()))
        date = max(self.day, ver.date)
        items = [ItemResult(i.id, i.verdict, i.note, i.evidence) for i in req.items]
        probe = Verification(vid, p.number, ver.number, req.kind, req.tier, rub.id, rub.version, acc.handle, date,
                             result, req.summary, items)
        p.verifications.append(probe)
        try:
            loop = self._loop(f"verification:{vid}", req.tier == "T4")
        finally:
            p.verifications.remove(probe)
        if self.res.failed:
            return self.refuse()
        cat = self.a.categories[p.category]
        self._earn(acc, cat.field_code, cat.field_name, self.cfg["credits"]["earn"]["verification"], loop)
        rec = {"id": vid, "version": str(ver.number), "kind": req.kind, "tier": req.tier,
               "rubric": {"id": rub.id, "version": rub.version}, "verifier": acc.handle, "date": date.isoformat(),
               "result": result, "summary": " ".join(req.summary.split()), "items": []}
        for it in req.items:
            item = {"id": it.id, "verdict": it.verdict}
            if it.note:
                item["note"] = it.note
            if it.evidence:
                item["evidence"] = it.evidence
            rec["items"].append(item)
        if req.automated:
            rec["automated"] = req.automated
        if req.time_spent is not None:
            rec["time_spent_minutes"] = req.time_spent
        if req.model_use:
            rec["model_use"] = " ".join(req.model_use.split())
        if req.tier == "T4":
            rec["independent"] = independent
            rec["t4_attestation"] = {"text": ATTEST_T4, "date": date.isoformat()}
        else:
            if req.conflicts:
                rec["conflict_flags"] = [{"type": t, "computed_at": date.isoformat(), "sources": ["verifier declaration"]}
                                         for t in req.conflicts]
            rec["attestation"] = {"text": ATTEST, "date": date.isoformat()}
        rec["status"] = "active"
        rec["intake"] = self.intake()
        self.w.data(f"papers/{p.number}/verifications/{vid}.yaml", rec)
        self.meta("verification", [f"verification:{vid}"], acc.handle, cat.field_code)
        return self.done([f"verification {vid} of paper:{p.number}v{ver.number}"],
                         f"Add verification {vid} of paper:{p.number}v{ver.number}", True)

    # -------------------------------------------------------- novelty check (§2.5, §4.4)

    def do_novelty(self, f: Fields):
        req = build_novelty(f)
        acc = self.need_account(human_only=True)
        self._problems(f)
        s = self._scratch(req.scratch)
        if acc and s:
            if ledger.responsible(self.a, s.author) == acc.handle:
                self.res.fail("independence", "Not the author", "A scratch's author, or the operator of an agent "
                              "that wrote it, cannot check it.", "SPEC §4.4.3")
            else:
                self.res.ok("independence", "Not the author", f"u/{s.author} wrote it")
        if req.outcome == "N1" and not (req.sources and req.queries):
            self.res.fail("outcome", "N1 search record", "N1 needs the sources searched and the queries used.",
                          "SPEC §2.5.2")
        if req.outcome == "N2" and not any(x.get("overlap") for x in req.prior_work):
            self.res.fail("outcome", "N2 prior work", "N2 needs at least one prior work, written `reference | how it "
                          "overlaps`.", "SPEC §2.5.3")
        if req.outcome == "N3":
            if not req.tractability:
                self.res.fail("outcome", "N3 tractability", "N3 needs a note on what testing the idea would take.",
                              "SPEC §2.5.5")
            if s and not any(c.outcome in ("N1", "N2") and c.status == "active" for c in s.checks):
                self.res.fail("outcome", "N3 path", "N3 needs an earlier N1 or N2 check on the scratch.",
                              "SPEC §2.5.5")
        if acc:
            self._rate(acc, "novelty")
        if self.res.failed or s is None:
            return self.refuse()
        cid = next_seq(f"{s.number}-n", [c.id for c in s.checks], self.taken.get("check", set()), 1,
                       self.mine.get("check", ()))
        date = max(self.day, s.date)
        probe = NoveltyCheck(cid, req.outcome, acc.handle, date)
        s.checks.append(probe)
        try:
            loop = self._loop(f"novelty:{cid}", False)
        finally:
            s.checks.remove(probe)
        cat = self.a.categories[s.category]
        self._earn(acc, cat.field_code, cat.field_name, self.cfg["credits"]["earn"]["novelty_check"], loop)
        check = {"id": cid, "outcome": req.outcome, "checker": acc.handle, "date": date.isoformat(),
                 "summary": " ".join(req.summary.split())}
        for key, val in (("sources", req.sources), ("queries", req.queries), ("closest", req.closest),
                         ("prior_work", req.prior_work)):
            if val:
                check[key] = val
        if req.tractability:
            check["tractability"] = " ".join(req.tractability.split())
        check["status"] = "active"
        if req.time_spent is not None:
            check["time_spent_minutes"] = req.time_spent
        if req.model_use:
            check["model_use"] = " ".join(req.model_use.split())
        check["intake"] = self.intake()
        rel = f"scratches/{s.number}.yaml"
        data = self.w.load(rel)
        data.setdefault("checks", []).append(check)
        self.w.data(rel, data)
        self.meta("novelty", [f"check:{cid}"], acc.handle, cat.field_code)
        return self.done([f"novelty check {cid} of scratch:{s.number}"],
                         f"Add novelty check {cid} of scratch:{s.number}", True)

    # -------------------------------------------------------- contest (§4.5.7)

    def do_contest(self, f: Fields):
        req = build_contest(f)
        acc = self.need_account()
        self._problems(f)
        p, ver = self._version(req.paper, req.version)
        if p and ver and req.prediction:
            pred = next((x for x in p.predictions if x.id == req.prediction), None)
            if pred is None or pred.version != ver.number:
                self.res.fail("prediction", "Prediction", f"v{ver.number} has no prediction {req.prediction!r}.",
                              "SPEC §4.5.7")
            else:
                self.res.ok("prediction", "Prediction", f"{pred.classifier_id} {pred.classifier_version}")
            if acc and acc.handle not in contributors(p, ver):
                self.res.fail("contributor", "Contributor", "Only a contributor to the version can contest its "
                              "prediction.", "SPEC §4.5.7")
        if self.res.failed or p is None:
            return self.refuse()
        cid = next_seq(f"{p.number}-c", [c.id for c in p.contests], self.taken.get("contest", set()), 1,
                       self.mine.get("contest", ()))
        self.w.data(f"papers/{p.number}/signals/{cid}.yaml", {
            "id": cid, "kind": "contest", "version": str(ver.number), "date": max(self.day, ver.date).isoformat(),
            "prediction": req.prediction, "axis": req.axis, "by": acc.handle,
            "statement": " ".join(req.statement.split()), "intake": self.intake()})
        self.res.info("record", "What a contest does", "it is shown next to the prediction and kept as calibration "
                      "data. It is not adjudicated and does not remove the prediction.")
        self.meta("contest", [f"contest:{cid}"], acc.handle, self.a.field_of(p.category))
        return self.done([f"contest {cid}"], f"Add contest {cid} of paper:{p.number}v{ver.number}", True)

    # -------------------------------------------------------- reader vote (§4.5.8, §3.7.5)

    def _earlier_vote(self, paper: int, version) -> tuple[int, str | None, str | None] | None:
        best = None
        for row in self.ctx.votes:
            n = int(row.get("number") or 0)
            names = {x.get("name") if isinstance(x, dict) else x for x in row.get("labels") or []}
            if n == self.number or L.STATUS["merged"] not in names:
                continue
            values, missing = parse_body(self.form, row.get("body") or "")
            ff = Fields(self.form, values, missing)
            v = build_vote(ff)
            if v.paper == paper and v.version == version and (best is None or n > best[0]):
                best = (n, v.writing, v.analysis)
        return best

    def do_vote(self, f: Fields):
        if not self.cfg["intake"]["votes_enabled"]:
            self.res.fail("votes", "Votes", "Community votes are switched off at the moment.", "config.yaml intake")
            return self.refuse()
        if L.STATUS["merged"] in self.labels:
            return self.noop("This vote is already counted.", "To change it, open a new vote. The new one replaces "
                             "this one (SPEC §4.5.8).")
        req = build_vote(f)
        acc = self.need_account(human_only=True)
        self._problems(f)
        p, ver = self._version(req.paper, req.version)
        if acc and ver and acc.handle in {ledger.responsible(self.a, h) for h in contributors(p, ver)}:
            self.res.fail("contributor", "Not a contributor", "Contributors do not vote on their own version.",
                          "SPEC §4.5.8")
        if self.res.failed or p is None:
            return self.refuse()
        tally = next((t for t in p.tallies if t.version == ver.number), None)
        tid = tally.id if tally else f"{p.number}-readers-{ver.number.major}-{ver.number.minor}"
        counts = {ax: dict((tally.counts.get(ax) or {}) if tally else {}) for ax in ("writing", "analysis")}
        earlier = self._earlier_vote(p.number, ver.number)
        if earlier:
            for ax, code in (("writing", earlier[1]), ("analysis", earlier[2])):
                if code and counts[ax].get(code, 0) > 0:
                    counts[ax][code] -= 1
            self.res.info("replaces", "Earlier vote", f"this vote replaces your vote in #{earlier[0]}; both stay on "
                          "GitHub")
        for ax, code in (("writing", req.writing), ("analysis", req.analysis)):
            if code:
                counts[ax][code] = counts[ax].get(code, 0) + 1
        rec = {"id": tid, "kind": "readers", "version": str(ver.number), "date": max(self.day, ver.date).isoformat()}
        for ax in ("writing", "analysis"):
            kept = {k: v for k, v in sorted(counts[ax].items()) if v > 0}
            if kept:
                rec[ax] = kept
        rec["intake"] = self.intake()
        self.w.data(f"papers/{p.number}/signals/{tid}.yaml", rec)
        self.res.info("public", "Public vote", "In Phase 1 this issue shows your GitHub account and your vote. The "
                      "archive stores only the counts (SPEC §3.7.5).")
        self.meta("vote", [f"tally:{tid}"], acc.handle, self.a.field_of(p.category))
        return self.done([f"a vote on paper:{p.number}v{ver.number}"], f"Count a vote on paper:{p.number}v{ver.number}",
                         True)

    # -------------------------------------------------------- claim (§2.5.7)

    def do_claim(self, f: Fields):
        req = build_claim(f)
        acc = self.need_account()
        self._problems(f)
        s = self._scratch(req.scratch)
        if acc and s:
            active = [c for c in s.claims if c.by == acc.handle and (c.expires is None or c.expires >= self.day)]
            if active:
                self.res.fail("claim", "Claim", f"You already hold an active claim on scratch:{s.number}, until "
                              f"{active[-1].expires}.", "SPEC §2.5.7")
        if self.res.failed or s is None:
            return self.refuse()
        days = self.cfg["intake"]["scratch_claim_days"]
        expires = self.day + dt.timedelta(days=days)
        rel = f"scratches/{s.number}.yaml"
        data = self.w.load(rel)
        data.setdefault("claims", []).append({"by": acc.handle, "date": self.date_iso(), "expires": expires.isoformat(),
                                              "intake": self.intake()})
        self.w.data(rel, data)
        self.res.info("claim", "What a claim means", f"non-exclusive, no priority, expires on {expires} "
                      "(SPEC §2.5.7)")
        self.meta("claim", [f"claim:{s.number}-{acc.handle}"], acc.handle, self.a.field_of(s.category))
        return self.done([f"a claim on scratch:{s.number}"], f"Add a claim on scratch:{s.number}", True)

    # -------------------------------------------------------- report or appeal (§8.4, §9.6)

    def do_report(self, f: Fields):
        req = build_report(f)
        self._problems(f)
        if self.res.failed:
            return self.refuse()
        r = self.res
        r.status = "acknowledged"
        if req.kind == "appeal":
            r.labels_add.append(L.MODERATION["appeal"])
            r.headline = "Appeal received."
            r.lead = (f"A different moderator from the one who made the decision reviews it, with a target of 14 days, "
                      f"and that decision is final on Garleak (SPEC §8.4.4). An appeal must come within "
                      f"{self.cfg['intake']['appeal_days']} days of the decision, and each decision can be appealed once.")
        else:
            r.labels_add.append(L.MODERATION["report"])
            r.headline = "Report received."
            r.lead = ("A moderator will look at it"
                      + (f" under criterion {req.criterion}" if req.criterion else "")
                      + ". This issue is public. For personal data, a legal matter or harm, write to "
                        "contact@garleak.org instead, and say so here without the details.")
        return r
