# SPDX-License-Identifier: AGPL-3.0-or-later
"""Credits, loops, standing and rate counters, derived from the public records.

Nothing here is stored. Every credit event follows from a record in the repository, so
anyone can recompute any account's balance in any field (SPEC §5.2.4). In Phase 1 that
makes the ledger public by design (SPEC §3.7.5): §5.2.6 asks for a private ledger, and a
public repository cannot give one. The amounts, the floor, the loop window and the
standing formula come from the archive's config.yaml (SPEC §10.4), never from this code.

    events(archive)            the credit events, earn, spend and reversal (SPEC §5.2 to §5.4)
    balance(...)               the sum of one account's events in one field
    check_spend(...)           whether a submission keeps the payer at or above the floor
    loop_labels(archive)       reciprocal loops in the verification graph (SPEC §5.6)
    standing(...)              verifier standing in a field (SPEC §4.6, OQ-8)
    daily_counts(...)          counters for the quotas and rate limits (SPEC §5.6.6, §5.6.7)
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import Archive, NoveltyCheck, Verification
from .stages import contributors

EARN_KINDS = ("earn_verification", "earn_novelty", "earn_fix", "earn_moderation", "earn_promotion")
SPEND_KINDS = ("spend_paper", "spend_scratch")


class LedgerError(RuntimeError):
    pass


def require_config(archive: Archive) -> dict:
    if archive.config is None:
        raise LedgerError(f"{archive.root} has no config.yaml, so it has no ledger (SPEC §10.4)")
    return archive.config


def dec(x) -> Decimal:
    return Decimal(str(x))


def responsible(archive: Archive, handle: str) -> str:
    """The accountable human for an account: an agent's operator, otherwise the account."""
    a = archive.accounts.get(handle)
    return a.operator if a and a.is_agent and a.operator else handle


def is_human(archive: Archive, handle: str) -> bool:
    a = archive.accounts.get(handle)
    return bool(a and not a.is_agent)


# ---------------------------------------------------------------- credit events


@dataclass(frozen=True)
class CreditEvent:
    """One entry of the ledger (SPEC §11.13). Derived, never stored."""

    id: str
    account: str
    field: str
    amount: Decimal
    kind: str
    ref: str
    date: dt.date
    reverses: str | None = None
    reason: str = ""
    config_version: str = ""


@dataclass(frozen=True)
class Pending:
    """A submission or record in an open pull request that is not merged yet. The intake
    check counts it so that several open requests cannot overdraw a balance or a quota."""

    kind: str  # paper | scratch | version | verification | novelty | claim | contest | vote | identity
    account: str
    field: str | None
    date: dt.date
    at: dt.datetime | None = None
    spend: Decimal = Decimal(0)
    issue: int | None = None


def _criterion(block: dict | None) -> int | None:
    if not block:
        return None
    text = str(block.get("criterion", "")).strip()
    digits = "".join(ch for ch in text.split()[-1] if ch.isdigit()) if text else ""
    return int(digits) if digits else None


def _status_date(v, fallback: dt.date) -> dt.date:
    hist = getattr(v, "status_history", None) or []
    for h in reversed(hist):
        if h.status == v.status:
            return h.date
    return fallback


