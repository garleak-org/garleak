# Build Plan

The milestone plan that [MASTER-PLAN.md](MASTER-PLAN.md) section 13 refers to, rewritten
on 2026-09-14 for the static architecture in
[RFC 0001](rfcs/0001-static-architecture.md). The earlier plan (M0 to M7) assumed a
server stack of FastAPI, PostgreSQL, Next.js, and Docker Compose. Its finished M0
scaffold is kept in [attic/dynamic-m0](attic/README.md).

Each milestone lists scope, deliverables, acceptance criteria, dependencies, and the
warnings the master plan attaches to it. Object definitions live in [SPEC.md](SPEC.md),
the record format in `archive/FORMAT.md`, the invariants in [CLAUDE.md](CLAUDE.md), and
the hosting details in [docs/HOSTING.md](docs/HOSTING.md).

| | Milestone | Status (2026-09-14) |
|---|---|---|
| S0 | Static site and prelaunch deploy on garleak.org | In progress. The generator and archive library are being built in `site/`, with self-hosted fonts. The owner is the organization `garleak-org` (not yet created). The domain order needs confirming, since `garleak.org` was not in the .org registry on 2026-09-14. DNS and GitHub Pages come after both. |
| S1 | Archive format, validation, v1 immutability guard in CI | In progress. Record schemas and an immutability module exist in `site/garleak_archive/`, and `archive/FORMAT.md` is being written. |
| S2 | Submission through issue forms, automated pre-screen, credit ledger | Not started |
| S3 | Verification through issue forms, rubric item records, anti-gaming, standing | Not started. The rubrics are written (citations, computational, and mathematics v1.0.0, status draft, 43 items, a validator, 27 tests). |
| S4 | Stamped PDFs, diff pages, digests and feeds | Not started |
| S5 | citecheck, released as `garleak-citecheck` | Code done, not released. 49 offline tests pass. The benchmark is in-sample only. |
| S6 | Fixes, scratch promotion, graduation, moderator queue, features, leaderboard | Not started |
| S7 | Zenodo DOIs, dataset export, final terms, seeding | Not started |
| Phase 2 | Cloudflare Worker with ORCID sign-in, for private identity | Planned for after Phase 1 opens |

Done outside the milestones: SPEC.md draft 0.2 (two assistance axes, Phase 1 identity
limits), the revised DESIGN.md, RFC 0001, and the hosting comparison.

## Identity decision

Decided 2026-09-14. Garleak opens with Phase 1 (issue forms, GitHub account plus ORCID
link, handles public) and adds the Worker after opening. The records, their validation,
and the site do not depend on this choice, because the Worker will commit the same
records that the issue-form path commits.

## Rules that apply to every milestone

- v1 of every paper and scratch is immutable forever, and so is every later version once
  created. Each version's content hash is stored in its record. CI recomputes every hash
  and fails any pull request that changes or deletes an existing version. The history of
  `main` is never rewritten.
- Verifications attach to an exact version, never to a paper or scratch.
- Assistance is declared on two axes, writing (W0 to W3) and analysis (A0 to A2), each
  with three signals (declared, predicted, community). They are stored and shown
  separately. Nothing averages or merges them, nothing combines the axes, and the
  classifier never overrides a declaration.
- Failed verifications are displayed, never hidden.
- T0 content, gated content, and listing pages carry `noindex`.
- Invented example records exist only in `archive-example/` and appear only under
  `/example/`, with a banner on every page and `noindex`.
- Nothing that SPEC.md §11 marks restricted (R) or held (H) goes into the repository,
  which is public (SPEC.md §3.7.5).
- Screening checks admissibility, never quality.
- Copy never calls Garleak a journal, a preprint server, or peer review, and never says
  "published". Use Verified (with a stage), Graduated, and admitted.
- No arXiv maroon and no "arxiv" string in the branding.
- Any change to tiers, rubrics, the credit ratio, or the other parts of the instrument
  in SPEC.md §10.1 goes through an RFC.
- **Build the diff viewer before any visual polish.** Here that means pre-rendered diff
  pages between versions. Seeing what a human had to change to make a model's paper
  correct is the content of the site.

