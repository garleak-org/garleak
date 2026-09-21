# Master Plan

An open archive where AI-assisted work gets posted honestly and checked in public.

This supersedes the earlier planning docs. `BUILD-PLAN.md`, `CLAUDE.md`, and `DESIGN.md`
remain the working files for implementation; this is the document you show a
collaborator, a funder, or a university library.

**Edits on 2026-09-14.** Targeted changes, each applying a decision approved that day.

- §1. "Most recent papers" became "about half", matching the estimate of 52 ± 15% for
  2025 astro-ph papers.
- §2. The stale naming material is gone (the candidate table, "My pick is Foolscap",
  and the pre-purchase checklist). Two naming rules remain as guidance.
- §5c. The L0 to L4 taxonomy is replaced by two ordinal axes, writing (W0 to W3) and
  analysis (A0 to A2), each with its own three signals.
- §9. Cross-references fixed. Gated categories and plagiarism screening are in §10, and
  citecheck is milestone S5.
- §11. Rewritten for the static architecture (`rfcs/0001-static-architecture.md`).
- §13. Points to the new milestones S0 to S7 in `BUILD-PLAN.md`.
- §17. Hosting costs $0, and the domain is the only cost.
- §18. The screening row names milestone S2 instead of M2.
- §19. Step 1 records the domain order and the GitHub organization `garleak-org`.
- §11. The identity question is decided. Phase 1 opens first and the Worker follows.

**Edit on 2026-09-21.** §14. The archive covers astronomy and its subsections, with
one category for everything else. The wider field tree waits for records.

---

## 1. The thesis

About half of recent papers in at least one field show signs of AI assistance (my own
estimate for 2025 astro-ph papers is 52 ± 15%). Under 1% disclose
it. The response so far has been detection and prohibition, both of which fail: detection
is unreliable and disproportionately flags non-native English writers, and prohibition
just moves the practice underground, which is where it is now.

The alternative is a venue where disclosure is mandatory, structured, and costless — and
where the interesting question is not *did a model write this* but *does it hold up*.

That reframing is the whole project. Everything below follows from it.

**What it is:** an open archive of AI-assisted papers and research sketches, each with a
declared provenance and a public verification record.

**What it is not:** a preprint server, a journal, peer review, or anonymous.

**Why it survives:** the archive is the substrate. The product is the verification
record and the longitudinal dataset — the first continuous measurement of what it costs
a human to make machine-generated research correct.

---

## 2. Name and identity

**Garleak** — `garleak.org`. The frame is leaking an idea without attaching your name to
it, which matches the pseudonymous sketch stream.

Two things the name does not cover, and the copy therefore has to, prominently:

- Identity is held, not absent. "We know who you are. Nobody else does, unless you say
  so." Without this stated on the signup and submission pages, the name implies a
  stronger anonymity than the platform provides.
- Nothing here is unauthorized. Submitters post their own work and their own model
  output. The site is not a venue for other people's unpublished material, and the terms
  should say so in a sentence.

**Visual identity:** the garlic-bulb mark, and gold in the role arXiv gives maroon —
header rule, mark, active state. arXiv's maroon appears nowhere. Full palette and the
contrast constraint in `DESIGN.md`; the short version is that gold is an identity color
and never carries text.

### Naming rules for tools and sub-projects

- Nothing containing "arxiv" or a near-variant. Cornell holds the mark and enforces it.
- Nothing implying journal, peer review, or publication. You are not any of those, and
  the name will be doing rhetorical work for years.

---

## 3. What lives on the platform

Two object types, each with its own ladder of stages. The submitter chooses the type at
upload; the stage is earned, never chosen.

```
SKETCH                              PAPER
N0 posted                            T0 unverified
N1 no prior work found               T1 citations checked
N2 prior work found and linked       T2 claims checked
N3 judged tractable                  T3 partially reproduced
        │                            T4 independently reproduced
        └──── promoted ─────────────▶        │
              (new object,                   └── graduated
               credits the author)               (real names, citable)
```

### Papers

A full write-up with a claim and an argument. Verified for correctness.

### Sketches

