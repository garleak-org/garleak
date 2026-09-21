# SPDX-License-Identifier: AGPL-3.0-or-later
"""Helpers for the intake tests: a sketch archive with the real config and categories,
issue fixtures rendered from the real issue forms, and a fake HTTP client."""

from __future__ import annotations

import copy
import datetime as dt
import shutil
from pathlib import Path

import yaml

from garleak_archive.hashing import sketch_content_sha256, tree_sha256
from garleak_archive.loader import load_archive
from garleak_archive.validate import validate
from garleak_intake.context import Comment, Context, OpenPR
from garleak_intake.forms import load_forms, render_body
from garleak_intake.http import Response
from garleak_intake.process import Options, process_issue

SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parent
RUBRICS = REPO / "packages" / "rubrics"
NOW = dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc)
FORMS = load_forms()

SENTENCE = ("We measure the rotation curve of the disk from stellar kinematics and compare it with a model that "
            "includes a bulge, a thin disk and a dark halo. ")


def long_body(seed: str = "alpha", n: int = 12) -> str:
    text = "".join(f"{SENTENCE}Sample {seed} number {i} gives an answer consistent within the errors. " for i in range(n))
    return f"## Results\n\n{text}\n"


ABSTRACT = ("We fit the rotation curve of a nearby disk galaxy with a bulge, a disk and a halo, and find that the "
            "halo mass within ten kiloparsecs is lower than earlier estimates by a fifth.")
T1_ITEMS = "\n".join(f"{i} | pass | https://example.org/evidence/{i}" for i in (
    "cit.T1.exists", "cit.T1.metadata-agree", "cit.T1.supports-central", "cit.T1.supports-sample", "cit.T1.retractions"))


def _all(kind: str, fid: str) -> list[str]:
    return list(FORMS[kind].field(fid).options)


DEFAULTS = {
    "identity": {"kind": "Human", "path": "ORCID: my public ORCID record lists this GitHub profile",
                 "orcid": "0000-0002-1825-0097", "display": "Real name", "display_name": "Dana Example",
                 "confirm": _all("identity", "confirm")},
    "sketch": {"category": "astro.ga: Galaxies and the Milky Way",
                "statement": "Wide-binary eccentricities should flatten above 0.1 pc if the Galactic tide is strong.",
                "models": "gpt-5, OpenAI, 2026-06", "writing": "W3: a model wrote it, with light or no human edits",
                "analysis": "No analysis in this sketch", "license": "CC-BY-4.0 (default)",
                "confirm": _all("sketch", "confirm")},
    "paper": {"category": "astro.ga: Galaxies and the Milky Way", "title": "A lighter halo from a rotation curve fit",
              "abstract": ABSTRACT, "models": "claude-opus-4, Anthropic, 2026-05",
              "writing": "W2: a model drafted it, and a human edited it",
              "analysis": "A1: a model assisted, and a human checked it",
              "provenance": "The model drafted the text from our notes, and we checked every number.",
              "rubric_families": ["computational (results that come from running code)"],
              "license": "CC-BY-4.0 (default)", "body": long_body(), "confirm": _all("paper", "confirm")},
    "version": {"paper": "paper:1", "change": "minor: wording, typos, formatting, clarifications, reference metadata",
                "note": "Wording", "models": "claude-opus-4, Anthropic, 2026-05",
                "writing": "W1: a human wrote it, and a model polished it",
                "analysis": "A1: a model assisted, and a human checked it",
                "provenance": "We reworded two sentences by hand.", "body": long_body() + "\nOne clearer sentence.\n",
                "confirm": _all("version", "confirm")},
    "verify": {"version": "paper:1v1.0", "tier": "T1: citations checked", "rubric": "citations (T1, every field)",
               "rubric_version": "1.0.0", "kind": "Full verification", "items": T1_ITEMS,
               "summary": "All references exist and support the sentences that cite them.",
               "conflicts": "None that I know of", "attest": _all("verify", "attest")},
    "novelty": {"sketch": "sketch:1", "outcome": "N1: no prior work found",
                "summary": "No work uses the eccentricity distribution above 0.1 pc to measure the tide.",
                "sources": "ADS\nOpenAlex", "queries": "wide binary eccentricity tide\nGalactic tide wide binaries",
                "attest": _all("novelty", "attest")},
    "contest": {"version": "paper:1v1.0", "prediction": "1-p1", "axis": "writing",
                "statement": "We wrote the text ourselves and only used the model for spelling."},
    "vote": {"version": "paper:1v1.0", "writing": "W2: a model drafted it, and a human edited it",
             "analysis": "No vote on this axis", "confirm": _all("vote", "confirm")},
    "claim": {"sketch": "sketch:1", "confirm": _all("claim", "confirm")},
    "report": {"kind": "Report content", "subject": "sketch:1", "criterion": "1: not a genuine attempt at research",
               "details": "This looks like a test post."},
}