## Measurement from day one

Every metric in master plan section 16 has to be computable from history. In a static
archive the history is the repository. Each record carries its timestamp, and git
records the commit that added it, so the numbers can be recomputed at any time. The
records behind each metric exist from the milestone that creates them.

| Metric | Records needed | From |
|---|---|---|
| Verification ratio | submissions, verifications | S2, S3 |
| Median time to T1 | version created, tier reached | S1, S3 |
| Fraction above T0 | tier per current version | S3 |
| Repeat verifier rate at 30 days | verification with verifier and timestamp | S3 |
| Median edits from v1 to T3 | version texts, tier reached | S1, S3 |
| Declared versus predicted gap | declared codes on each axis, predicted codes with intervals | S2, and whenever the classifier lands |
| Fabricated-citation rate by model | citecheck results with the declared model | S2, S5 |

A dashboard is S6 work, but the numbers must be recoverable before then.

---

## S0. Static site and prelaunch deploy

**Scope.** A public site on garleak.org before any real submission, so that people can
read the spec, see what a record will look like, and volunteer to verify.

**Deliverables**

- The generator in `site/` (Python 3.12, Jinja templates, tokens from
  `design/tokens.css`, self-hosted fonts), writing plain HTML to a build directory that
  is never committed.
- Pages for the spec (rendered from SPEC.md), the stages, an about page that says what
  Garleak is and is not and states the Phase 1 identity trade-off as SPEC.md §3.7.4
  requires, and the call for verifiers (master plan section 19 asks for five by name
  before anything else).
- The example archive at `/example/`, built from `archive-example/`, with a banner on
  every page and `noindex`.
- `site.yml`, a custom Actions workflow that builds the site, runs the checks, and
  deploys to GitHub Pages.
- The custom domain with HTTPS enforced, and contact@garleak.org forwarding, following
  docs/HOSTING.md.
- Checks in CI for branding (no "arxiv" string, no maroon), wording ("published",
  "journal", "peer review" used as a claim), `noindex` on `/example/` and listings, and
  broken links.

**Acceptance criteria**

- https://garleak.org serves the site with a valid certificate, and HTTP redirects to
  HTTPS.
- Every page under `/example/` has the banner and `noindex` (tested).
- The branding and wording checks pass.
- Every page renders and navigates with JavaScript disabled.
- WCAG AA contrast with the revised palette and ramp v2 (DESIGN.md).

**Depends on.** The maintainer creating the GitHub organization `garleak-org` (the name
`garleak` belongs to an unrelated user account), and `garleak.org` appearing in the .org
registry (on 2026-09-14 it did not, so the Namecheap order needs checking).

---

## S1. Archive format, validation, v1 immutability guard

**Slow down here.** Retrofitting the immutability guard is near-impossible once data
exists. Every later milestone builds on the decisions made in S1, and a mistake in the
record format corrupts the one dataset the project exists to produce.

**Scope.** The records for every object in SPEC.md, their validation, and the guard
that keeps versions unchanged.

**Deliverables**

- `archive/FORMAT.md`, documenting the file layout and fields for every object, following
  the SPEC.md §11 tables and holding only fields marked public (P).
- JSON Schemas for the records, and a validator that CI runs on every pull request.
- The immutability guard. Each version record stores its content hash. CI recomputes
  every hash and fails if an existing version file was changed or deleted. Branch
  protection on `main` requires the checks and forbids force-pushes and deletion.
- Identifier pages. Every issued identifier has a page or a tombstone. The custom 404
  page says when an identifier was never issued and links to what exists.
- `pct_original` by algorithm `po-1`, with the test vectors SPEC.md §6.6.6 requires.
- Stage computation from verification records (SPEC.md §2.4.3 and §2.4.4) as pure
  functions with tests.
- A field on each record for the intake path that created it (issue form or Worker),
  as RFC 0001 asks for comparability.

**Acceptance criteria**

- A pull request that edits or deletes an existing version file fails CI (tested with a
  fixture).
