# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sketches, papers and new versions."""

from __future__ import annotations

from garleak_archive.hashing import sketch_content_sha256, tree_sha256
from garleak_archive.stages import CITATIONS, graduated

from . import labels as L
from . import screen
from .assign import next_number
from .attachments import AttachmentError, Fetcher, pdf_field, text_field
from .requests import Fields, build_paper, build_sketch, build_version
from .screen import CHECK_VERSION

BODY_SUFFIXES = (".md", ".markdown", ".txt")
BIB_SUFFIXES = (".bib", ".txt")


class SubmitMixin:
    # -------------------------------------------------------- shared

    def _form_problems(self, f: Fields) -> None:
        for p in f.problems:
            self.res.fail("form", f"Form: {p.field}", p.message, "the issue form")

    def _fetcher(self) -> Fetcher:
        return Fetcher(self.opts.http, list(self.cfg["intake"]["attachment_prefixes"]), self.opts.offline)

    def _files(self, body_text: str, refs_text: str, pdf_text: str):
        """The body, the references and the PDF, downloading attachments where given."""
        cfg, fx, out = self.cfg["intake"], self._fetcher(), [None, None, None]
        for i, (what, fn) in enumerate((
            ("Body", lambda: text_field(body_text, fx, cfg["max_body_bytes"], BODY_SUFFIXES)[0]),
            ("References", lambda: text_field(refs_text, fx, cfg["max_bib_bytes"], BIB_SUFFIXES)[0] if refs_text else None),
            ("PDF", lambda: pdf_field(pdf_text, fx, cfg["max_pdf_bytes"])[0]),
        )):
            try:
                out[i] = fn()
            except AttachmentError as e:
                self.res.fail(f"attachment-{what.lower()}", what, f"Could not use it: {e}.", "the issue form")
        return out

    def _citecheck(self, bib: str | None) -> None:
        cc = self.cfg["intake"]["citecheck"]
        if not bib:
            self.res.skip("citations", "Citations", "no reference list was given, so citecheck did not run")
            return
        if not cc["enabled"]:
            self.res.skip("citations", "Citations", "citecheck is switched off in config.yaml")
            return
        from .paths import find_citecheck

        res = screen.run_citecheck(bib, find_citecheck(self.opts.citecheck), cc["timeout_seconds"], cc["max_refs"])
        ver = f"citecheck/{res.version}" if res.version else "citecheck"
        score = (res.flagged / res.total) if res.total else None
        if res.status == "pass":
            self.res.ok("citations", "Citations", res.detail or "every reference resolved", version=ver, score=score)
        elif res.status == "skipped":
            self.res.skip("citations", "Citations", res.detail)
        else:
            self.res.flag("citations", "Citations", (res.detail or res.status) + ". A moderator and the T1 verifier "
                          "see the flagged references. Existence is checked, never whether a reference supports "
                          "its sentence.", "SPEC §8.3.1", version=ver, score=score)
            self.res.labels_add.append(L.FLAGS["citations"])

    def _text_flags(self, flags: list[str]) -> None:
        if flags:
            self.res.flag("truncated", "Empty or truncated", "; ".join(flags).capitalize() + ". A moderator will look.",
                          "SPEC §8.3.1", version=f"text-heuristics/{CHECK_VERSION}", score=float(len(flags)))
            self.res.labels_add.append(L.FLAGS["truncated"])
        else:
            self.res.ok("truncated", "Empty or truncated", "the length and shape look complete",
                        version=f"text-heuristics/{CHECK_VERSION}", score=0.0)

    def _declaration_ok(self, models, writing, analysis) -> bool:
        return bool(models) and writing is not None and analysis is not None

    def _agent_hold(self, acc) -> None:
        if acc is not None and acc.is_agent:
            self.res.flag("agent", "Agent submission", "every submission from an agent account waits for a person",
                          "SPEC §3.4.6, §8.2.4")
            self.res.labels_add.append(L.FLAGS["agent"])

    def _authors(self, handles: list[str]) -> list[str]:
        for h in handles:
            if h not in self.a.accounts:
                self.res.fail("authors", "Authors", f"u/{h} has no Garleak account. Every author needs one.",
                              "SPEC §3.1")
        return handles

    # -------------------------------------------------------- sketch

    def do_sketch(self, f: Fields):
        req = build_sketch(f)
        acc = self.need_account()
        self._form_problems(f)
        cat = self.need_category(req.category, acc)
        if acc and cat:
            self.check_quota(acc, "sketch")
            sc = self.check_credits(acc, cat, "sketch")
        if req.statement:
            self._text_flags(screen.sketch_flags(req.statement, req.detail, self.cfg))
            self.check_duplicate(f"{req.statement}\n{req.detail}", screen.sketch_corpus(self.a),
                                 self.cfg["screening"]["sketch_shingle_k"])
            self.check_gated_keywords(f"{req.statement}\n{req.detail}")
        if self.res.failed:
            return self.refuse()
        self._agent_hold(acc)
        if not self.res.flagged and screen.calibration_sampled(
                self.number, screen.content_hash(req.statement + "\n" + req.detail),
                self.cfg["screening"]["sample_rate"]):
            self.res.flag("calibration-sample", "Calibration sample", "chosen at random for a person to read, "
                          f"{self.cfg['screening']['sample_rate']:.0%} of unflagged sketches", "SPEC §8.3.1, §8.3.5")
            self.res.labels_add.append(L.FLAGS["calibration-sample"])
        n = next_number(self.a.sketches, self.taken.get("sketch", set()),
                        self.cfg["intake"]["first_sketch_number"], self.mine.get("sketch", ()))
        data = {"id": f"sketch:{n}", "category": cat.code, "author": acc.handle, "date": self.date_iso(),
                "statement": req.statement}
        if req.detail:
            data["detail"] = req.detail
        data["models"] = req.models
        data["assistance"] = {"writing": req.writing, "analysis": req.analysis}
        data["v1_sha256"] = sketch_content_sha256(data)
        data.update({"license": req.license, "gated": cat.gated,
                     "track": "autonomous" if acc.is_agent else "human-prompted", "intake": self.intake()})
        self.w.data(f"sketches/{n}.yaml", data)
        self.meta("sketch", [f"sketch:{n}"], acc.handle, cat.field_code, sc.amount)
        auto = not self.res.flagged
        return self.done([f"sketch:{n}"], f"Add sketch:{n}", auto,
                         held_reason="It waits because the automated pass flagged it, or it came from an agent, or "
                                     "it was drawn for the calibration sample. A person reads it and merges it, or "
                                     "rejects it citing a numbered criterion.")

    # -------------------------------------------------------- paper

    def _families(self, fams: list[str]) -> list[str]:
        known = self.a.rubrics.ids() - {CITATIONS}
        for fam in fams:
            if fam not in known:
                self.res.fail("families", "Rubric families", f"There is no approved rubric family {fam!r}.",
                              "SPEC §4.2.2")
        if not fams:
            self.res.info("families", "Rubric families", "none declared, so the paper can reach T1 and no higher "
                          "until it declares one (SPEC §2.4.8)")
        return fams

    def _write_version(self, rel: str, meta: dict, body: str, bib: str | None, pdf: bytes | None) -> str:
        self.w.data(f"{rel}/meta.yaml", meta)
        self.w.text(f"{rel}/body.md", body)
        if bib:
            self.w.text(f"{rel}/refs.bib", bib)
        if pdf:
            self.w.binary(f"{rel}/paper.pdf", pdf)
        return tree_sha256(self.root / rel)

    def _meta(self, version, title, authors, abstract, date, change, note, submitted_by, req, families,
              transcript=None, artifacts=None) -> dict:
        meta = {"version": version, "title": title, "authors": authors, "abstract": abstract, "date": date,
                "change": change, "note": note, "submitted_by": submitted_by,
                "assistance": {"writing": req.writing, "analysis": req.analysis}, "models": req.models}
        if req.tools:
            meta["tools"] = req.tools
        if req.provenance:
            meta["provenance"] = req.provenance
        if transcript:
            meta["transcript"] = {"url": transcript}
        if artifacts:
            meta["artifacts"] = artifacts
        if families:
            meta["rubric_families"] = families
        meta["intake"] = self.intake()
        return meta

    def do_paper(self, f: Fields):
        req = build_paper(f)
        acc = self.need_account()
        self._form_problems(f)
        cat = self.need_category(req.category, acc)
        authors = self._authors(req.authors or ([acc.handle] if acc else []))
        fams = self._families(req.rubric_families)
        sketch = None
        if req.promoted_from:
            sketch = self.a.sketches.get(req.promoted_from)
            if sketch is None or sketch.status != "admitted":
                self.res.fail("promoted", "Promoted from", f"sketch:{req.promoted_from} is not an admitted sketch.",
                              "SPEC §2.6.1")
                sketch = None
            else:
                self.res.ok("promoted", "Promoted from", f"sketch:{sketch.number}v1.0 by u/{sketch.author}; its "
                            "author earns the promotion credit when this paper is admitted (SPEC §2.6.5)")
        body, bib, pdf = self._files(req.body, req.refs, req.pdf) if req.body else (None, None, None)
        if acc and cat:
            self.check_quota(acc, "paper")
            sc = self.check_credits(acc, cat, "paper")
        if body:
            self._text_flags(screen.paper_flags(req.title, req.abstract, body, self.cfg))
            self.check_duplicate(f"{req.title}\n{req.abstract}\n{body}", screen.paper_corpus(self.a),
                                 self.cfg["screening"]["paper_shingle_k"])
            self.check_gated_keywords(f"{req.title}\n{req.abstract}\n{body}")
            self._citecheck(bib)
        if self.res.failed:
            return self.refuse()
        self._agent_hold(acc)
        n = next_number(self.a.papers, self.taken.get("paper", set()), self.cfg["intake"]["first_paper_number"],
                        self.mine.get("paper", ()))
        rel = f"papers/{n}"
        meta = self._meta("1.0", req.title, authors, " ".join(req.abstract.split()), self.date_iso(), "initial",
                          "First submission", acc.handle, req, fams, req.transcript, req.artifacts)
        v1 = self._write_version(f"{rel}/v1.0", meta, body, bib, pdf)
        paper = {"id": f"paper:{n}", "category": cat.code, "submitter": acc.handle, "created": self.date_iso(),
                 "license": req.license, "gated": cat.gated, "track": "autonomous" if acc.is_agent else "human-prompted"}
        if sketch:
            paper["promoted_from"] = f"sketch:{sketch.number}v1.0"
            srel = f"sketches/{sketch.number}.yaml"
            sdata = self.w.load(srel)
            sdata["promoted_to"] = sorted(set(sdata.get("promoted_to") or []) | {n})
            self.w.data(srel, sdata)
        paper["v1_sha256"] = v1
        self.w.data(f"{rel}/paper.yaml", paper)
        self.meta("paper", [f"paper:{n}"], acc.handle, cat.field_code, sc.amount)
        return self.done([f"paper:{n}"], f"Add paper:{n}", False)

    # -------------------------------------------------------- new version

    def do_version(self, f: Fields):
        req = build_version(f)
        acc = self.need_account()
        self._form_problems(f)
        p = self.a.papers.get(req.paper) if req.paper else None
        if req.paper and p is None:
            self.res.fail("paper", "Paper", f"paper:{req.paper} does not exist.", "SPEC §2.3.7")
        elif p is not None and p.status != "admitted":
            self.res.fail("paper", "Paper", f"paper:{p.number} is {p.status}, so it takes no new versions.",
                          "SPEC §9.7.1")
        elif p is not None:
            self.res.ok("paper", "Paper", f"paper:{p.number}, current version v{p.current.number}")
            if acc and acc.handle not in p.maintainers and not (acc.is_agent and p.submitter == acc.handle):
                self.res.fail("maintainer", "Maintainer", f"Only a maintainer of paper:{p.number} ("
                              + ", ".join(f"u/{m}" for m in p.maintainers) + ") can add a version. Others propose "
                              "fixes.", "SPEC §6.7.3, §6.8.1")
        if p is None or self.res.failed:
            return self.refuse()
        cur = p.current
        g = graduated(p, cur.number)
        if req.change == "minor" and g is not None and g.state == "graduated":
            self.res.fail("bump", "Change", f"v{cur.number} is Graduated, so the next version must be major.",
                          "SPEC §7.3.2")
        number = cur.number.next_minor() if req.change == "minor" else cur.number.next_major()
        authors = self._authors(req.authors or list(cur.authors))
        parent_bib = cur.bib.read_text(encoding="utf-8") if cur.bib else ""
        body, bib, pdf = self._files(req.body, req.refs, req.pdf)
        bib = bib if req.refs else (parent_bib or None)
        if body:
            abstract = " ".join(req.abstract.split()) or cur.abstract
            self._text_flags(screen.paper_flags(req.title or cur.title, abstract, body, self.cfg))
            self.check_duplicate(f"{req.title or cur.title}\n{abstract}\n{body}",
                                 screen.paper_corpus(self.a, exclude=p.number), self.cfg["screening"]["paper_shingle_k"])
            if req.change == "minor":
                touched = screen.bump_flags(cur.body, body, parent_bib, bib or "")
                if touched:
                    self.res.flag("bump", "Minor change", "this minor version changes " + ", ".join(touched) + ". "
                                  "A minor version never changes a claim; verifiers may challenge the "
                                  "classification.", "SPEC §6.3.6, §6.3.7")
                    self.res.labels_add.append(L.FLAGS["bump"])
            if req.refs:
                self._citecheck(bib)
        if self.res.failed:
            return self.refuse()
        self._agent_hold(acc)
        date = max(self.day, cur.date).isoformat()
        rel = f"papers/{p.number}/v{number}"
        meta = self._meta(str(number), req.title or cur.title, authors, " ".join(req.abstract.split()) or cur.abstract,
                          date, req.change, req.note, acc.handle, req, list(cur.rubric_families),
                          None, list(cur.artifacts))
        h = self._write_version(rel, meta, body, bib, pdf)
        prel = f"papers/{p.number}/paper.yaml"
        pdata = self.w.load(prel)
        pdata.setdefault("version_sha256", {})
        pdata["version_sha256"][str(number)] = h
        self.w.data(prel, pdata)
        self.meta("version", [f"paper:{p.number}v{number}"], acc.handle, self.a.field_of(p.category), 0)
        return self.done([f"paper:{p.number}v{number}"], f"Add paper:{p.number}v{number}", False)