def events(archive: Archive, pending: Iterable[Pending] = ()) -> list[CreditEvent]:
    cfg = require_config(archive)
    cv = str(cfg["config_version"])
    credits = cfg["credits"]
    earn = {k: dec(v) for k, v in credits["earn"].items()}
    spend = {k: dec(v) for k, v in credits["spend"].items()}
    no_refund = set(int(x) for x in credits["no_refund_criteria"])
    labels = loop_labels(archive)
    out: list[CreditEvent] = []

    def add(kind, account, field, amount, ref, date, reverses=None, reason=""):
        out.append(CreditEvent(f"{kind}:{ref}:{account}", account, field, dec(amount), kind, ref, date,
                               reverses, reason, cv))

    def reverse(ev_kind, account, field, amount, ref, date, reason):
        add("reversal", account, field, -dec(amount), ref, date, f"{ev_kind}:{ref}:{account}", reason)

    for p in archive.papers.values():
        fld = archive.field_of(p.category)
        if fld is None:
            continue
        ref = f"paper:{p.number}"
        who = responsible(archive, p.submitter)
        add("spend_paper", who, fld, -spend["paper"], ref, p.created)
        crit = _criterion(p.removal)
        if p.status == "removed" and crit not in no_refund:
            when = dt.date.fromisoformat(str(p.removal["date"])[:10]) if p.removal else p.created
            reverse("spend_paper", who, fld, -spend["paper"], ref, when,
                    f"removed under criterion {crit}, refunded (§5.4.5)")
        if p.promoted_from:
            try:
                n = int(p.promoted_from.split(":", 1)[1].split("v", 1)[0])
            except (IndexError, ValueError):
                n = None
            s = archive.scratches.get(n) if n else None
            if s and is_human(archive, s.author):
                add("earn_promotion", s.author, fld, earn["promotion"], ref, p.created)
                if p.status == "removed":
                    reverse("earn_promotion", s.author, fld, earn["promotion"], ref, p.created,
                            "the promoted paper was removed")
        for v in p.verifications:
            if not is_human(archive, v.verifier):
                continue  # agents record no verifications and earn nothing (§3.4.7, §5.3.5)
            vref = f"verification:{v.id}"
            add("earn_verification", v.verifier, fld, earn["verification"], vref, v.date)
            label = v.loop_label or (labels[vref].as_record() if vref in labels else None)
            if label:
                reverse("earn_verification", v.verifier, fld, earn["verification"], vref, v.date,
                        f"reciprocal loop of length {label['length']}, earns nothing (§5.6.3)")
            elif v.status in ("withdrawn", "void"):
                reverse("earn_verification", v.verifier, fld, earn["verification"], vref,
                        _status_date(v, v.date), f"verification {v.status} (§4.2.10, §5.3.5)")
        for fx in p.fixes:
            if fx.status != "merged" or fx.merged_into is None:
                continue
            ver = p.version(fx.merged_into)
            if ver is None or not is_human(archive, fx.author):
                continue
            if responsible(archive, ver.submitted_by) == fx.author:
                continue  # merged by its own author (§5.3.5)
            fref = f"fix:{p.number}-{fx.id}"
            add("earn_fix", fx.author, fld, earn["merged_fix"], fref, ver.date)
            if fref in labels:
                reverse("earn_fix", fx.author, fld, earn["merged_fix"], fref, ver.date,
                        f"reciprocal loop of length {labels[fref].length}, earns nothing (§5.6.3)")

    for s in archive.scratches.values():
        fld = archive.field_of(s.category)
        if fld is None:
            continue
        ref = f"scratch:{s.number}"
        who = responsible(archive, s.author)
        add("spend_scratch", who, fld, -spend["scratch"], ref, s.date)
        crit = _criterion(s.removal)
        if s.status == "removed" and crit not in no_refund:
            when = dt.date.fromisoformat(str(s.removal["date"])[:10]) if s.removal else s.date
            reverse("spend_scratch", who, fld, -spend["scratch"], ref, when,
                    f"removed under criterion {crit}, refunded (§5.4.5)")
        for ch in s.checks:
            if not is_human(archive, ch.checker):
                continue
            cref = f"novelty:{ch.id}"
            add("earn_novelty", ch.checker, fld, earn["novelty_check"], cref, ch.date)
            label = ch.loop_label or (labels[cref].as_record() if cref in labels else None)
            if label:
                reverse("earn_novelty", ch.checker, fld, earn["novelty_check"], cref, ch.date,
                        f"reciprocal loop of length {label['length']}, earns nothing (§5.6.3)")
            elif ch.status in ("withdrawn", "void"):
                reverse("earn_novelty", ch.checker, fld, earn["novelty_check"], cref, ch.date,
                        f"novelty check {ch.status} (§5.3.5)")

    for r in archive.screening:
        fld = archive.field_of(r.category)
        if fld is None:
            continue
        if r.decision == "reject" and r.criterion in no_refund and r.object in spend:
            add(f"spend_{r.object}", responsible(archive, r.submitter), fld, -spend[r.object],
                f"screening:{r.id}", r.date, reason=f"rejected under criterion {r.criterion}, not refunded (§5.4.5)")
        if r.moderator and is_human(archive, r.moderator):
            # Restricted in SPEC §11.15, so the Phase 1 schema never carries it. Kept so that
            # moderation credit (§5.3.4) works once the record can hold the moderator.
            add("earn_moderation", r.moderator, fld, earn["moderation"], f"screening:{r.id}", r.date)

    for i, pd in enumerate(pending):
        if pd.spend and pd.field and pd.kind in ("paper", "scratch"):
            add(f"spend_{pd.kind}", responsible(archive, pd.account), pd.field, -pd.spend,
                f"pending:{pd.issue or i}", pd.date, reason="open pull request, not merged yet")
    return out