An idea, an observation, a fragment that came out of a conversation with a model. Five
minutes to post. Verified for **novelty**, not correctness — the question is "has this
been done," which is a literature question and partly mechanical.

Sketches will probably outnumber papers heavily, and that's fine. A browsable feed of
plausible, not-previously-done, unclaimed ideas is genuinely useful to a graduate student
and exists nowhere else.

**Promotion:** a sketch that someone tests becomes a paper — a new object with a permanent
backlink crediting the sketch's author. This is the mechanic that makes posting an idea
worthwhile rather than a giveaway.

The two streams are completely separate: different listings, different identifiers,
different visual treatment, different credit costs. A sketch must never be citable in a way
that implies a result.

---

## 4. Identity and accountability

- **Every submission has an accountable human.** No exceptions.
- ORCID is the primary identity path. Verified institutional email is the fallback for
  fields where ORCID coverage is thin — law and the humanities especially. Without a
  second path those fields cannot participate.
- **Agent accounts** are permitted and first-class. Each has a registered human
  operator who bears accountability. The agent displays as author, the operator as
  responsible party. The operator's credits pay for the submission. Hard daily quota,
  much tighter than the human one. Excluded entirely from gated categories.
- Autonomous submissions are segregated in the leaderboard. Mixed into the
  human-prompted pool they measure nothing; separated, they are the cleanest capability
  measurement anyone has.

---

## 5. Scoring

Three independent signals, never collapsed into one number.

### 5a. Verification tier — papers

| Tier | Meaning |
|------|---------|
| T0 | Unverified |
| T1 | Citations checked — every reference exists and says what is claimed. **Universal across all fields, always first.** |
| T2 | Claims checked against the field rubric |
| T3 | Central result partially reproduced |
| T4 | Independently reproduced, no shared affiliation |

T1 is where these models fail most reliably and is the one check that partly automates.

**Field rubrics** sit under T2–T4: computational (code runs, outputs match),
mathematics (proof checks line by line), empirical and medical (studies exist and report
what is claimed), law (cases and statutes exist and are still good law), humanities
(quotations and sources exist and say what is claimed).

### 5b. Novelty stage — sketches

| Tier | Meaning |
|------|---------|
| N0 | Posted, nobody has looked |
| N1 | Searched, no close prior work found — verifier states where they looked |
| N2 | Prior work found and linked. **Informative, not a failure.** Display it neutrally or nobody will post. |
| N3 | Someone judged it tractable and said what testing it would take |

T3 and T4 have no meaning for a sketch. Don't fake them.

### 5c. Assistance: two axes, three signals each

Who wrote the text and who did the analysis are different questions, so assistance is
declared on two separate ordinal axes.

| Writing | |
|---|---|
| W0 | Human wrote it |
| W1 | Human wrote, model polished |
| W2 | Model drafted, human edited |
| W3 | Model wrote it (light or no human edits) |

| Analysis | |
|---|---|
| A0 | Human did the analysis |
| A1 | Model assisted (code or derivations, checked by a human) |
| A2 | Model did the analysis |

Each axis carries three signals, always shown separately.

| | Source |
|---|---|
| **Declared** | The submitter, one level on each axis |
| **Predicted** | Your classifier, on each axis, shown with a confidence interval |
| **Community** | Median of reader votes, on each axis |

Signals and axes are never averaged or merged, and the classifier **never overrides a
declaration**. It is
a calibration estimate, not an accusation. The submitter can contest a prediction and the
contest is recorded. Since there is no penalty for high AI use here, the classifier
doesn't have to function as an enforcement tool — which is exactly why this is the one
place it can be calibrated honestly.

The gap between declared and predicted, measured continuously with ground truth attached,
is the platform's most valuable research output.

### 5d. Verifier standing

Per-field, rises with verifications that survive, falls when overturned. Every
verification shows the verifier's name and the rubric items they passed or failed.
**Failed verifications are displayed, not hidden** — suppressing them biases the whole
archive upward.

### 5e. Display

Never one number. Current tier, verifier names, version count, `pct_original`. A T3 paper
that is 40% human-rewritten is a different object from an untouched one.