- Recomputed hashes match for every version in `archive/` and `archive-example/`.
- The `pct_original` test vectors pass, including the edge cases in SPEC.md §6.6.5.
- A verification record without an exact version identifier fails validation.
- The validator rejects fields that SPEC.md §11 marks R or H.

**Depends on.** SPEC.md sections for objects, stages, and versions.

**Open questions to settle before code.** The diff format (line diff on source text,
structured diff on a parsed document, or both), what counts as the source for a
PDF-only submission, and whether carrying a verification forward needs the verifier's
consent (OQ-22).

---

## S2. Submission through issue forms, automated pre-screen, credit ledger

**The pre-screen ships with submission, not after.** Submission is free, so the day it
opens without an automated first pass is the day screening becomes the founder's evening
job.

**Scope.** Getting papers and scratches in through issue forms, verifying identity,
paying with credits, and the automated screening pass.

**Deliverables**

- Issue forms in `.github/ISSUE_TEMPLATE/` for papers and scratches. Required fields
  include the declared writing and analysis codes, the models used, a provenance
  statement, the category, the rubric families (papers), and a content license from a
  short list with CC BY 4.0 as the default.
- An intake workflow that parses the form, validates it, writes the records, and opens a
  pull request. A paper waits for a moderator to review and merge it. A scratch merges
  automatically once every automated check passes.
- Identity. A verification form, and a workflow that reads the person's public ORCID
  record through a registered public API client and checks that it lists their GitHub
  profile URL. The institutional email path goes through the contact address, and a
  moderator records the result.
- The automated pre-screen as workflow jobs, each recording its check id, version, and
  score.

  | Check | Source |
  |---|---|
  | Fabricated or unresolvable citations | `citecheck` (S5), behind an interface that can be stubbed |
  | Near-duplicate of an existing submission | content hash plus text similarity |
  | Gated content filed elsewhere | classifier or keyword screen over title, abstract, and body |
  | Harmful content | classifier tuned for recall |
  | Empty, truncated, or non-research submissions | heuristics |
  | Plagiarism against Crossref and open corpora | a free service still to be found |

- Gated submissions are not accepted through public issue forms in Phase 1 (SPEC.md
  §3.7.7, OQ-24). The form points to the contact address instead.
- The credit ledger, computed from the records per field. The intake workflow refuses a
  submission that would take a balance below the floor. Credits are never sold, and
  submission never costs money.
- Agent accounts, each registered with a human operator whose credits pay. The intake
  workflow enforces the agent quota, and agent submissions are always held for review.
- Rejections cite a numbered criterion from the public admission criteria. One appeal,
  reviewed by a different moderator.
- The forms state, in plain words, that the GitHub account and the ORCID link are
  public (SPEC.md §3.7.4) and that admission never means endorsement.

**Acceptance criteria**

- No paper appears on the site without a pull request merged by a moderator.
- Balances recomputed from the records match what the intake check enforces.
- The agent quota is enforced, and agent submissions to gated categories are refused.
- The share of submissions reaching a human is measured and reported. The target is
  under 10%. If it rises, tighten the automated pass rather than recruit more
  moderators.

**Depends on.** S1. The citecheck interface can be stubbed.

**Warning.** Actions runners share IP addresses, so anonymous ORCID reads will hit the
per-IP quota. Use a registered public client (docs/HOSTING.md).

---

## S3. Verification through issue forms, rubric item records, anti-gaming, standing

**Scope.** Checking a version against a versioned field rubric, and the rules that keep
that checking honest.

**Deliverables**

- A verification form. The verifier names the exact version and the tier and gives a
  verdict (pass, fail, or not applicable with a reason) and evidence for every rubric
  item. The workflow records the rubric id and its current active version. T1
  (citations) is universal and always first.
- A novelty-check form for scratches (the search record for N1, the prior work for N2,
  the tractability note for N3). N2 is displayed neutrally.
- Failed verifications shown on the version with the same weight as passing ones.
- Conflict checks from public sources (ORCID works, Crossref, OpenAlex). Held data, such
  as declared affiliations, is checked by moderators outside the repository, and only
  the result is recorded.