def balances(evts: Iterable[CreditEvent]) -> dict[tuple[str, str], Decimal]:
    out: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for e in evts:
        out[(e.account, e.field)] += e.amount
    return dict(out)


def balance(archive: Archive, account: str, field: str, pending: Iterable[Pending] = ()) -> Decimal:
    return sum((e.amount for e in events(archive, pending) if e.account == account and e.field == field), Decimal(0))


@dataclass(frozen=True)
class SpendCheck:
    payer: str
    field: str
    amount: Decimal
    before: Decimal
    after: Decimal
    floor: Decimal
    agent: bool

    @property
    def ok(self) -> bool:
        return self.after >= self.floor


def check_spend(archive: Archive, submitter: str, field: str, object_kind: str,
                pending: Iterable[Pending] = ()) -> SpendCheck:
    """SPEC §5.4.3 and §5.4.4. A human may go down to the balance floor; an agent's
    submission spends from its operator, who may not overdraw."""
    cfg = require_config(archive)
    acc = archive.accounts.get(submitter)
    agent = bool(acc and acc.is_agent)
    who = responsible(archive, submitter)
    amount = dec(cfg["credits"]["spend"][object_kind])
    before = balance(archive, who, field, pending)
    floor = dec(cfg["credits"]["agent_balance_floor"] if agent else cfg["credits"]["balance_floor"])
    return SpendCheck(who, field, amount, before, before - amount, floor, agent)


# ---------------------------------------------------------------- loops (§5.6)


@dataclass(frozen=True)
class Action:
    """One edge of the verification graph (SPEC §5.6.1): from the account that acted to an
    account it acted on, with the date of the action."""

    ref: str  # verification:<id> | novelty:<id> | fix:<paper>-<id>
    frm: str
    to: str
    at: dt.date


@dataclass(frozen=True)
class LoopLabel:
    length: int
    detected: dt.date

    def as_record(self) -> dict:
        return {"length": self.length, "detected": self.detected.isoformat()}


def graph_actions(archive: Archive) -> list[Action]:
    """Edges run from a verifier or novelty checker to every human contributor of what they
    checked (an agent counts as its operator, §3.6.4), and from the account that merged a
    fix to the fix's author."""
    acts: list[Action] = []
    for p in archive.papers.values():
        for v in p.verifications:
            ver = p.version(v.version)
            if ver is None:
                continue
            frm = responsible(archive, v.verifier)
            targets = {responsible(archive, h) for h in contributors(p, ver)}
            for t in sorted(targets - {frm}):
                acts.append(Action(f"verification:{v.id}", frm, t, v.date))
        for fx in p.fixes:
            if fx.status != "merged" or fx.merged_into is None:
                continue
            ver = p.version(fx.merged_into)
            if ver is None:
                continue
            merger, author = responsible(archive, ver.submitted_by), responsible(archive, fx.author)
            if merger != author:
                acts.append(Action(f"fix:{p.number}-{fx.id}", merger, author, ver.date))
    for s in archive.scratches.values():
        author = responsible(archive, s.author)
        for ch in s.checks:
            frm = responsible(archive, ch.checker)
            if frm != author:
                acts.append(Action(f"novelty:{ch.id}", frm, author, ch.date))
    return acts


