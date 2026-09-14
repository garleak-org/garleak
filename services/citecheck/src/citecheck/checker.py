# SPDX-License-Identifier: AGPL-3.0-or-later
"""The decision procedure: from a parsed reference and resolver answers to a verdict.

Order of work for one reference:
  1. Identifiers first. Each printed DOI / arXiv ID / bibcode is looked up and the
     returned record is compared with the reference. A DOI missing from Crossref is
     then tried in the global DOI handle system (other registries), then as a PoS
     contribution, then with conservative repairs (URL tails, doubled letters).
  2. If an identifier failed or pointed at a different work, or if there was none,
     the reference is searched by metadata (ADS, Crossref, OpenAlex, arXiv).
  3. A verdict is chosen. 'unresolved' is used only when nothing matching was found
     after all of the above, and it is never called fabrication.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .ids import arxiv_from_doi, doi_repairs, pos_from_doi, pos_from_url
from .match import MatchScores, compare
from .models import Evidence, Record, RefResult, Reference, Verdict
from .parsers.freetext import LOW_COVERAGE_FLAGS, NO_SEARCH_FLAGS
from .resolvers.base import Lookup, Resolver
from .textutil import content_tokens

_STRENGTH_RANK = {"strong": 3, "moderate": 2, "weak": 1, "none": 0}
_KIND_NAMES = {"doi": "DOI", "arxiv": "arXiv", "bibcode": "bibcode", "pos": "PoS"}


def _k(kind: str) -> str:
    return _KIND_NAMES.get(kind, kind)
_INCOMPLETE = ("error", "offline_miss")


@dataclass
class IdOutcome:
    kind: str
    value: str
    state: str  # agree | uncertain | mismatch | missing | exists_nometa | error
    record: Record | None = None
    scores: MatchScores | None = None
    repaired_to: str | None = None
    repair_note: str | None = None
    note: str | None = None


def _rank(s: MatchScores) -> tuple:
    return (s.agrees, _STRENGTH_RANK[s.strength], not s.contradicts, s.overall)


def _conf_from_scores(s: MatchScores) -> float:
    base = {"strong": 0.9, "moderate": 0.75, "weak": 0.6, "none": 0.45}[s.strength]
    return max(0.3, min(0.99, base + 0.1 * (s.overall - 0.8) + 0.05 * (s.coverage - 0.6)))


def searchable(ref: Reference) -> bool:
    n_title = len(content_tokens(ref.title)) if ref.title else 0
    if n_title >= 3 or (n_title >= 2 and (ref.authors or ref.collaboration) and ref.year):
        return True
    if ref.authors and ref.year and (ref.journal or (ref.volume and ref.page)):
        return True
    if ref.collaboration and ref.year and (ref.journal or ref.volume):
        return True
    return bool(ref.bibcode_hint)


class Checker:
    def __init__(self, resolvers: dict[str, Resolver], arxiv_search: bool = True,
                 progress: Callable[[int, int, Reference], None] | None = None):
        self.res = resolvers
        self.arxiv_search = arxiv_search
        self.progress = progress

    # ------------------------------------------------------------ public

    def check_all(self, refs: list[Reference]) -> list[RefResult]:
        arx = [r.arxiv for r in refs if r.arxiv]
        dois = [r.doi for r in refs if r.doi and not pos_from_doi(r.doi) and not arxiv_from_doi(r.doi)]
        if "arxiv" in self.res and arx:
            self.res["arxiv"].prefetch("arxiv", arx)
        if "crossref" in self.res and dois:
            self.res["crossref"].prefetch("doi", dois)
        out = []
        for i, r in enumerate(refs):
            if self.progress:
                self.progress(i + 1, len(refs), r)
            out.append(self.check(r))
        return out

    def check(self, ref: Reference) -> RefResult:
        ev: list[Evidence] = []
        flags = set(ref.flags)

        if not ref.has_identifier() and flags & NO_SEARCH_FLAGS:
            kind = sorted(flags & NO_SEARCH_FLAGS)[0].replace("_", " ")
            return RefResult(ref, Verdict.NOT_CHECKABLE, 0.9,
                             f"Cited as {kind}; there is no public record to check.", evidence=ev)

        outcomes: list[IdOutcome] = []
        if ref.doi:
            outcomes.append(self._check_doi(ref, ref.doi, ev))
        if ref.arxiv:
            outcomes.append(self._check_arxiv(ref, ev))
        # ADS bibcodes (usually from an adsurl hyperlink, not printed text) are unstable: preprint
        # bibcodes become alternates and '.tmp.' in-press bibcodes are replaced. Check them only
        # when nothing better is printed, and never hold a stale one against the reference.
        if ref.bibcode and "ads" in self.res and ".tmp." not in ref.bibcode and not (ref.doi or ref.arxiv):
            outcomes.append(self._check_bibcode(ref, ev))
        if not ref.doi and "pos" in flags and "pos" in self.res and pos_from_url(ref.url):
            outcomes.append(self._check_pos(ref, "/".join(pos_from_url(ref.url)), ev, printed="url"))

        good = [o for o in outcomes if o.state in ("agree", "uncertain", "exists_nometa")]
        bad = [o for o in outcomes if o.state in ("missing", "mismatch")]
        repaired = [o for o in outcomes if o.state == "repaired"]
        errors = [o for o in outcomes if o.state == "error"]

        # all printed identifiers check out
        if outcomes and good and not bad and not repaired and not errors:
            best = self._best_outcome(good)
            if best.state == "exists_nometa":
                return RefResult(ref, Verdict.VERIFIED, 0.55,
                                 f"{_k(best.kind)} {best.value} is registered"
                                 f"{' with ' + best.record.registry if best.record and best.record.registry else ''},"
                                 " but the registry returned no metadata to compare.",
                                 matched_record=best.record, evidence=ev)
            if best.state == "uncertain":
                return RefResult(ref, Verdict.VERIFIED, 0.5,
                                 f"{_k(best.kind)} {best.value} resolves. Too little of the reference could be "
                                 "parsed to compare metadata, and nothing disagrees.",
                                 matched_record=best.record, scores=best.scores.to_dict() if best.scores else None,
                                 evidence=ev)
            conf = _conf_from_scores(best.scores)
            if len(good) > 1:
                conf = min(0.99, conf + 0.05)
            ids_txt = " and ".join(f"{_k(o.kind)} {o.value}" for o in good)
            return RefResult(ref, Verdict.VERIFIED, conf, f"{ids_txt} resolve{'s' if len(good) == 1 else ''} and "
                             "the metadata agree.", matched_record=best.record, scores=best.scores.to_dict(),
                             evidence=ev)

        # a repaired identifier (typo) resolves to the right work
        if repaired and not bad:
            o = repaired[0]
            corrected = {"doi": o.repaired_to} if o.kind == "doi" else {o.kind: o.repaired_to}
            if o.kind == "pos":
                corrected = {"url": o.repaired_to}
            return RefResult(ref, Verdict.ID_MISMATCH_REAL_REF, _conf_from_scores(o.scores),
                             o.repair_note or "The identifier as printed does not resolve; a corrected form does.",
                             corrected_ids=corrected, matched_record=o.record, scores=o.scores.to_dict(), evidence=ev)

        # one identifier is good and another is bad: the work is real, an identifier is wrong
        if good and (bad or repaired):
            best = self._best_outcome(good)
            corrected = self._corrections_from(best, bad + repaired, ref, ev)
            wrong = ", ".join(f"{_k(o.kind)} {o.value} ({'does not resolve' if o.state == 'missing' else 'points to a different work'})"
                              for o in bad)
            reason = (f"The work is real ({_k(best.kind)} {best.value} resolves and agrees), but {wrong}."
                      if wrong else f"The work is real; {repaired[0].repair_note}")
            if corrected:
                reason += " Suggested correction: " + ", ".join(f"{k} {v}" for k, v in corrected.items()) + "."
            conf = _conf_from_scores(best.scores) if best.scores else 0.6
            return RefResult(ref, Verdict.ID_MISMATCH_REAL_REF, conf, reason, corrected_ids=corrected,
                             matched_record=best.record, scores=best.scores.to_dict() if best.scores else None,
                             evidence=ev)

        # no identifier agreed: search by metadata
        found, search_incomplete = self._search(ref, ev)
        incomplete = bool(errors) or search_incomplete
        if found is not None:
            rec, s = found
            wrong_ids = [o for o in outcomes if o.state in ("missing", "mismatch", "error")]
            # If the independently found record carries the very identifier that was printed, the
            # identifier is right and the earlier comparison was thrown off by parsing noise.
            same = [o for o in wrong_ids if o.kind != "pos" and rec.ids.get(o.kind, "").lower() == o.value.lower()]
            if same and len(same) == len(wrong_ids):
                return RefResult(ref, Verdict.VERIFIED, _conf_from_scores(s) - 0.05,
                                 f"{_k(same[0].kind)} {same[0].value} belongs to the record found by metadata "
                                 f"search ({rec.source}), and the metadata agree.",
                                 matched_record=rec, scores=s.to_dict(), evidence=ev, incomplete=incomplete)
            if wrong_ids:
                corrected = {}
                for o in wrong_ids:
                    v = rec.ids.get(o.kind) if o.kind != "pos" else rec.ids.get("url")
                    if v and v.lower() != o.value.lower():
                        corrected[o.kind] = v
                if not corrected and rec.ids.get("doi") and not ref.doi:
                    corrected["doi"] = rec.ids["doi"]
                desc = "; ".join(
                    f"{_k(o.kind)} {o.value} "
                    + {"missing": "does not resolve in any registry consulted",
                       "mismatch": "resolves to a different work",
                       "error": "could not be checked (resolver error)"}[o.state]
                    for o in wrong_ids)
                if all(o.state == "error" for o in wrong_ids):
                    return RefResult(ref, Verdict.VERIFIED, max(0.4, _conf_from_scores(s) - 0.2),
                                     f"{desc}, but a matching record was found by metadata search.",
                                     matched_record=rec, scores=s.to_dict(), evidence=ev, incomplete=True)
                reason = f"{desc}. A matching real work was found by metadata search ({rec.source})."
                if corrected:
                    reason += " Suggested correction: " + ", ".join(f"{k} {v}" for k, v in corrected.items()) + "."
                return RefResult(ref, Verdict.ID_MISMATCH_REAL_REF, _conf_from_scores(s), reason,
                                 corrected_ids=corrected, matched_record=rec, scores=s.to_dict(), evidence=ev,
                                 incomplete=incomplete)
            lead = "No identifier printed; matched" if not outcomes else "Matched"
            return RefResult(ref, Verdict.VERIFIED, _conf_from_scores(s) - 0.05,
                             f"{lead} by metadata search ({rec.source}).",
                             matched_record=rec, scores=s.to_dict(), evidence=ev, incomplete=incomplete)

        mism = [o for o in outcomes if o.state == "mismatch"]
        if mism:
            o = mism[0]
            what = self._disagreement_text(o.scores)
            return RefResult(ref, Verdict.METADATA_MISMATCH, 0.7 if o.scores and o.scores.contradicts else 0.5,
                             f"{_k(o.kind)} {o.value} resolves to a record whose {what} disagree with the "
                             "reference, and no better match was found. The reference or the identifier is wrong.",
                             matched_record=o.record, scores=o.scores.to_dict() if o.scores else None, evidence=ev,
                             incomplete=incomplete)

        missing = [o for o in outcomes if o.state == "missing"]
        if not outcomes and not searchable(ref):
            return RefResult(ref, Verdict.NOT_CHECKABLE, 0.8,
                             "Too little parsed metadata to search. A search needs an identifier, a title, or "
                             "an author and year together with a journal volume and page.",
                             evidence=ev)
        if incomplete and not missing:
            return RefResult(ref, Verdict.UNRESOLVED, 0.2,
                             "Could not complete the check (resolver errors or offline cache misses). Run again "
                             "online before drawing any conclusion.", evidence=ev, incomplete=True)
        if not missing and flags & LOW_COVERAGE_FLAGS:
            kinds = ", ".join(sorted(flags & LOW_COVERAGE_FLAGS))
            return RefResult(ref, Verdict.NOT_CHECKABLE, 0.6,
                             f"No matching record found, but this looks like a kind of work ({kinds}) that the "
                             "registries cover poorly, so a miss says little. Check by hand if it matters.",
                             evidence=ev, incomplete=incomplete)
        conf = self._unresolved_confidence(ref, missing, incomplete)
        idtxt = ""
        if missing:
            idtxt = " " + "; ".join(f"{_k(o.kind)} {o.value} does not resolve"
                                    + (f" ({o.note})" if o.note else "") for o in missing) + "."
        return RefResult(ref, Verdict.UNRESOLVED, conf,
                         "No registry record matches this reference." + idtxt +
                         " It may be fabricated, or it may be a real work the consulted registries do not index. "
                         "Check it by hand before drawing a conclusion.", evidence=ev, incomplete=incomplete)

    # ------------------------------------------------------------ identifiers

    def _record_ev(self, ev: list[Evidence], resolver: str, action: str, lk: Lookup,
                   scores: MatchScores | None = None) -> None:
        ev.append(Evidence(resolver, action, lk.query, lk.status, lk.record, scores.to_dict() if scores else None,
                           lk.note))

    def _judge(self, ref: Reference, rec: Record) -> tuple[str, MatchScores]:
        s = compare(ref, rec)
        if s.agrees:
            return "agree", s
        if s.contradicts:
            return "mismatch", s
        return "uncertain", s

    def _check_doi(self, ref: Reference, doi: str, ev: list[Evidence]) -> IdOutcome:
        pos = pos_from_doi(doi)
        err_notes = []
        statuses: dict[str, str] = {}
        for name in ("crossref", "doi.org"):
            r = self.res.get(name)
            if r is None:
                continue
            lk = r.lookup("doi", doi)
            statuses[name] = lk.status
            if lk.status == "found":
                rec = lk.record
                if rec is not None and (rec.title or rec.authors):
                    state, s = self._judge(ref, rec)
                    self._record_ev(ev, name, "lookup_doi", lk, s)
                    return IdOutcome("doi", doi, state, rec, s, note=lk.note)
                self._record_ev(ev, name, "lookup_doi", lk)
                return IdOutcome("doi", doi, "exists_nometa", rec, note=lk.note)
            self._record_ev(ev, name, "lookup_doi", lk)
            if lk.status in _INCOMPLETE:
                err_notes.append(f"{name}: {lk.note or lk.status}")
        # the DOI system does not know it (or could not be reached)
        if pos and "pos" in self.res:
            o = self._check_pos(ref, "/".join(pos), ev, printed="doi")
            if o.state in ("agree", "uncertain", "repaired"):
                o.state = "repaired"
                o.repair_note = (f"The PoS DOI {doi} is not registered with doi.org (this is common for Proceedings "
                                 f"of Science), but the contribution exists at {o.record.ids.get('url')}.")
                if o.scores is None:
                    o.scores = compare(ref, o.record)
                return o
        for cand, why in doi_repairs(doi):
            for name in ("crossref", "doi.org"):
                r = self.res.get(name)
                if r is None:
                    continue
                lk = r.lookup("doi", cand)
                self._record_ev(ev, name, "repair_doi", lk)
                if lk.status == "found" and lk.record is not None:
                    state, s = self._judge(ref, lk.record)
                    ev[-1].scores = s.to_dict()
                    ev[-1].note = f"repair: {why}"
                    if state in ("agree", "uncertain") and (s.agrees or (lk.record.title is None)):
                        return IdOutcome("doi", doi, "repaired", lk.record, s, repaired_to=cand,
                                         repair_note=f"DOI {doi} does not resolve; {why} gives {cand}, which "
                                                     "resolves to a matching record.")
                    break
        # The global handle system is the authority on whether a DOI exists at all. If it could
        # not be asked, a Crossref miss proves nothing (the DOI may live in another registry).
        authority = "doi.org" if "doi.org" in statuses else ("crossref" if "crossref" in statuses else None)
        if authority is None or statuses[authority] != "not_found":
            return IdOutcome("doi", doi, "error", note="; ".join(err_notes) or "no DOI resolver available")
        return IdOutcome("doi", doi, "missing", note="checked Crossref and the doi.org handle system"
                         if authority == "doi.org" else "checked Crossref only")

    def _check_arxiv(self, ref: Reference, ev: list[Evidence]) -> IdOutcome:
        aid = ref.arxiv
        r = self.res.get("arxiv")
        lk = r.lookup("arxiv", aid) if r else Lookup("skipped", query=aid)
        if lk.status == "found" and lk.record is not None:
            state, s = self._judge(ref, lk.record)
            self._record_ev(ev, lk.record.source, "lookup_arxiv", lk, s)
            return IdOutcome("arxiv", aid, state, lk.record, s)
        self._record_ev(ev, "arxiv", "lookup_arxiv", lk)
        if lk.status in _INCOMPLETE or lk.status == "skipped":
            ads = self.res.get("ads")
            if ads is not None:
                lk2 = ads.lookup("arxiv", aid)
                if lk2.status == "found" and lk2.record is not None:
                    state, s = self._judge(ref, lk2.record)
                    self._record_ev(ev, "ads", "lookup_arxiv", lk2, s)
                    return IdOutcome("arxiv", aid, state, lk2.record, s)
                self._record_ev(ev, "ads", "lookup_arxiv", lk2)
                if lk2.status == "not_found":
                    return IdOutcome("arxiv", aid, "missing", note=lk.note)
            return IdOutcome("arxiv", aid, "error", note=lk.note)
        return IdOutcome("arxiv", aid, "missing", note=lk.note)

    def _check_bibcode(self, ref: Reference, ev: list[Evidence]) -> IdOutcome:
        lk = self.res["ads"].lookup("bibcode", ref.bibcode)
        if lk.status == "found" and lk.record is not None:
            state, s = self._judge(ref, lk.record)
            self._record_ev(ev, "ads", "lookup_bibcode", lk, s)
            return IdOutcome("bibcode", ref.bibcode, state, lk.record, s)
        self._record_ev(ev, "ads", "lookup_bibcode", lk)
        # a bibcode ADS no longer knows is weak evidence; let the metadata search decide
        return IdOutcome("bibcode", ref.bibcode, "error" if lk.status != "not_found" else "stale")

    def _check_pos(self, ref: Reference, value: str, ev: list[Evidence], printed: str) -> IdOutcome:
        lk = self.res["pos"].lookup("pos", value)
        if lk.status == "found" and lk.record is not None:
            state, s = self._judge(ref, lk.record)
            self._record_ev(ev, "pos", "lookup_pos", lk, s)
            o = IdOutcome("pos", value, state, lk.record, s, repaired_to=lk.record.ids.get("url"))
            return o
        self._record_ev(ev, "pos", "lookup_pos", lk)
        return IdOutcome("pos", value, "missing" if lk.status == "not_found" else "error")

    @staticmethod
    def _best_outcome(good: list[IdOutcome]) -> IdOutcome:
        order = {"agree": 2, "uncertain": 1, "exists_nometa": 0}
        return max(good, key=lambda o: (order[o.state], _rank(o.scores) if o.scores else ()))

    def _corrections_from(self, best: IdOutcome, wrong: list[IdOutcome], ref: Reference,
                          ev: list[Evidence]) -> dict[str, str]:
        """Suggest the right identifier for each wrong one, verified before it is suggested."""
        out: dict[str, str] = {}
        rec = best.record
        for o in wrong:
            if o.state == "repaired" and o.repaired_to:
                out["url" if o.kind == "pos" else o.kind] = o.repaired_to
                continue
            cand = None
            if rec is not None:
                if o.kind == "doi":
                    # a preprint's own DataCite DOI (10.48550/arXiv.*) is never the fix for a journal DOI;
                    # the journal DOI it reports (IsVersionOf / arxiv:doi) is
                    cands = [rec.related_ids.get("doi"), rec.ids.get("doi")]
                    cands = [c for c in cands if c and (not arxiv_from_doi(c) or arxiv_from_doi(o.value))]
                    cand = cands[0] if cands else None
                else:
                    cand = rec.ids.get(o.kind) or rec.related_ids.get(o.kind)
            if o.kind == "doi" and cand and cand.lower() != o.value.lower():
                # confirm the suggested DOI resolves and matches before recommending it
                for name in ("crossref", "doi.org"):
                    r = self.res.get(name)
                    if r is None:
                        continue
                    lk = r.lookup("doi", cand)
                    if lk.status == "found" and lk.record is not None:
                        s = compare(ref, lk.record)
                        self._record_ev(ev, name, "confirm_correction", lk, s)
                        if s.agrees or lk.record.title is None:
                            out["doi"] = cand
                        break
                    self._record_ev(ev, name, "confirm_correction", lk)
                continue
            if cand and cand.lower() != o.value.lower():
                out[o.kind] = cand
        if "doi" in [o.kind for o in wrong] and "doi" not in out:
            found, _ = self._search(ref, ev, stop_on_strong=True)
            if found is not None and found[0].ids.get("doi"):
                d = found[0].ids["doi"]
                if d.lower() != next(o.value for o in wrong if o.kind == "doi").lower():
                    out["doi"] = d
        return out

    # ------------------------------------------------------------ search

    def _search(self, ref: Reference, ev: list[Evidence],
                stop_on_strong: bool = True) -> tuple[tuple[Record, MatchScores] | None, bool]:
        """Return ((record, scores) of the best acceptable candidate or None, incomplete_flag)."""
        if not searchable(ref):
            return None, False
        best: tuple[Record, MatchScores] | None = None
        answered: set[str] = set()
        errored: set[str] = set()
        tried_any = False
        steps: list[tuple[str, Callable[[], Lookup]]] = []
        ads = self.res.get("ads")
        if ads is not None and ref.bibcode_hint and ref.bibcode_hint != ref.bibcode:
            steps.append(("ads", lambda: ads.lookup("bibcode", ref.bibcode_hint)))
        for name in ("ads", "crossref", "openalex"):
            r = self.res.get(name)
            if r is not None and r.searchable:
                steps.append((name, lambda r=r: r.search(ref)))
        if self.arxiv_search and "arxiv" in self.res and ref.title:
            steps.append(("arxiv", lambda: self.res["arxiv"].search(ref)))
        for name, fn in steps:
            if name == "arxiv" and best is not None:
                break
            lk = fn()
            if lk.status == "skipped":
                continue
            tried_any = True
            if lk.status in _INCOMPLETE:
                errored.add(name)
            else:
                answered.add(name)
            scored = []
            for rec in lk.records:
                s = compare(ref, rec)
                scored.append((rec, s))
            scored.sort(key=lambda t: _rank(t[1]), reverse=True)
            top = scored[0] if scored else None
            ev.append(Evidence(name, "search", lk.query, lk.status, top[0] if top else None,
                               top[1].to_dict() if top else None, lk.note))
            for rec, s in scored:
                if s.agrees and s.strength in ("strong", "moderate") and not s.contradicts:
                    if best is None or _rank(s) > _rank(best[1]):
                        best = (rec, s)
                    break
            if best is not None and best[1].strength == "strong" and stop_on_strong:
                break
        # A search counts as complete when at least one general-purpose index (Crossref or
        # OpenAlex) answered. One throttled resolver among several should not void the check.
        general = {"crossref", "openalex"} & set(self.res)
        if general:
            incomplete = bool(errored) and not (answered & general)
        else:
            incomplete = bool(errored) and not answered
        if not tried_any:
            return None, incomplete
        return best, incomplete

    # ------------------------------------------------------------ wording

    @staticmethod
    def _disagreement_text(s: MatchScores | None) -> str:
        if s is None:
            return "details"
        parts = []
        if s.title_mode == "field" and s.title is not None and s.title < 0.6:
            parts.append("title")
        if s.author is not None and s.author == 0.0:
            parts.append("authors")
        if s.year_delta is not None and s.year_delta >= 2:
            parts.append("year")
        if s.venue is not None and s.venue < 1.0:
            parts.append("volume/page")
        if not parts:
            return "details"
        return ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]

    @staticmethod
    def _unresolved_confidence(ref: Reference, missing: list[IdOutcome], incomplete: bool) -> float:
        c = 0.2
        if ref.title and ref.title_reliable:
            c += 0.25
        elif ref.title:
            c += 0.1
        if ref.authors or ref.collaboration:
            c += 0.1
        if ref.year:
            c += 0.05
        if ref.volume and ref.page:
            c += 0.15
        if missing:
            c += 0.2
        if incomplete:
            c -= 0.25
        return max(0.1, min(0.9, c))