---

## 6. The credit economy

Generation is free, so unlimited submission drowns the archive in week one. Verification
is the scarce resource and nobody volunteers. One mechanic solves both.

- Verifying earns credits, submitting spends them. Opening ratio: **2 verifications per
  paper**, tighter for sketches. Tuned from real throughput, set in config.
- A merged fix earns more than a verification. It is harder work.
- **Credits are field-scoped.** Global pools get farmed in the easy fields and spent in
  the hard ones.
- Never charge money for submission. A fee reads as pay-to-publish, which is the exact
  adjacency to avoid. Credits are the access control.

### Anti-gaming

Reciprocal rings will form in the first month. Assume it.

- Closed loops of length 2–4 in the verification graph earn nothing and are labeled.
- Daily rate limits on verification. Careful checking is slow; a burst is a signal.
- Shared affiliation or recent co-authorship: allowed, flagged, visible.
- T4 requires no shared affiliation or co-authorship with any contributor.

---

## 7. Versions

- **v1 is immutable forever.** The raw model output is the scientific object.
- Verifications attach to a **version**, never a paper.
- `major.minor` numbering. Major bump when a claim changes — clears verifications. Minor
  for prose — carries them forward.
- Linear trunk per paper. Genuine divergence becomes a fork with a permanent backlink.
- Each version carries its own contributor list and its own assistance level. By v6 the
  authorship is not v1's authorship, and the site should say so.
- `pct_original` displayed always. It is the guard against papers being quietly edited
  until they're good, at which point they measure nothing.

**Fixes** are pull-request shaped: diff, rationale, merged or declined. The submitter
maintains by default; after an inactivity window the paper becomes community-maintained
and a fix merges on two approvals from verifiers with field standing. Without this, half
the archive freezes with open fixes nobody can apply.

---

## 8. Graduation and features

**Graduation:** T3 or above, two independent verifiers, no shared affiliation, no open
fixes. Distinct visual state, stable citation string, separate listing. Graduation
freezes that version; further edits open a new major version that starts unverified.

Call it **Verified** or **Graduated**. Never "real paper" or "published" — verification
is narrower than peer review and the language must not imply otherwise.

**Cadence:**

- *Daily* — new submissions digest, arXiv mailing format, purely mechanical. The
  habit-forming one.
- *Weekly* — most-verified, computed automatically. No judgment, no controversy.
- *Monthly* — editorial pick from that month's graduations, with published criteria and a
  named picker. Select on **verification depth and what was learned**, not on how
  impressive the result sounds. Run a verifier-of-the-month alongside it; recognition
  should flow to the scarce work.

Watch for prize-driven behavior: once a monthly feature exists, people polish before
submitting, which contaminates v1. Keep `pct_original` and the declared-versus-predicted
gap visible on featured papers.

---

## 9. Screening

Everything is read before or shortly after it goes public — papers and sketches alike.
The scope of that reading is narrow and fixed.

### What screening checks

Admissibility, never quality:

- Is this a genuine attempt at research rather than spam, a test post, or nonsense?
- Is it in scope and in the correct category?
- Does it belong in a gated category (§10) that it wasn't filed under?
- Does it contain anything harmful, defamatory, or plagiarized?

Nothing else. **Not whether the work is good, correct, novel, or worth reading** — that
is what the verification layer exists to determine. The moment screening becomes a
quality judgment, the platform is a journal with an editor, and every rejection becomes
an argument you own forever.

### Asymmetry by type

- **Papers**: screened *before* public visibility. They carry weight, get cited, and can
  graduate.
- **Sketches**: published immediately, removed post-hoc if they fail. Low-stakes by
  construction, and pre-screening them is where the volume problem bites hardest.
- **Anything in a gated category**: held for human review regardless of type. No
  exceptions.
- **Agent submissions**: held regardless of type.

### Volume

This is the most likely way the project dies — not from lack of interest, but from the
founder screening submissions every evening for eight months. Submission is free and a
sketch takes five minutes to write, so success means hundreds a week.

**Automate the entire first pass.** A human sees only what is flagged, plus a random
sample for calibration:

| Check | Source |
|---|---|
| Plagiarism against Crossref and open corpora | existing screen, §10 |
| Fabricated or unresolvable citations | `citecheck`, §13 milestone S5 |
| Near-duplicate of an existing submission | content hashing + embedding similarity |
| Gated-category content filed elsewhere | classifier over title, abstract, body |
| Harmful content | classifier, tuned for recall over precision |
| Empty, truncated, or non-research submissions | heuristics |

Target: under 10% of submissions reaching a human. If it climbs above that, tighten the
automated pass rather than recruiting more moderators.

### Moderators

Per-field, recruited on the same schedule as rubric maintainers, named publicly.
**Moderation earns credits at the same rate as verification** — it is the same kind of
unpaid labor and should carry the same standing.

### Transparency

arXiv's moderation is widely criticized for opacity: rejections without stated reasons
and no meaningful appeal. Doing better is cheap and is a real differentiator with exactly
the people who have been burned by it.

- Publish the admission criteria in full.
- Every rejection states a specific reason, citing the criterion.
- One appeal, reviewed by a different moderator.
- Publish quarterly counts: submissions, held, rejected, by reason.

### Language

**Admitted never means endorsed.** Someone will eventually argue that you approved what
they acted on. The terms, the submission page, and the paper header must all say that
screening checks scope and form only, and that admission carries no claim about
correctness.

---

## 10. Safety and legal

- **Gated categories** — clinical, legal, financial, pharmacological, structural
  engineering. Not publicly visible below T1. No agent submissions.
- `noindex` on all T0 content. Blunts citation laundering.
- The not-peer-reviewed notice is stamped **inside the PDF**, on every page. PDFs travel;
  pages don't.
- Plagiarism screening on v1 against Crossref and open corpora.
- A named responsible person and a working takedown path. Required for any institutional
  partnership.
- **Explicit in the terms: archiving here is not prior publication and does not preclude
  journal submission.** The biggest hesitation among people with genuinely interesting
  drafts is that posting burns their journal option. Say so before the objection forms.

---

## 11. Architecture

Static, free, and boring. Contributors are academics, not platform engineers, and a
static site has no server to patch, no database to back up, and no monthly bill. The
decision and its trade-offs are recorded in `rfcs/0001-static-architecture.md`.

**The repository is the database.** Papers, sketches, versions, verifications, and
screening decisions are YAML and Markdown records under `archive/`, in the format
documented in `archive/FORMAT.md`. Git history is the audit trail. v1 is guarded by a
content hash that CI checks on every pull request.

**A Python generator in `site/` builds the pages** (listings, `/abs/`, diffs, digests,
feeds) as plain HTML with near-zero JavaScript. Search is Pagefind, a static index built
with the pages. GitHub Actions builds the site and deploys it to GitHub Pages at
`garleak.org`, registered at Namecheap. Hosting options and their limits are in
`docs/HOSTING.md`.

**Phase 1 submission and verification go through GitHub issue forms.** An Actions
workflow turns each form into a pull request. Screening a paper is reviewing and merging
that pull request. A sketch merges automatically once the automated checks pass.

**Phase 1 identity is a GitHub account plus an ORCID link.** The link is verified by
checking that the person's public ORCID record lists their GitHub profile URL, through
the ORCID public API, with no server. Where ORCID coverage is thin, a moderator verifies
an institutional email by hand through the contact address.

**The trade-off, stated plainly.** In Phase 1 GitHub handles are public, and so is the
ORCID record that links a handle to a name. That weakens "We know who you are. Nobody
else does" for pseudonymous sketches, and the copy has to say so. Only an account
verified by institutional email keeps its identity out of public view. Issues are also
public from the moment they are opened, so a paper is visible on GitHub before it is
screened, even though the site shows it only after merge. Gated submissions should not
come in through public issue forms at all (`SPEC.md` §3.7.7).

**Phase 2 option, still free.** A Cloudflare Worker with ORCID OAuth accepts submissions
and commits them with a bot token, so submitter identity stays private and the promise
in §2 holds as written.

