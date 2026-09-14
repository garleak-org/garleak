# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routing, moderator actions and the identity form."""

from __future__ import annotations

import re

from garleak_archive.models import Paper, Scratch

from . import labels as L
from .forms import parse_body
from .orcid import OrcidRecord, github_url_for, normalize_orcid, orcid_checksum_ok
from .process import CONTACT, CRITERIA, Base, fmt
from .recording import RecordMixin
from .requests import HANDLE_RE, Fields, build_identity
from .submit import SubmitMixin

MODERATOR_ONLY = ("approve-email", "conflict-check", "reject", "remove")


class Intake(RecordMixin, SubmitMixin, Base):
    def run(self):
        if self.form is None:
            return self.noop("No intake form on this issue.", comment=False)
        t = self.trigger
        if t is not None:
            if t.name in MODERATOR_ONLY and not t.moderator:
                return self.noop(f"Only moderators can use /{t.name}.",
                                 "Nothing changed. If you meant to ask for a check again, comment /recheck.")
            if t.name == "recheck" and not (t.author or t.moderator):
                return self.noop("", comment=False)
        acting = t is not None and t.moderator and t.name in ("reject", "remove")
        if self.state == "closed" and not acting:
            return self.noop("This issue is closed.", comment=False)
        existing = self.find_existing()
        if acting and t.name == "remove":
            return self.do_remove(existing, t)
        if acting and t.name == "reject":
            if existing:
                return self.noop("This issue is already recorded as " + ", ".join(x for x, _ in existing) + ".",
                                 "To take down admitted content, comment /remove followed by the criterion number.")
            return self.do_reject(t)
        if existing and self.kind != "vote":
            return self.noop("Already recorded as " + ", ".join(x for x, _ in existing) + ".",
                             "Records never change once merged, so editing this issue changes nothing. To change a "
                             "paper, open the new-version form. To take something back, see "
                             "https://garleak.org/moderation/#removal.")
        values, missing = parse_body(self.form, self.body)
        return getattr(self, f"do_{self.kind}")(Fields(self.form, values, missing))

    # -------------------------------------------------------- lookups

    def find_existing(self) -> list[tuple[str, object]]:
        n = self.number
        out: list[tuple[str, object]] = []

        def mine(block) -> bool:
            return bool(block) and block.get("issue") == n

        for acc in self.a.accounts.values():
            if mine(acc.intake):
                out.append((f"u/{acc.handle}", acc))
        for p in self.a.papers.values():
            for v in p.versions:
                if mine(v.intake):
                    out.append((f"paper:{p.number}v{v.number}", p))
            for ver in p.verifications:
                if mine(ver.intake):
                    out.append((f"verification {ver.id} of paper:{p.number}v{ver.version}", ver))
            for c in p.contests:
                if mine(c.intake):
                    out.append((f"contest {c.id}", c))
        for s in self.a.scratches.values():
            if mine(s.intake):
                out.append((f"scratch:{s.number}", s))
            for ch in s.checks:
                if mine(ch.intake):
                    out.append((f"novelty check {ch.id} of scratch:{s.number}", ch))
            for cl in s.claims:
                if mine(cl.intake):
                    out.append((f"a claim on scratch:{s.number}", cl))
        for r in self.a.screening:
            if mine(r.intake):
                out.append((f"the rejection {r.id}", r))
        return out

    def criterion(self, t) -> int | None:
        m = re.match(r"^([1-4])$", t.args[0]) if t.args else None
        return int(m[1]) if m else None

    # -------------------------------------------------------- moderator actions

    def do_remove(self, existing, t):
        crit = self.criterion(t)
        if crit is None:
            return self.noop("Give the criterion: /remove followed by 1, 2, 3 or 4.",
                             "Every removal cites a numbered admission criterion (SPEC §8.4.3).")
        targets = [obj for _, obj in existing if isinstance(obj, (Scratch, Paper))]
        if not targets:
            return self.noop("Nothing here to remove.", "Removal applies to admitted papers and scratches "
                             "(SPEC §9.6). A verification is withdrawn, overturned or voided instead.")
        obj = targets[0]
        if obj.status == "removed":
            return self.noop("Already removed.")
        date = t.at.date().isoformat()
        if isinstance(obj, Scratch):
            rel, ident, auto = f"scratches/{obj.number}.yaml", f"scratch:{obj.number}", True
        else:
            rel, ident, auto = f"papers/{obj.number}/paper.yaml", f"paper:{obj.number}", False
        data = self.w.load(rel)
        data["status"] = "removed"
        data["removal"] = {"date": date, "criterion": str(crit)}
        self.w.data(rel, data)
        r = self.res
        r.status, r.ids, r.files, r.automerge = "removed", [ident], self.w.files, auto
        r.branch = f"intake/issue-{self.number}-removal"
        r.closes_issue = False
        r.pr_title = f"Remove {ident} under criterion {crit} (issue #{self.number})"
        no_refund = crit in self.cfg["credits"]["no_refund_criteria"]
        r.headline = f"Removed under admission criterion {crit}: {CRITERIA[crit]}."
        r.lead = ("The identifier keeps resolving, to a tombstone that gives the date and the criterion. "
                  + ("Under this criterion the credit charge stands (SPEC §5.4.5). " if no_refund else
                     "The credit charge is refunded (SPEC §5.4.5). ")
                  + f"The submitter may appeal once within {self.cfg['intake']['appeal_days']} days with the "
                  "report-or-appeal form, and a different moderator reviews it (SPEC §8.4.4).")
        self.res.meta = {"issue": self.number, "kind": "removal", "ids": [ident]}
        return r

    def do_reject(self, t):
        crit = self.criterion(t)
        if crit is None:
            return self.noop("Give the criterion: /reject followed by 1, 2, 3 or 4.",
                             "Every rejection cites a numbered admission criterion (SPEC §8.4.3).")
        r = self.res
        r.status, r.close_pr, r.close_issue = "rejected", True, "not planned"
        r.headline = f"Rejected under admission criterion {crit}: {CRITERIA[crit]}."
        charged = self.kind in ("paper", "scratch")
        no_refund = crit in self.cfg["credits"]["no_refund_criteria"]
        credit_note = ""
        if charged:
            credit_note = ("Under this criterion the credit charge stands (SPEC §5.4.5). " if no_refund
                           else "No credits are charged, because nothing was admitted. ")
        r.lead = (f"Nothing from this issue appears on the site. {credit_note}You may appeal once within "
                  f"{self.cfg['intake']['appeal_days']} days with the report-or-appeal form, and a different "
                  "moderator reviews the appeal (SPEC §8.4.4). The criteria are listed at "
                  "https://garleak.org/moderation/#criteria.")
        if charged and no_refund:
            values, _ = parse_body(self.form, self.body)
            m = re.match(r"^([a-z][a-z0-9]*\.[a-z][a-z0-9-]*)\b", str(values.get("category") or ""))
            acc = self.account_by_github(self.author)
            if acc and m and m[1] in self.a.categories:
                sid = f"reject-{self.number}"
                self.w.data(f"screening/{sid}.yaml", {
                    "id": sid, "decision": "reject", "criterion": crit, "date": t.at.date().isoformat(),
                    "object": self.kind, "category": m[1], "submitter": acc.handle, "intake": self.intake()})
                r.ids, r.files, r.automerge = [f"screening:{sid}"], self.w.files, True
                r.branch = f"intake/issue-{self.number}-rejection"
                r.closes_issue = False
                r.pr_title = f"Record the rejection of issue #{self.number} under criterion {crit}"
                r.meta = {"issue": self.number, "kind": "rejection", "ids": r.ids}
        return r

    # -------------------------------------------------------- identity

    def orcid_record(self, orcid: str) -> OrcidRecord | None:
        if self.ctx.orcid and self.ctx.orcid.get("orcid") == orcid:
            return OrcidRecord.from_dict(self.ctx.orcid)
        if self.opts.orcid_client and not self.opts.offline:
            return self.opts.orcid_client.lookup(orcid)
        return None

    def do_identity(self, f: Fields):
        r = self.res
        linked = self.account_by_github(self.author)
        if linked:
            return self.noop(f"This GitHub account is already linked as u/{linked.handle}.")
        req = build_identity(f)
        for p in f.problems:
            r.fail("form", f"Form: {p.field}", p.message, "the issue form")
        handle = req.handle or self.author.lower()
        if not HANDLE_RE.match(handle):
            r.fail("handle", "Handle", f"u/{handle} is not a valid handle. Choose one in the form: 2 to 39 "
                   "lowercase letters, digits or hyphens.", "archive/FORMAT.md")
        elif handle in self.a.accounts or handle in self.taken.get("account", set()):
            r.fail("handle", "Handle", f"u/{handle} is taken. Choose another handle in the form.", "SPEC §3.3.2")
        else:
            r.ok("handle", "Handle", f"u/{handle} is free")
        record: dict = {"handle": handle}
        if req.kind == "agent":
            op = self.a.accounts.get(req.operator) if req.operator else None
            if op is None or op.is_agent or op.status != "active" or not op.identity_path:
                r.fail("operator", "Operator", f"u/{req.operator} must be an active human account with a verified "
                       "identity.", "SPEC §3.4.1")
            else:
                r.ok("operator", "Operator", f"u/{op.handle}")
            if r.failed:
                return self.refuse()
            confirmed = op.github and self.last("confirm-operator", user=op.github)
            if not confirmed:
                return self.waiting(f"Waiting for u/{op.handle} to confirm.",
                                    f"The operator answers for this agent and pays its credits (SPEC §3.4). "
                                    f"@{op.github}, if you operate this agent, comment /confirm-operator here. "
                                    "Then the bot opens the pull request for a moderator.")
            r.ok("operator-confirmed", "Operator confirmed", f"u/{op.handle} confirmed on this issue")
            record.update({"display_name": req.display_name or handle, "kind": "agent", "operator": op.handle,
                           "github": self.author, "agent": {"models": req.models}})
            if req.runner_url:
                record["agent"]["runner_url"] = req.runner_url
            r.labels_add.append(L.FLAGS["agent"])
        else:
            if req.path == "orcid":
                orcid = normalize_orcid(req.orcid)
                if orcid is None or not orcid_checksum_ok(orcid):
                    r.fail("orcid", "ORCID iD", f"{req.orcid!r} is not a valid ORCID iD; its check digit does not "
                           "match. Copy it from your ORCID record.", "SPEC §3.7.2")
                else:
                    rec = self.orcid_record(orcid)
                    want = f"https://github.com/{self.author}"
                    if rec is None:
                        r.fail("orcid", "ORCID record", "The ORCID lookup did not run. Comment /recheck to try "
                               "again.", "SPEC §3.7.2")
                    elif rec.status == "not_found":
                        r.fail("orcid", "ORCID record", f"ORCID has no public record for {orcid}.", "SPEC §3.7.2")
                    elif rec.status != "ok":
                        r.fail("orcid", "ORCID record", f"ORCID did not answer ({rec.error or rec.http_status}). "
                               "Comment /recheck to try again.", "SPEC §3.7.2")
                    elif not github_url_for(rec.urls, self.author):
                        r.fail("orcid", "ORCID record", f"Your public ORCID record does not list {want}. Add it "
                               "under Websites and social links, with visibility set to Everyone, then comment "
                               "/recheck.", "SPEC §3.7.2")
                    else:
                        r.ok("orcid", "ORCID record", f"{orcid} lists {want}")
                        if rec.name and not req.pseudonymous:
                            same = rec.name.casefold().split() == req.display_name.casefold().split()
                            r.info("orcid-name", "Name on ORCID", f"ORCID shows {rec.name!r}; you asked to show "
                                   f"{req.display_name!r}" + ("" if same else ". The moderator compares them."))
                        if req.pseudonymous:
                            r.info("orcid-public", "Pseudonym", "The iD is not stored with a handle-only account, "
                                   "but your ORCID record lists this GitHub account for anyone who looks "
                                   "(SPEC §3.7.3). If you need a pseudonym, use the institutional email path.")
                        else:
                            record["orcid"] = orcid
            elif req.path == "institutional_email":
                if not r.failed and not self.last("approve-email", moderator=True):
                    return self.waiting(
                        "Waiting for a moderator to check your institutional email.",
                        f"Write to {CONTACT} from your institutional address, quote issue #{self.number}, and list "
                        "your current affiliations. Do not post the address or the affiliations in this issue. A "
                        "moderator keeps them outside the repository and comments /approve-email here.")
                if not r.failed:
                    r.ok("email", "Institutional email", "checked by a moderator; the evidence stays outside the "
                         "repository (SPEC §3.7.3)")
            if r.failed:
                return self.refuse()
            record.update({"display_name": f"u/{handle}" if req.pseudonymous else req.display_name})
            if req.pseudonymous:
                record["pseudonymous"] = True
            record.update({"kind": "human", "identity_path": req.path})
            if "orcid" in record:
                record["orcid"] = record.pop("orcid")
            record["github"] = self.author
        if r.failed:
            return self.refuse()
        record.update({"status": "active", "joined": self.date_iso(), "intake": self.intake()})
        self.w.data(f"accounts/{handle}.yaml", record)
        self.meta("identity", [f"account:{handle}"], handle)
        return self.done([f"u/{handle}"], f"Link account u/{handle}", False,
                         held_reason="Every account link waits for a moderator, who checks the display name "
                                     "and merges the pull request. The account can act once it is merged.")


__all__ = ["Intake", "fmt"]