def answers(form_kind: str, /, **over) -> dict:
    d = copy.deepcopy(DEFAULTS[form_kind])
    d.update(over)
    return d


def make_issue(kind: str, ans: dict | None = None, number: int = 1, author: str = "alice",
               created: str = "2026-09-14T10:00:00Z", labels=(), state: str = "open") -> dict:
    form = FORMS[kind]
    return {"number": number, "title": kind, "body": render_body(form, ans if ans is not None else answers(kind)),
            "user": {"login": author, "type": "User"}, "labels": [{"name": x} for x in [*form.labels, *labels]],
            "state": state, "created_at": created}


def comment(body: str, user: str, cid: int = 100, at: str = "2026-09-14T11:00:00Z") -> Comment:
    return Comment.from_dict({"id": cid, "body": body, "user": user, "created_at": at})


def command_event(c: Comment) -> dict:
    return {"comment": {"id": c.id, "body": c.body, "user": {"login": c.user, "type": "User"},
                        "created_at": c.created_at.isoformat()}}


def ctx(comments=(), permissions=None, open_prs=(), votes=(), orcid=None) -> Context:
    return Context(list(comments), dict(permissions or {}), list(open_prs), list(votes), orcid)


def open_pr(number: int, issue: int, meta: dict) -> OpenPR:
    return OpenPR(number, f"intake/issue-{issue}", issue, dict(meta, issue=issue))


class FakeHttp:
    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[tuple] = []

    def request(self, method, url, *, headers=None, data=None, timeout=20.0, max_bytes=None):
        self.calls.append((method, url, dict(headers or {}), data))
        r = self.routes.get((method, url), self.routes.get(url))
        if isinstance(r, Exception):
            raise r
        return r if r is not None else Response(404, b"{}")


