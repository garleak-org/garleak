# SPDX-License-Identifier: AGPL-3.0-or-later
"""Process one issue: parse the form, run every check, write the records, and report.

Every run recomputes the outcome from the issue body, its comments, the archive on the
default branch and the open intake pull requests, so a re-run (an edit, `/recheck`, a
dispatch from the sync workflow) always reaches the same answer for the same inputs.
Moderator commands that approve something (`/approve-email`, `/conflict-check`) are read
from the comments on every run. Commands that act (`/reject`, `/remove`) act only when
they are the comment that triggered the run."""

from __future__ import annotations

import datetime as dt
import shutil
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from garleak_archive import ledger
from garleak_archive.loader import load_archive
from garleak_archive.models import Account, Archive, Category
from garleak_archive.validate import validate

from . import labels as L
from .assign import own, reserved
from .context import MODERATOR_ONLY, Command, Context, Comment, commands, last_bot_comment, parse_command, parse_ts
from .forms import Form, form_for_labels, load_forms
from .http import Http
from .orcid import OrcidClient
from .records import Writer, intake_block
from .report import Result

MODERATION_URL = "https://garleak.org/moderation/#criteria"
CONTACT = "contact@garleak.org"
CRITERIA = {
    1: "not a genuine attempt at research (spam, a test post, or nonsense)",
    2: "out of scope or in the wrong category",
    3: "gated content filed elsewhere",
    4: "harmful, defamatory or plagiarized, or posted without the right to",
}
NOUN = {"identity": "account link", "sketch": "sketch", "paper": "paper", "version": "new version",
        "verify": "verification", "novelty": "novelty check", "contest": "contest", "vote": "vote",
        "claim": "claim", "report": "report"}


@dataclass
class Options:
    dry_run: bool = False
    now: dt.datetime | None = None
    offline: bool = False
    citecheck: str | None = None
    forms_dir: Path | None = None
    rubrics_dir: Path | None = None
    http: Http | None = None
    orcid_client: OrcidClient | None = None


def fmt(d: Decimal | float | int) -> str:
    d = Decimal(str(d))
    return f"{d:.2f}" if d != d.quantize(Decimal("0.1")) else f"{d:.1f}"


def rubrics_dir_for(root: Path) -> Path | None:
    cfg = root / "archive.yaml"
    if cfg.is_file():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        if data.get("rubrics"):
            return (root / data["rubrics"]).resolve()
    return None


