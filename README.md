# Garleak

Garleak (garleak.org) is an open archive for AI-assisted research. Every paper and every
research sketch on it says which model was involved and how much, and carries a public
record of who checked it and what they found. The interesting question here is not
whether a model wrote something. It is whether the thing holds up.

Garleak is not a journal, a preprint server, or peer review, and it is not anonymous.
Every submission has an accountable human. Screening checks scope and form only, so
admission says nothing about whether a paper is correct. A verification stage says
exactly what was checked and nothing more.

There are two kinds of object, kept apart everywhere (separate listings, separate
identifiers, separate stages).

- **Papers** are full write-ups with a claim and an argument. They climb verification
  tiers from T0 (unverified) through T1 (citations checked), T2 (claims checked against a
  field rubric), and T3 (partially reproduced) to T4 (independently reproduced). A paper
  that meets the graduation rules becomes Graduated, with a stable citation string.
- **Sketches** are ideas and fragments, checked for novelty rather than correctness
  (N0 posted, N1 no prior work found, N2 prior work found and linked, N3 judged
  tractable). A sketch that someone tests can be promoted into a paper that credits the
  sketch's author by a permanent backlink.

Verifications attach to a specific version, and v1 is kept unchanged forever. Assistance
is declared on two axes, writing (from W0, a human wrote it, to W3, a model wrote it) and
analysis (from A0, a human did it, to A2, a model did it). Each axis shows three signals
side by side (declared by the submitter, predicted by a classifier, and the median of
reader votes), never merged into one number. Verifying earns credits and submitting
spends them.

Garleak is a static site. The records live in this repository as YAML and Markdown
files, a Python generator builds the HTML, and GitHub Pages serves it. In the first
phase, people submit and verify through GitHub issue forms, and identity is a GitHub
account linked to an ORCID record. That link is public, so the first phase cannot keep a
pseudonym private except for accounts verified by institutional email.
[SPEC.md](SPEC.md) §3.7 and [RFC 0001](rfcs/0001-static-architecture.md) explain the
trade-off and what a later phase would change.

The rationale is in [MASTER-PLAN.md](MASTER-PLAN.md). The object definitions are in
[SPEC.md](SPEC.md), the visual brief in [DESIGN.md](DESIGN.md), the milestone plan in
[BUILD-PLAN.md](BUILD-PLAN.md), and hosting in [docs/HOSTING.md](docs/HOSTING.md).

## Status

Prelaunch, as of 2026-09-14. The archive holds no records yet. The specification (draft
0.2) is out for comment, the site generator and the example archive are being built
(milestone S0), and citecheck and the first three rubrics are written. See
[BUILD-PLAN.md](BUILD-PLAN.md).

## Repository map

| Path | What it holds |
|------|---------------|
| `site/` | The static-site generator and archive library (Python 3.12). Loads and validates records, computes stages and `pct_original`, and writes the HTML. |
| `archive/` | The records, one file per object and event, in the format in `archive/FORMAT.md`. The git history is the audit trail. |
| `archive-example/` | Invented records for the prelaunch example under `/example/`, shown with a banner and `noindex`. |
| `services/citecheck` | Citation checker. A standalone package, useful outside Garleak. |
| `packages/rubrics` | Versioned field rubrics (YAML), their schema, and a validator. A standalone package. |
| `design/` | Design tokens, the prototype, and design notes. |
| `docs/` | Operator and contributor documentation. |
| `rfcs/` | Proposals for changes to the instrument (tiers, rubrics, credit ratio, assistance axes). |
| `attic/` | The retired dynamic stack (FastAPI, Next.js, Docker Compose), kept for reference. |

## Quickstart

Everything needs Python 3.12. Each part has its own venv inside its directory.

The site. Full commands are in `site/README.md`.

```sh
cd site
python3.12 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest
.venv/bin/garleak-site --help
```

citecheck.

```sh
cd services/citecheck
python3.12 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest -m "not network"
```

Rubrics.

```sh
cd packages/rubrics
python3.12 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python scripts/validate.py && .venv/bin/pytest
```

## Licenses

| What | License |
|------|---------|
| Code in this repository (site generator, citecheck, rubric validator, workflows) | [AGPL-3.0-or-later](LICENSE) |
| Rubric YAML files and the rubric schema | CC0 1.0 |
| The specification | CC0 1.0 |
| Verification records and metadata | CC0 1.0 (they are facts about the corpus) |
| Paper and sketch content | Chosen by the submitter from a short list, CC BY 4.0 by default |
| Released datasets | CC BY 4.0, each with a DOI and a citation string |
| Fonts in `site/garleak_site/static/fonts` | SIL Open Font License 1.1 (license files alongside) |

## Contributing

Sign off your commits (DCO, no CLA). Changes to tiers, rubrics, the credit ratio, or the
assistance axes need an RFC first, because those are the measuring instrument and a
silent change breaks comparison across time. Details in
[CONTRIBUTING.md](CONTRIBUTING.md).