class Arch:
    """A copy of archive/ (real config.yaml and categories.yaml, no records) to add to."""

    def __init__(self, tmp: Path):
        self.root = tmp / "archive"
        shutil.copytree(REPO / "archive", self.root)
        cfg = yaml.safe_load((self.root / "archive.yaml").read_text())
        cfg["rubrics"] = str(RUBRICS)
        (self.root / "archive.yaml").write_text(yaml.safe_dump(cfg))
        self.set("screening.sample_rate", 0.0)  # the calibration draw has its own test

    def set(self, dotted: str, value) -> None:
        p = self.root / "config.yaml"
        data = yaml.safe_load(p.read_text())
        node = data
        keys = dotted.split(".")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
        p.write_text(yaml.safe_dump(data, sort_keys=False))

    def _w(self, rel: str, data: dict) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(data, sort_keys=False))
        return p

    def account(self, handle: str, github: str | None = None, kind: str = "human", path: str = "orcid",
                pseud: bool = False, operator: str | None = None, **extra) -> None:
        d = {"handle": handle, "display_name": f"u/{handle}" if pseud else handle.capitalize() + " Example",
             "kind": kind}
        if pseud:
            d["pseudonymous"] = True
        if kind == "human":
            d["identity_path"] = path
        else:
            d["operator"] = operator
        d["github"] = github or handle
        d.update(extra)
        self._w(f"accounts/{handle}.yaml", d)

    def sketch(self, n: int, author: str, date: str = "2026-09-01", category: str = "astro.ga",
                statement: str | None = None, **extra) -> None:
        d = {"id": f"sketch:{n}", "category": category, "author": author, "date": date,
             "statement": statement or f"Sketch number {n} says something testable about wide binaries.",
             "models": [{"name": "gpt-5"}], "assistance": {"writing": "W3", "analysis": None}}
        d["v1_sha256"] = sketch_content_sha256(d)
        if self.load_accounts().get(author, {}).get("kind") == "agent":
            d["track"] = "autonomous"
        d.update(extra)
        self._w(f"sketches/{n}.yaml", d)

    def load_accounts(self) -> dict:
        return {p.stem: yaml.safe_load(p.read_text()) for p in (self.root / "accounts").glob("*.yaml")}

    def paper(self, n: int, submitter: str, date: str = "2026-09-01", category: str = "astro.ga",
              authors: list[str] | None = None, families=("computational",), body: str | None = None, **extra) -> None:
        d = self.root / "papers" / str(n)
        vd = d / "v1.0"
        vd.mkdir(parents=True)
        meta = {"title": f"Paper {n} on rotation curves", "authors": authors or [submitter], "abstract": ABSTRACT,
                "date": date, "change": "initial", "submitted_by": submitter,
                "assistance": {"writing": "W2", "analysis": "A1"}, "models": [{"name": "model-x"}],
                "rubric_families": list(families)}
        (vd / "meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
        (vd / "body.md").write_text(body or long_body(f"paper{n}"))
        cat_gated = category == "other.applied"
        acc = self.load_accounts().get(submitter, {})
        data = {"id": f"paper:{n}", "category": category, "submitter": submitter, "created": date,
                "license": "CC-BY-4.0", "gated": cat_gated,
                "track": "autonomous" if acc.get("kind") == "agent" else "human-prompted",
                "v1_sha256": tree_sha256(vd)}
        data.update(extra)
        self._w(f"papers/{n}/paper.yaml", data)

    def verification(self, n: int, vid: str, verifier: str, date: str = "2026-09-05", tier: str = "T1",
                     version: str = "1.0", at: str | None = None, **extra) -> None:
        from garleak_archive.rubrics import RubricSet

        rub = RubricSet.load(RUBRICS).get("citations" if tier == "T1" else "computational", "1.0.0")
        d = {"id": vid, "version": version, "kind": "paper", "tier": tier,
             "rubric": {"id": rub.id, "version": "1.0.0"}, "verifier": verifier, "date": date, "result": "passed",
             "summary": "Checked.", "items": [{"id": i.id, "verdict": "pass"} for i in rub.required_at(tier)],
             "status": "active"}
        if at:
            d["intake"] = {"path": "issue-form", "issue": 900, "at": at}
        d.update(extra)
        self._w(f"papers/{n}/verifications/{vid}.yaml", d)

    def check(self, n: int, cid: str, checker: str, date: str = "2026-09-05", outcome: str = "N1") -> None:
        p = self.root / "sketches" / f"{n}.yaml"
        data = yaml.safe_load(p.read_text())
        data.setdefault("checks", []).append({"id": cid, "outcome": outcome, "checker": checker, "date": date,
                                              "summary": "Searched.", "sources": ["ADS"], "queries": ["q"]})
        p.write_text(yaml.safe_dump(data, sort_keys=False))

    def load(self):
        return load_archive(self.root)

    def errors(self) -> list[str]:
        return [str(i) for i in validate(self.load()) if i.level == "error"]


def run(arch: Arch, issue: dict, context: Context | None = None, event: dict | None = None, **opts):
    o = Options(now=NOW, offline=opts.pop("offline", True), citecheck=opts.pop("citecheck", "/nonexistent/citecheck"),
                **opts)
    return process_issue(issue, arch.root, context or Context(), o, event)