**Decided 2026-09-14.** Open with Phase 1 and add the Worker later. Pages say plainly
that GitHub handles are public until then.

**Files and DOIs.** PDFs and figures live in the repository at first. Zenodo (free)
holds files and mints DOIs for Graduated versions later, a version DOI plus a concept
DOI that resolves to the latest.

Identifiers: `sketch:4471` resolves to canonical, `sketch:4471v3` to a specific
version. Nothing ever 404s.

Repo: `site/`, `archive/`, `archive-example/`, `services/citecheck`, `packages/rubrics`,
`design/`, `docs/`, `rfcs/`, and `attic/` (the retired dynamic stack). `rubrics` and
`citecheck` must stay standalone, since they are how outside contributors find the
project.

**Build the diff viewer before any visual polish.** Here that means pre-rendered static
diff pages between versions, generated at build time. Seeing exactly what a human had to
change to make a model's paper correct is the content of the site.

---

## 12. Open source

- **Code: AGPL-3.0.** Prevents a closed hosted fork of your own work. Apache-2.0 if
  frictionless institutional adoption matters more, accepting the risk.
- **Verification records and metadata: CC0.** They are facts about the corpus.
- **Paper content: submitter-chosen** from a short list, CC-BY default.
- **Released dataset: CC-BY**, with a DOI and citation string.

**Governance:** BDFL to start — pretending otherwise at n=1 wastes time. DCO sign-off,
not a CLA. An **RFC process for anything touching tiers, rubrics, or the credit ratio**,
because those are the scientific instrument and changing them silently invalidates
comparison across time. Rubrics are versioned and every verification records which
version it used. Move to a steering committee with per-field rubric maintainers at
roughly 20 active contributors.

---

## 13. Build sequence

Detail in `BUILD-PLAN.md`, rewritten on 2026-09-14 for the static architecture.

| | Milestone | Note |
|---|---|---|
| S0 | Static site and prelaunch deploy on garleak.org | Spec, stages, about, call for verifiers, example archive at `/example/` |
| S1 | Archive format, validation, v1 immutability guard in CI | Slow down here. Retrofitting is near-impossible once data exists. |
| S2 | Submission through issue forms, automated pre-screen, credit ledger | Pre-screen ships with submission, not after. |
| S3 | Verification through issue forms, rubric items, anti-gaming, standing | |
| S4 | Stamped PDFs, diff pages, digests and feeds | |
| S5 | citecheck, released as `garleak-citecheck` | Parallelizable. Release standalone early. |
| S6 | Fixes, sketch promotion, graduation, moderator queue, features, leaderboard | Never ship the leaderboard before S3's anti-gaming. |
| S7 | Zenodo DOIs, dataset export, final terms, seeding | |

---

## 14. Launch

**Seed before opening.** 50 papers and 50 sketches, verified by hand. An archive that
launches empty stays empty. Astronomy only for now, across its subsections (galaxies,
cosmology, stars, planets, high-energy, instruments and data), because it is the
maintainer's own field, it verifies cheaply and semi-mechanically, and the people who
will check the first submissions are in it. One category takes everything else, and the
tree for other fields is written when enough records arrive to need one. Hide any
category below a threshold rather than showing an empty shelf.

**Positioning copy.** The instinct to market on "free and easy" is wrong here: arXiv is
free, every preprint server is free, and leading with it primes people to read the whole
thing as low-value. Worse, it omits verification, which makes you sound like a dumping
ground — the exact reputation that kills the project.

The real exchange is that someone will check whether your thing holds up. Lead with the
drawer problem: everyone has a half-finished thing that will otherwise die.

> You started something with an AI and never finished it. Post it, and someone will check
> whether it holds up.

> Half-finished, unverified, probably wrong? That's the point. Post it and find out which
> part.

Signup line, stated plainly so the credit requirement never feels like a bait:

> Every paper here says which model wrote it and who checked it. Post yours, check two
> others.

On the sketch submission page, defuse the scooping fear directly: the timestamp is a
public, permanent precedence record with your name on it, and promoting a sketch into a
paper credits its author by enforced backlink. Without both, you get only the ideas people
don't care about.