class Base:
    """State and helpers shared by the handlers."""

    def __init__(self, issue: dict, event: dict | None, archive: Archive, root: Path, ctx: Context,
                 opts: Options, forms: dict[str, Form]):
        self.issue = issue
        self.number = int(issue["number"])
        self.author = (issue.get("user") or {}).get("login", "")
        self.labels = [x["name"] if isinstance(x, dict) else str(x) for x in issue.get("labels") or []]
        self.body = issue.get("body") or ""
        self.state = issue.get("state", "open")
        self.created = parse_ts(issue.get("created_at") or dt.datetime.now(dt.timezone.utc))
        self.now = opts.now or dt.datetime.now(dt.timezone.utc)
        self.day = self.created.date()
        self.at = self.created.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.a = archive
        self.cfg = archive.config or {}
        self.root = root
        self.ctx = ctx
        self.opts = opts
        self.forms = forms
        self.form = form_for_labels(forms, self.labels)
        self.kind = self.form.kind if self.form else ""
        self.res = Result(issue=self.number, kind=self.kind, branch=f"intake/issue-{self.number}")
        self.w = Writer(root)
        self.cmds: list[Command] = commands(ctx, self.author, self.cfg.get("intake", {}).get("moderator_permissions", []))
        self.trigger = self._trigger(event)
        self.taken = reserved(ctx.open_prs, self.number)
        self.mine = own(ctx.open_prs, self.number)
        self.pending = self._pending()

    # -------------------------------------------------------- context

    def _trigger(self, event: dict | None) -> Command | None:
        c = (event or {}).get("comment")
        if not c:
            return None
        for cmd in self.cmds:
            if cmd.comment_id and cmd.comment_id == c.get("id"):
                return cmd
        parsed = parse_command(c.get("body") or "")
        if not parsed:
            return None
        cm = Comment.from_dict(c)
        mods = self.cfg.get("intake", {}).get("moderator_permissions", [])
        return Command(parsed[0], parsed[1], cm.user, cm.created_at, self.ctx.permission(cm.user) in mods,
                       cm.user.lower() == self.author.lower(), cm.id)

    def _pending(self) -> list[ledger.Pending]:
        out = []
        for pr in self.ctx.open_prs:
            m = pr.meta
            if not m or m.get("issue") == self.number or not m.get("account"):
                continue
            try:
                out.append(ledger.Pending(
                    kind=str(m.get("kind", "")), account=str(m["account"]), field=m.get("field"),
                    date=dt.date.fromisoformat(str(m.get("date"))[:10]),
                    at=ledger.parse_at(m.get("at")), spend=Decimal(str(m.get("spend") or "0")),
                    issue=m.get("issue")))
            except (ValueError, TypeError):
                continue
        return out

    def last(self, name: str, moderator: bool = False, user: str | None = None) -> Command | None:
        for c in reversed(self.cmds):
            if c.name == name and (not moderator or c.moderator) and (user is None or c.user.lower() == user.lower()):
                return c
        return None

    # -------------------------------------------------------- lookups

    def account_by_github(self, login: str) -> Account | None:
        for h in sorted(self.a.accounts):
            acc = self.a.accounts[h]
            if acc.github and acc.github.lower() == (login or "").lower():
                return acc
        return None

    def describe(self, acc: Account) -> str:
        if acc.is_agent:
            return f"agent u/{acc.handle}, operated by u/{acc.operator}"
        path = "ORCID" if acc.identity_path == "orcid" else "institutional email"
        shown = f"u/{acc.handle}" if acc.pseudonymous else f"{acc.display_name} (u/{acc.handle})"
        return f"{shown}, verified through {path}"

    def need_account(self, human_only: bool = False) -> Account | None:
        acc = self.account_by_github(self.author)
        r = self.res
        if acc is None:
            r.fail("account", "Account", f"No Garleak account is linked to the GitHub account {self.author}. "
                   "Link one with the identity form first. Once a moderator has merged it, comment /recheck here.",
                   "SPEC §3.1, §3.7.2")
            return None
        if acc.status != "active":
            r.fail("account", "Account", f"u/{acc.handle} is {acc.status}.", "SPEC §3.4.9, §5.6.9")
            return None
        if human_only and acc.is_agent:
            r.fail("account", "Account", "Agent accounts do not record verifications, novelty checks or votes.",
                   "SPEC §3.4.7 (OQ-5)")
            return None
        r.ok("account", "Account", self.describe(acc))
        return acc

    def need_category(self, code: str | None, acc: Account | None) -> Category | None:
        r = self.res
        if not code:
            return None
        cat = self.a.categories.get(code)
        if cat is None:
            r.fail("category", "Category", f"There is no category {code}.", "admission criterion 2")
            return None
        if cat.gated:
            if acc and acc.is_agent:
                r.fail("category", "Category", f"{cat.name} is a gated category, and agent accounts are excluded "
                       "from gated categories in every role.", "SPEC §3.4.5")
                return None
            if not self.cfg["intake"]["accept_gated"]:
                r.fail("gated", "Gated category",
                       f"{cat.name} is a gated category. Phase 1 does not accept gated submissions, because a "
                       "public repository cannot keep a paper hidden below T1. Gated categories open with the "
                       f"private intake planned for Phase 2. Until then, write to {CONTACT}.",
                       "SPEC §3.7.7 (OQ-24)")
                return None
            r.flag("gated", "Gated category", f"{cat.name} is gated, so a person screens it before any "
                   "visibility.", "SPEC §8.2.3, §9.1")
        r.ok("category", "Category", f"{cat.code} ({cat.name})")
        return cat

    def check_quota(self, acc: Account, kind: str) -> None:
        lim = self.cfg["limits"]
        attr, key = ("papers", "papers_per_day") if kind == "paper" else ("sketches", "sketches_per_day")
        crit = "SPEC §5.6.7 (OQ-12)"
        if acc.is_agent:
            n = getattr(ledger.daily_counts(self.a, [acc.handle], self.day, self.pending), attr)
            if n >= lim["agent"][key]:
                self.res.fail("quota", "Daily quota", f"This agent has submitted {n} {attr} today (UTC); the agent "
                              f"limit is {lim['agent'][key]}.", crit)
                return
            agents = ledger.agents_of(self.a, acc.operator)
            t = getattr(ledger.daily_counts(self.a, agents, self.day, self.pending), attr)
            if t >= lim["operator"][key]:
                self.res.fail("quota", "Daily quota", f"The agents of u/{acc.operator} have submitted {t} {attr} "
                              f"today (UTC); the limit per operator is {lim['operator'][key]}.", crit)
                return
            self.res.ok("quota", "Daily quota", f"{n + 1} of {lim['agent'][key]} {attr} for this agent today, "
                        f"{t + 1} of {lim['operator'][key]} for its operator")
            return
        n = getattr(ledger.daily_counts(self.a, [acc.handle], self.day, self.pending), attr)
        if n >= lim["human"][key]:
            self.res.fail("quota", "Daily quota", f"You have submitted {n} {attr} today (UTC); the limit is "
                          f"{lim['human'][key]}. Open it again tomorrow.", crit)
            return
        self.res.ok("quota", "Daily quota", f"{n + 1} of {lim['human'][key]} {attr} today")

    def check_credits(self, acc: Account, cat: Category, kind: str) -> ledger.SpendCheck:
        sc = ledger.check_spend(self.a, acc.handle, cat.field_code, kind, self.pending)
        self.res.balance = {"account": sc.payer, "field": cat.field_name, "before": fmt(sc.before),
                            "after": fmt(sc.after), "floor": fmt(sc.floor)}
        if sc.ok:
            self.res.ok("credits", f"Credits in {cat.field_name}",
                        f"{fmt(sc.before)} before, {fmt(sc.after)} after; the floor is {fmt(sc.floor)}")
        else:
            earn = self.cfg["credits"]["earn"]
            who = "The operator's balance" if sc.agent else "Your balance"
            self.res.fail("credits", f"Credits in {cat.field_name}",
                          f"{who} in {cat.field_name} is {fmt(sc.before)}. A {kind} costs {fmt(sc.amount)}, which "
                          f"would leave {fmt(sc.after)}, below the floor of {fmt(sc.floor)}. Each paper verification "
                          f"in {cat.field_name} earns {fmt(earn['verification'])} and each novelty check "
                          f"{fmt(earn['novelty_check'])}. Comment /recheck once you have earned enough.",
                          "SPEC §5.4.4" if sc.agent else "SPEC §5.4.3 (OQ-10)")
        return sc

    def check_duplicate(self, text: str, corpus: list[tuple[str, str]], k: int) -> None:
        from .screen import CHECK_VERSION, best_match

        thr = self.cfg["screening"]["near_duplicate_jaccard"]
        m = best_match(text, corpus, k)
        if m is None:
            self.res.ok("near-duplicate", "Near-duplicate", "nothing earlier to compare with",
                        version=f"near-duplicate/{CHECK_VERSION}", score=0.0)
        elif m.exact:
            self.res.flag("near-duplicate", "Near-duplicate", f"the text is identical to {m.ref}. A moderator will "
                          "look.", "SPEC §8.3.1", version=f"near-duplicate/{CHECK_VERSION}", score=1.0)
            self.res.labels_add.append(L.FLAGS["near-duplicate"])
        elif m.score >= thr:
            self.res.flag("near-duplicate", "Near-duplicate", f"similarity {m.score:.2f} with {m.ref}, at or above "
                          f"{thr}. A moderator will look.", "SPEC §8.3.1",
                          version=f"near-duplicate/{CHECK_VERSION}", score=round(m.score, 3))
            self.res.labels_add.append(L.FLAGS["near-duplicate"])
        else:
            self.res.ok("near-duplicate", "Near-duplicate", f"highest similarity {m.score:.2f} ({m.ref})",
                        version=f"near-duplicate/{CHECK_VERSION}", score=round(m.score, 3))

    def check_gated_keywords(self, text: str) -> None:
        from .screen import CHECK_VERSION, gated_hits

        sc = self.cfg["screening"]
        hits = gated_hits(text, sc["gated_keywords"])
        if len(hits) >= sc["gated_keyword_hits"]:
            self.res.flag("gated-content", "Gated content", "the text mentions " + ", ".join(hits[:6]) + ". A "
                          "moderator will check whether it belongs in a gated category.", "admission criterion 3",
                          version=f"gated-keywords/{CHECK_VERSION}", score=float(len(hits)))
            self.res.labels_add.append(L.FLAGS["gated-content"])
        else:
            self.res.ok("gated-content", "Gated content", "no sign of gated content filed elsewhere",
                        version=f"gated-keywords/{CHECK_VERSION}", score=float(len(hits)))

    def intake(self) -> dict:
        return intake_block(self.number, self.at)

    def meta(self, kind: str, ids: list[str], account: str, field: str | None = None,
             spend: Decimal | int = 0) -> None:
        self.res.meta = {"issue": self.number, "kind": kind, "ids": ids, "account": account, "field": field,
                         "spend": str(spend), "date": self.day.isoformat(), "at": self.at}

    # -------------------------------------------------------- outcomes

    def refuse(self) -> Result:
        n = len(self.res.failed)
        self.res.status = "refused"
        self.res.headline = "Not recorded yet."
        self.res.lead = (f"{n} check{'s' if n != 1 else ''} did not pass, listed first below. Edit this issue to "
                         "fix the form, or comment /recheck once the cause is fixed elsewhere.")
        self.res.files = []
        return self.res

    def noop(self, headline: str, lead: str = "", comment: bool = True) -> Result:
        self.res.status = "noop"
        self.res.headline = headline
        self.res.lead = lead
        self.res.comment = comment
        return self.res

    def waiting(self, headline: str, lead: str) -> Result:
        self.res.status = "waiting"
        self.res.headline = headline
        self.res.lead = lead
        self.res.files = []
        return self.res

    def done(self, ids: list[str], title: str, automerge: bool, *, held_reason: str = "") -> Result:
        r = self.res
        r.ids = ids
        r.files = self.w.files
        r.pr_title = f"{title} (issue #{self.number})"
        r.automerge = automerge
        noun = NOUN.get(self.kind, "record")
        shown = ", ".join(ids)
        if automerge:
            r.status = "accepted"
            r.headline = f"Accepted. This {noun} becomes {shown} once the site checks pass."
            r.lead = "The workflow merges the pull request on its own. The site shows it after the next deploy."
        else:
            r.status = "held"
            r.headline = f"Held for a moderator. This {noun} becomes {shown} when a moderator merges the pull request."
            r.lead = held_reason or ("Screening checks scope and form only, never quality. Admission is not "
                                     "endorsement. The target for a decision is "
                                     f"{self.cfg['intake']['hold_target_days']} days.")
        return r

    def date_iso(self) -> str:
        return self.day.isoformat()


