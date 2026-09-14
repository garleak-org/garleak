# Guide for coding agents

Garleak is an open archive for AI-assisted papers and research scratches. Each object
has a declared provenance and a public verification record. It is not a journal, a
preprint server, or peer review.

Since 2026-09-14 Garleak is a static site ([RFC 0001](rfcs/0001-static-architecture.md)).
The git repository is the database, a Python generator in `site/` builds the HTML, and
GitHub Pages serves it at garleak.org. In Phase 1, people submit and verify through
GitHub issue forms that Actions turn into pull requests.

Read these before changing anything that touches objects, stages, or copy.

- `llm.txt` is the living context file. Read it first in every session, and update it at
  the end of every session with status, decisions, and open issues. The user wants it
  kept current. It is gitignored. Never commit it.
- `MASTER-PLAN.md` for what the project is and why.
- `SPEC.md` for the object definitions. It wins over anything in code comments.
- `DESIGN.md` for the visual and copy brief.
- `BUILD-PLAN.md` for milestones (S0 to S7), acceptance criteria, and status.
- `archive/FORMAT.md` for the record format.
- `docs/HOSTING.md` for hosting, DNS, and the free services in use.

## Layout

| Path | Owner | Notes |
|------|-------|-------|
| `site/` | core | Python 3.12 package `garleak-site`. `garleak_archive` loads and validates records and computes stages, `pct_original`, and diffs. `garleak_site` holds templates, static assets, and self-hosted fonts. |
| `archive/` | core, through pull requests | The real records, as YAML and Markdown. Format in `archive/FORMAT.md`. |
| `archive-example/` | core | Invented records for the prelaunch example under `/example/`. Never mixed into `archive/`. |
| `services/citecheck` | citecheck maintainers | Standalone. Citation checker, to be released as `garleak-citecheck`. |
| `packages/rubrics` | rubrics maintainers | Standalone. Versioned rubric YAML, schema, and validator. |
| `design/` | design | `tokens.css` (the token source), the prototype, and `NOTES.md`. |
| `docs/` | everyone | Operator and contributor documentation, starting with `HOSTING.md`. |
| `rfcs/` | everyone | Proposals for changes to the instrument. |
| `attic/` | nobody | The retired dynamic M0 stack. Reference only. Never import from it or build it. |
| `.github/workflows/` | core | `ci.yml` (citecheck, rubrics, DCO) and `site.yml` (build, check, deploy). |

## Building and testing

Each Python part has its own venv inside its directory (Python 3.12). Do not use any
shared venv outside the repository.

Site. The exact commands and flags are in `site/README.md` and in
`.github/workflows/site.yml`, which are the source of truth. The package installs two
commands.

```sh
cd site
python3.12 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/pytest
.venv/bin/garleak-archive --help     # record validation and checks
.venv/bin/garleak-site --help        # builds the static site
```

The build output directory (`_site/`) is gitignored. Search is indexed after a build
with Pagefind, for example `npx pagefind --site _site`.

citecheck.

```sh
cd services/citecheck
python3.12 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/pytest -m "not network"    # offline, on recorded fixtures
.venv/bin/pytest --network           # live services, by hand only
```

Rubrics.

```sh
cd packages/rubrics
python3.12 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python scripts/validate.py && .venv/bin/pytest
```

Design. `design/prototype/index.html` opens directly in a browser. There is nothing to
build.

## Invariants

Never break these. A change that needs to break one needs an RFC and a SPEC.md change
first, not a code change.

1. **v1 is immutable forever and hash-guarded.** Every version, once created, is
   immutable too. No change may edit or delete an existing version file. Each version
   record stores its content hash, and CI recomputes every hash and fails on any
   mismatch. Never rewrite the history of `main`, and never add a script or workflow
   that works around the guard.
2. **Verifications attach to an exact version**, never to a paper or scratch.
3. **Assistance axes and signals are never merged.** Writing (W0 to W3) and analysis
   (A0 to A2) are separate ordinal axes. Each has three signals (declared, predicted,
   community), stored and displayed separately. No average, no combined score, no single
   field, and no level that combines a W code with an A code.
4. **The classifier never overrides a declaration.** A prediction is an estimate shown
   with its interval. It is never used in screening, credits, stages, visibility, or
   ranking. Contests are recorded.
5. **Failed verifications are displayed**, with the same prominence as passing ones.
6. **T0 content, gated content, and listing pages carry `noindex`.**
7. **Invented example records live only under `/example/`.** They come from
   `archive-example/`, and every page built from them has a visible banner and
   `noindex`. Never put an invented record in `archive/`.
8. **Nothing ever 404s for an archive identifier.** An identifier that was issued
   resolves to its page or a tombstone. One that was never issued reaches a page that
   says so and links to what exists.
9. **Papers and scratches never share a listing**, an identifier space, or a stage
   ladder.
10. **The repository is public.** Nothing that SPEC.md §11 marks restricted (R) or held
    (H) is ever committed. Phase 1 limits on identity are in SPEC.md §3.7, and copy must
    not promise more privacy than they allow.
11. **Wording.** Never call Garleak a journal, a preprint server, or peer review. Never
    write "published", "real paper", or anything implying peer review for what Garleak
    does. Use Verified (with a stage), Graduated, and admitted. Admitted never means
    endorsed.
12. **Branding.** No arXiv maroon (`#b31b1b` or anything near it) and no "arxiv" string
    in the branding (names, the mark, colors, class names, page titles, domains).
13. **The instrument changes only through an RFC.** That covers tiers, stages, rubrics,
    the credit ratio, and the other parts SPEC.md §10.1 lists. Every verification
    records the rubric version it used.
14. **No real credentials in the repository.** Tokens and client secrets that workflows
    need live in repository secrets.

## Ownership

`packages/rubrics` and `services/citecheck` are standalone packages. They must stay
installable and testable on their own, because they are how outside contributors find
the project. They never import from `site/` or `attic/`. When doing site work, do not
edit files in those directories. Open a separate change for their maintainers.

`design/` owns colors, type, and spacing. The generator's templates take them from
`design/tokens.css` and never choose them by hand.

`attic/` is read-only reference. Its README says what may be reused.

## Conventions

- A new kind of record comes with its JSON Schema in `site/garleak_archive/schemas/`, its
  entry in `archive/FORMAT.md`, and a check against the SPEC.md §11 table, all in the
  same change.
- Pages are static HTML and must work with JavaScript disabled. Add JavaScript only
  when a feature cannot work without it, and keep the page usable without it.
- New source files carry `SPDX-License-Identifier: AGPL-3.0-or-later`.
- Commits are signed off (`git commit -s`). CI rejects unsigned commits.
- Update `llm.txt` before the session ends.

## Prose rules

These apply to README files, plans, docs, comments, and user-facing copy.

- Plain, active, specific. "Verify this version", not "Submit verification". An action
  keeps its name through a flow (Verify, then Verified).
- No em dashes. Use commas, parentheses, or separate sentences.
- Few colons in running prose.
- Avoid these words: delve, underscore, pivotal, leverage, robust, seamless,
  comprehensive, intricate, meticulous, crucial, showcase, streamline, harness,
  landscape, realm, foster.
- Avoid the visual tells DESIGN.md lists in copy too (all-caps labels, arrows appended
  to link text, strings joined with middle dots).
- Empty states are invitations. Say what belongs there and how to add it.