- Anti-gaming, computed from the records.
  - Closed loops of length 2 to 4 in the verification graph earn nothing and are labeled.
  - Daily rate limits on verification, enforced by the intake workflow.
  - Shared affiliation or recent co-authorship is allowed, flagged, and visible.
  - T4 requires independence from every contributor.
- Verifier standing per field, recomputed from history.
- Moderation earns credits at the same rate as verification.

**Acceptance criteria**

- A test ring of three accounts verifying each other earns no credit and is labeled.
- A T4 attempt with a shared affiliation is refused.
- Every verification has a rubric version.
- Failed verifications appear on the version's `/abs/` page.
- Standing recomputed from history matches the published value.

**Depends on.** S1, S2 (credits), and the rubrics in `packages/rubrics`.

**Warning.** Changes to tiers, rubrics, or the credit ratio need an RFC from here on.

---

## S4. Stamped PDFs, diff pages, digests and feeds

**Build the diff viewer before any visual polish.**

**Scope.** The pages people read, built from real records, following DESIGN.md.

**Deliverables**

- Pre-rendered diff pages, first. At minimum each version against its parent and
  against v1. The diff may animate the change between compared versions, and nothing
  else on the site animates.
- The version timeline on the `/abs/` page, with `pct_original` as a filled proportion.
- The `/abs/` page in the order DESIGN.md gives, including the assistance block with
  both axes and all three signals side by side.
- Stamped PDFs, generated at build time. The not-peer-reviewed notice is printed on
  every page with the identifier, version, stage, and date.
- Daily listings per category in the mailing format, and Atom feeds per category and per
  stream.
- The Pagefind search index.

**Acceptance criteria**

- Every page of a stamped PDF carries the notice (tested by extracting text per page).
- T0 pages, gated pages, and listing pages have `noindex` (tested).
- No listing ever mixes papers and scratches (tested).
- Pages work with JavaScript disabled, with WCAG AA contrast, visible keyboard focus,
  `prefers-reduced-motion` respected, and stage never shown by color alone.

**Depends on.** S1 for records, S3 for stages.

---

## S5. citecheck, released as garleak-citecheck

**Parallelizable. Release it standalone early.** It is useful to people who will never
touch the archive, and it is the cheapest way to find collaborators.

**Scope.** A standalone tool that checks whether each reference exists and whether its
identifiers and metadata agree.

**Deliverables**

- The distribution renamed to `garleak-citecheck`, since the PyPI name `citecheck` is
  taken. Whether the import name stays `citecheck` is the maintainers' call.
- A tagged release on PyPI.
- An out-of-sample benchmark, since the current one was tuned on the same papers it
  reports on, plus fields beyond astronomy and harder fabricated references.
- Caching and rate limits, so it stays within the usage policies of the free public APIs
  it calls.
- A documented interface for the S2 pre-screen and automated T1 pre-checks.

**Acceptance criteria**

- Installs and runs with nothing else from this repository.
- Offline tests pass in CI.
- Precision and recall are reported on a labeled set that was not used for tuning.
- A tagged release exists before the archive opens.

**Status.** 49 offline tests pass (3 network tests are skipped by default). On the
in-sample benchmark, 1,044 real references gave no unresolved or metadata-mismatch
results, and 48 of 48 fabricated ones were flagged.

**Depends on.** Nothing. Owned by its own maintainers.

---

## S6. Fixes, scratch promotion, graduation, moderator queue, features, leaderboard

**Never ship the leaderboard before S3's anti-gaming is live.** A leaderboard over
unguarded verification rewards rings, and the numbers it shows would be wrong.

**Scope.** The features that make the archive a living thing rather than a pile.

**Deliverables**

- Fixes, shaped like pull requests (diff, rationale, merged or declined). The submitter
  maintains by default. After an inactivity window the paper becomes community
  maintained, and a fix merges on two approvals from verifiers with standing in the
  field. A merged fix earns more credit than a verification.
- Scratch promotion. A tested scratch becomes a new paper with a permanent backlink that
  credits the scratch's author. A scratch is never citable in a way that implies a
  result.
- Graduation, checked automatically. T3 or above, two independent verifiers, no shared
  affiliation, no open fixes. Graduation freezes that version, and further edits open a
  new major version at T0. The label is Graduated.