def detect_loops(actions: Iterable[Action], window_days: int, min_length: int = 2,
                 max_length: int = 4) -> dict[str, LoopLabel]:
    """Label every action that lies on a directed cycle of min_length to max_length distinct
    accounts whose edges were all made within window_days of each other (SPEC §5.6.2).

    Deterministic: cycles are enumerated from their smallest account, in sorted order, and
    each action keeps its shortest loop (then the earliest date that loop closed)."""
    by_pair: dict[tuple[str, str], list[Action]] = defaultdict(list)
    adj: dict[str, set[str]] = defaultdict(set)
    for a in actions:
        by_pair[(a.frm, a.to)].append(a)
        adj[a.frm].add(a.to)
    for lst in by_pair.values():
        lst.sort(key=lambda a: (a.at, a.ref))
    window = dt.timedelta(days=window_days)

    cycles: list[list[str]] = []

    def walk(start: str, node: str, path: list[str]) -> None:
        for nxt in sorted(adj.get(node, ())):
            if nxt == start and len(path) >= min_length:
                cycles.append(list(path))
            elif nxt != start and nxt > start and nxt not in path and len(path) < max_length:
                walk(start, nxt, path + [nxt])

    for s in sorted(adj):
        walk(s, s, [s])

    labels: dict[str, LoopLabel] = {}
    for cyc in cycles:
        k = len(cyc)
        lists = [by_pair[(cyc[i], cyc[(i + 1) % k])] for i in range(k)]
        for i, lst in enumerate(lists):
            for a in lst:
                closed = _closes(a.at, lists, i, window)
                if closed is None:
                    continue
                cand = LoopLabel(k, closed)
                old = labels.get(a.ref)
                if old is None or (cand.length, cand.detected) < (old.length, old.detected):
                    labels[a.ref] = cand
    return labels


def _closes(at: dt.date, lists: list[list[Action]], i: int, window: dt.timedelta) -> dt.date | None:
    """If some window of the given width contains `at` and one action from every other edge
    of the cycle, return the date the loop closed in the earliest such window."""
    starts = sorted({x.at for lst in lists for x in lst if at - window <= x.at <= at})
    for s in starts:
        end = s + window
        if at > end:
            continue
        firsts = []
        for j, lst in enumerate(lists):
            if j == i:
                continue
            inside = [x.at for x in lst if s <= x.at <= end]
            if not inside:
                break
            firsts.append(min(inside))
        else:
            return max([at] + firsts)
    return None


def loop_labels(archive: Archive) -> dict[str, LoopLabel]:
    cfg = require_config(archive)["loops"]
    return detect_loops(graph_actions(archive), int(cfg["window_days"]), int(cfg["min_length"]),
                        int(cfg["max_length"]))


def apply_loop_labels(archive: Archive) -> dict[str, LoopLabel]:
    """Set the derived label on every verification and novelty check on a loop, unless a
    label was already stored by hand. Loop-labeled verifications still count toward T1 to
    T3 with the label shown, and never toward T4, graduation or standing (§5.6.4)."""
    labels = loop_labels(archive)
    for p in archive.papers.values():
        for v in p.verifications:
            lab = labels.get(f"verification:{v.id}")
            if lab and v.loop_label is None:
                v.loop_label = lab.as_record()
    for s in archive.scratches.values():
        for ch in s.checks:
            lab = labels.get(f"novelty:{ch.id}")
            if lab and ch.loop_label is None:
                ch.loop_label = lab.as_record()
    return labels


# ---------------------------------------------------------------- standing (§4.6)