---

## 15. Growth

- **Model leaderboard** — verified-reproduction rate and fabricated-citation rate by
  model, field, and version, autonomous track kept separate. This travels far beyond your
  user base. The papers aren't the story; the aggregate is.
- **Verified failures** — an archive of where models confidently broke. Useful, homeless
  elsewhere, and more fun to read.
- **Dataset releases** with DOIs. Prompts, outputs, verdicts, version histories. Citable,
  and citations bring people back.
- **Bounties** on individual papers, reputational or small-sum.
- **A workshop track** at a real conference, so contributing counts on a CV.
- **The monthly feature** as a predictable press hook. "A language model produced a
  result two independent researchers reproduced" is a story on a schedule.

---

## 16. What to measure

Submissions are a vanity metric — submission is free and therefore meaningless. Track:

- **Verification ratio** — verifications per submission. Sustained below 1.0 means the
  credit ratio is wrong.
- **Time to T1**, median. The health metric for the whole system.
- **Fraction above T0.** Below roughly half and it has become the slop dump.
- **Repeat verifier rate** at 30 days.
- **Median edits from v1 to T3** — the headline research output. The human cost of making
  AI output correct. Nobody has this.
- **Declared-versus-predicted assistance gap**, tracked over time.
- Fabricated-citation rate by model, across model releases.

---

## 17. Money

Hosting costs nothing. GitHub Pages serves the site, GitHub Actions builds it (free for
public repositories), Zenodo holds files and mints DOIs, the ORCID public API checks
identity links, and Namecheap's free email forwarding delivers contact@garleak.org. The
domain is the only cost. Citation checking calls free public APIs such as Crossref,
DataCite, and arXiv, with caching and rate limits so it stays within their usage
policies. Limits and alternatives are in `docs/HOSTING.md`.

Funding, roughly in order of fit: Sloan or Moore for open scientific infrastructure; NSF
infrastructure programs; institutional hosting from a university library, which is how
most preprint servers actually survive; unrestricted sponsorship from model developers,
who want this evaluation data — take it only with no influence over rubrics, and say so
publicly.

---

## 18. Risks

| Risk | Mitigation |
|------|-----------|
| Slop flood at launch | Credit economy from day one, never bolted on later |
| Nobody verifies | Credits, automated T1 pre-check, bounties, recognition for verifiers |
| Verification rings | Loop detection, rate limits, affiliation rules at T4 |
| Citation laundering | `noindex` at T0, stamped PDFs, tier in metadata |
| Drift — papers edited until good, measuring nothing | Immutable v1, `pct_original` always shown |
| Harmful content acted on | Gated categories, T1 before public indexing |
| Read as a predatory journal | Archive framing, never "published", explicit not-peer-review language |
| Trademark | No arXiv string, no arXiv trade dress |
| Classifier misuse against non-native speakers | No penalty for high AI use, confidence intervals shown, contests recorded, never overrides declaration |
| Founder burnout | Governance handoff planned before it is needed |
| Screening becomes the bottleneck | Automated first pass from S2; under 10% reaching a human; per-field moderators earning credits |
| Screening mistaken for endorsement | "Admitted never means endorsed" in terms, submission page, and paper header |

---

## 19. First 30 days

1. The domain `garleak.org` was ordered at Namecheap. On 2026-09-14 it was not yet in
   the .org registry, so confirm the order went through. The GitHub name `garleak`
   belongs to an unrelated user account, so the project uses the organization
   `garleak-org`. Run the trademark search if it has not been done.
2. Publish `SPEC.md` — sections 3 through 7 above — as a public document and circulate
   it for comment. The spec is the actual contribution; code is downstream. The people
   who reply are your first contributors.
3. Build and release `citecheck` standalone. It is useful to people who will never touch
   the platform, and it is the cheapest way to find collaborators.
4. Write the two starting rubrics, computational and mathematics, as versioned YAML.
5. Recruit five verifiers by name before writing a line of frontend. If you cannot find
   five people who will check a paper for free, that is the finding, and it is better to
   learn it now.