- Digests. Weekly most-verified, computed automatically. A monthly pick from that
  month's graduations, with written criteria and a named picker, chosen for verification
  depth and what was learned, plus a verifier of the month. Featured papers show
  `pct_original` and the gap between declared and predicted assistance on both axes.
- Model leaderboard. Verified-reproduction rate and fabricated-citation rate by model,
  field, and model version, with autonomous submissions in a separate track.
- Moderator queue, using issue labels. Flagged items plus the calibration sample,
  stated reasons, one appeal to a different moderator, and quarterly counts of
  submissions, holds, and rejections by reason.
- A dashboard for the section 16 metrics.

**Acceptance criteria**

- The leaderboard excludes verifications labeled as ring activity, and the autonomous
  track never mixes with the human-prompted one (tested).
- Graduation is refused while a fix is open (tested).
- The validator rejects a change that removes a promotion backlink.
- An appeal is never routed to the moderator who made the original decision.

**Depends on.** S3 (hard dependency for the leaderboard and community merges), S4.

**Warning.** Once a monthly feature exists, people polish before submitting, which
contaminates v1. Keep `pct_original` and the declared versus predicted gap visible on
featured papers.

---

## S7. Zenodo DOIs, dataset export, final terms, seeding

**Scope.** What has to exist before the doors open.

**Deliverables**

- Zenodo records for Graduated versions, with a version DOI and a concept DOI that
  resolves to the latest (OQ-16). PDFs move from the repository to Zenodo before the
  repository nears the GitHub size limits in docs/HOSTING.md.
- Dataset export of prompts, outputs, verdicts, and version histories under CC BY, with a
  DOI and a citation string. Verification records and metadata under CC0.
- Terms that state, in plain sentences, what identity protection the current phase
  actually gives, that submitters post only their own work and their own model output,
  that admission never means endorsement, and that archiving here is not prior
  publication and does not preclude journal submission. A named responsible person and
  a working takedown path.
- Seed content. 50 papers and 50 scratches across physics, computer science, and
  mathematics, verified by hand. Categories below a threshold are hidden rather than
  shown empty.

**Acceptance criteria**

- A DOI resolves for a seeded graduated paper, and the concept DOI moves when a new
  version graduates.
- The terms, the submission forms, and the `/abs/` header all carry the "admitted never
  means endorsed" statement.
- A dataset export rebuilds every version and matches the stored hashes.

**Depends on.** S1 through S6.

---

## Phase 2 option. Cloudflare Worker with private identity

**Scope.** Submissions and verifications that do not expose the submitter's GitHub
account or ORCID link.

**Deliverables**

- A Cloudflare Worker with ORCID OAuth sign-in that accepts submissions and
  verifications and commits the records with a bot token held in the Worker's secrets.
- Held identity kept outside the public repository.
- Optionally, submissions held privately until screened, which would close the gap in
  SPEC.md §3.7.7.
- The ORCID flow in `attic/dynamic-m0/apps/api/garleak_api/orcid.py` may serve as a
  starting point.

**Acceptance criteria**

- A submission made through the Worker produces the same records as the issue-form path,
  with no GitHub handle or ORCID link of the submitter in the repository.
- SPEC.md §3.3 is met without the Phase 1 exceptions in §3.7.

**Depends on.** S1, and Phase 1 being open (decided 2026-09-14).

**Free limits.** 100,000 requests a day and 10 ms of CPU time per request
(docs/HOSTING.md).

---

## Not yet placed

The master plan names these without assigning a milestone. Each needs a decision before
S4 ships the `/abs/` page, since the page shows all three signals on both axes.

- **The assistance classifier** (the predicted signal), one estimate per axis with an
  interval, contestable by the submitter, with every contest recorded. It must never
  override a declaration. It could run as a scheduled Action that writes prediction
  records after S2.
- **Community assistance votes** (the community median on each axis). In Phase 1 a vote
  cast through GitHub shows its voter (SPEC.md §3.7.5), so votes may be better left for
  Phase 2.
- **Bounties** on individual papers.