def _overturned(rec: Verification | NoveltyCheck) -> bool:
    return rec.status == "overturned" or any(h.status == "overturned" for h in getattr(rec, "status_history", []))


def standing(archive: Archive, handle: str, field: str, today: dt.date) -> int | float:
    """OQ-8: S minus overturn_weight times O. S counts the account's verifications and
    novelty checks in the field that have been active for at least age_days and never
    overturned, leaving out loop-labeled ones. O counts overturned ones."""
    cfg = require_config(archive)["standing"]
    age = dt.timedelta(days=int(cfg["age_days"]))
    s = o = 0
    for p in archive.papers.values():
        if archive.field_of(p.category) != field:
            continue
        for v in p.verifications:
            if v.verifier != handle:
                continue
            if _overturned(v):
                o += 1
            elif v.status == "active" and not v.loop_label and today - v.date >= age:
                s += 1
    for sc in archive.scratches.values():
        if archive.field_of(sc.category) != field:
            continue
        for ch in sc.checks:
            if ch.checker != handle:
                continue
            if _overturned(ch):
                o += 1
            elif ch.status == "active" and not ch.loop_label and today - ch.date >= age:
                s += 1
    value = dec(s) - dec(cfg["overturn_weight"]) * o
    return int(value) if value == value.to_integral_value() else float(value)


def has_field_standing(archive: Archive, handle: str, field: str, today: dt.date) -> bool:
    return standing(archive, handle, field, today) >= require_config(archive)["standing"]["field_standing_min"]


# ---------------------------------------------------------------- counters (§5.6.6, §5.6.7)


@dataclass
class Counts:
    papers: int = 0
    scratches: int = 0
    verifications: int = 0
    novelty_checks: int = 0


def daily_counts(archive: Archive, handles: Iterable[str], day: dt.date,
                 pending: Iterable[Pending] = ()) -> Counts:
    """How many papers and scratches the accounts submitted, and how many verifications
    and novelty checks they recorded, on one UTC day. Rejections that keep their charge
    count as submissions, and so do open pull requests."""
    hs = set(handles)
    c = Counts()
    for p in archive.papers.values():
        if p.submitter in hs and p.created == day:
            c.papers += 1
        c.verifications += sum(1 for v in p.verifications if v.verifier in hs and v.date == day)
    for s in archive.scratches.values():
        if s.author in hs and s.date == day:
            c.scratches += 1
        c.novelty_checks += sum(1 for ch in s.checks if ch.checker in hs and ch.date == day)
    for r in archive.screening:
        if r.submitter in hs and r.date == day:
            if r.object == "paper":
                c.papers += 1
            else:
                c.scratches += 1
    for pd in pending:
        if pd.account in hs and pd.date == day:
            if pd.kind == "paper":
                c.papers += 1
            elif pd.kind == "scratch":
                c.scratches += 1
            elif pd.kind == "verification":
                c.verifications += 1
            elif pd.kind == "novelty":
                c.novelty_checks += 1
    return c


def agents_of(archive: Archive, operator: str) -> list[str]:
    return sorted(h for h, a in archive.accounts.items() if a.is_agent and a.operator == operator)


def parse_at(value) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def recent_records(archive: Archive, handle: str, now: dt.datetime, minutes: int,
                   pending: Iterable[Pending] = ()) -> int:
    """Verifications and novelty checks the account recorded in the `minutes` before `now`,
    by the time each arrived (`intake.at`). Records without a time are not counted."""
    start = now - dt.timedelta(minutes=minutes)
    n = 0
    stamps = []
    for p in archive.papers.values():
        stamps += [parse_at((v.intake or {}).get("at")) for v in p.verifications if v.verifier == handle]
    for s in archive.scratches.values():
        stamps += [parse_at((ch.intake or {}).get("at")) for ch in s.checks if ch.checker == handle]
    stamps += [pd.at for pd in pending if pd.account == handle and pd.kind in ("verification", "novelty")]
    for t in stamps:
        if t is not None and start < t <= now:
            n += 1
    return n