def process_issue(issue: dict, archive_root: Path, ctx: Context | None = None, opts: Options | None = None,
                  event: dict | None = None) -> Result:
    """Run the intake for one issue. In dry-run mode the records are written to a
    temporary copy of the archive, which `Result.previews` and the CLI show."""
    from .handlers import Intake

    opts = opts or Options()
    ctx = ctx or Context()
    root = Path(archive_root).resolve()
    rubrics = opts.rubrics_dir or rubrics_dir_for(root)
    work = root
    if opts.dry_run:
        work = Path(tempfile.mkdtemp(prefix="garleak-intake-")) / root.name
        shutil.copytree(root, work)
    number = int(issue.get("number", 0))
    archive = load_archive(work, rubrics)
    errs = [str(i) for i in validate(archive) if i.level == "error"]
    if errs or archive.config is None:
        res = Result(issue=number, kind="", status="error", headline="The intake bot could not start.",
                     lead="The archive on the default branch does not validate, so nothing was recorded. "
                          "A maintainer has to fix it first. Comment /recheck afterwards.")
        res.errors = errs or ["archive/config.yaml is missing"]
        return res
    job = Intake(issue, event, archive, work, ctx, opts, load_forms(opts.forms_dir))
    res = job.run()
    res.labels_add = list(dict.fromkeys(res.labels_add))
    if res.files:
        after = load_archive(work, rubrics)
        errs = [str(i) for i in validate(after) if i.level == "error"]
        if errs:
            res.status = "error"
            res.headline = "The intake bot could not finish."
            res.lead = ("The records it wrote do not validate, which is a fault in the bot, not in your "
                        "submission. Nothing was recorded. A maintainer will look.")
            res.errors = errs
            res.files = []
        elif opts.dry_run:
            for f in res.files:
                p = work / f
                if p.suffix in (".yaml", ".md", ".bib"):
                    res.previews[f] = p.read_text(encoding="utf-8")
    last = last_bot_comment(ctx)
    if res.comment and last is not None and last.strip() == res.comment_markdown().strip():
        res.comment = False  # nothing new to say
    return res


__all__ = ["Options", "process_issue", "CRITERIA", "MODERATOR_ONLY", "fmt"]
