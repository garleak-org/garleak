# RFC 0001: Static architecture

- **Status:** accepted by the maintainer, 2026-09-14
- **Author(s):** the Garleak maintainer
- **Created:** 2026-09-14
- **Affects:** infrastructure, and through it identity, visibility, and record storage.
  No tier, stage, rubric, or credit amount changes.
- **Discussion:** none yet. The repository has no public remote, so the usual 14-day
  discussion did not happen. The maintainer accepted this directly, as the single
  maintainer may at this stage (`CONTRIBUTING.md`, Governance). Comments are still
  welcome once the repository is public.

## Summary

Garleak becomes a static site in the style of arXiv's listing and abstract pages. The git
repository is the database, with every object and record kept as a YAML or Markdown file
under `archive/`. A Python generator in `site/` builds the HTML, and GitHub Actions
deploys it to GitHub Pages at `garleak.org`. In Phase 1, submissions and verifications
arrive through GitHub issue forms that Actions turns into pull requests, and identity is
a GitHub account linked to an ORCID record. Hosting costs nothing beyond the domain. An
optional Phase 2 adds a free Cloudflare Worker with ORCID sign-in so that submitter
identity can stay private.

## Motivation

The first milestone of the dynamic plan (FastAPI, PostgreSQL, Celery and Redis,
Typesense, MinIO, Next.js, Docker Compose) worked locally, but running it in public
needs a server, a database with backups, a job queue, object storage, and a search
service. Each costs money every month and needs someone to patch and watch it. At one
maintainer, with no funding, that is the most likely way for the project to stall.

A static site fits the design brief better as well. The brief asks for dense,
text-first pages with near-zero JavaScript that work without scripts and load fast. A
generator that writes plain HTML meets that directly.

Keeping records in git gives an audit trail for free. Every change to a record is a
commit with an author and a date, and the immutability of v1 can be checked in CI
against a stored content hash. The archive's dataset is the repository itself, which
anyone can clone.

## The change

1. **Records.** Papers, scratches, versions, verifications, novelty checks, fixes,
   screening decisions, and credit events are files under `archive/`, in the format
   documented in `archive/FORMAT.md`. Invented examples live only in
   `archive-example/` and render under `/example/` with a banner and `noindex`.
2. **Generator.** A Python package in `site/` validates the records and writes the
   static site (listings, `/abs/` pages, pre-rendered diffs, digests, Atom feeds).
   Search is a Pagefind index built with the pages.
3. **Hosting.** GitHub Pages, deployed by a custom Actions workflow (`site.yml`), with
   the custom domain `garleak.org`. DNS stays at Namecheap. HTTPS comes from GitHub
   Pages. Details in `docs/HOSTING.md`.
4. **Intake, Phase 1.** Issue forms for submission, verification, and the other
   actions. An Actions workflow validates the form, runs the automated pre-screen, and
   opens a pull request with the new records. Screening a paper is reviewing and
   merging that pull request. A scratch merges automatically once the automated checks
   pass.
5. **Identity, Phase 1.** A GitHub account plus an ORCID link. The link is verified by
   reading the person's public ORCID record through the ORCID public API and checking
   that it lists their GitHub profile URL. No server is needed. Where ORCID coverage is
   thin, a moderator verifies an institutional email address by hand through the
   contact address.
6. **Files.** PDFs and figures live in the repository at first. Zenodo later holds
   files and mints DOIs for Graduated versions, with a version DOI and a concept DOI.
7. **Phase 2, optional and free.** A Cloudflare Worker with ORCID OAuth accepts
   submissions and commits them with a bot token, so neither the submitter's GitHub
   account nor their ORCID link appears in the public record.
8. **Retirement.** The dynamic M0 stack moves to `attic/dynamic-m0/`, with a note on
   what it was and what may be reused.

### Identity decision

Decided 2026-09-14. Garleak opens with Phase 1 and adds the Worker later. The record
format does not depend on this, since the Worker will commit the same records that the
issue-form workflow commits.

## Trade-offs, stated plainly

- **GitHub handles are public.** Every Phase 1 action is made from a GitHub account, so
  the handle is public on every record it creates.
- **The ORCID link is public.** Verification works because the ORCID record lists the
  GitHub URL, so anyone who looks can connect a verified account to a real name. That
  breaks the promise "We know who you are. Nobody else does" for pseudonymous scratches
  and papers. Only accounts verified by institutional email keep their identity out of
  public view. The copy must say this in Phase 1 (`SPEC.md` §3.7).
- **Restricted data cannot stay restricted.** The credit ledger follows from public
  records, so anyone can compute any balance (`SPEC.md` §5.2.6 cannot hold). A
  community vote cast through GitHub shows its voter.
- **Issues are public when opened.** A paper is visible on GitHub before it is screened,
  though the site shows it only after merge. Gated submissions should not come in
  through public issue forms at all (`SPEC.md` §3.7.7, OQ-24).
- **Limits.** GitHub Pages recommends a source repository under 1 GB, caps a published
  site at 1 GB, and has a soft bandwidth limit of 100 GB a month. GitHub blocks files
  over 100 MiB. PDFs will have to move to Zenodo well before the archive is large.

## Comparability across time

No stage, rubric, credit amount, or ratio changes, so a T2 recorded under this
architecture means exactly what a T2 meant before it. The archive held no records before
the change, so no metric in master plan section 16 becomes discontinuous.

If intake later moves from issue forms to the Worker, the move could change who submits
(people who wanted privacy may wait for it). Records SHOULD therefore carry the intake
path that created them (for example issue form or Worker), so that the dataset can mark
the date of the change and any analysis can split on it.

## Existing records

None existed. The M0 code is kept, unchanged, in `attic/dynamic-m0/`.

## Alternatives considered

- **Keep the dynamic stack.** It gives private identity and restricted data from day
  one, at the cost of a server, a database, and an operator. Rejected for now. Parts of
  it (ORCID OAuth, the `noindex` helper, the branding check) may inform Phase 2 and the
  generator.
- **Cloudflare Pages from the start.** Unlimited static bandwidth and the Worker in the
  same account, but serving the apex domain needs the domain's DNS moved to Cloudflare.
  Kept as the move to make when the Worker is built or bandwidth becomes a problem.
- **Worker from the start.** Solves the identity trade-off before anyone is exposed to
  it, and delays opening. Not chosen. Phase 1 opens first and the Worker follows.
- **Netlify, Codeberg Pages, Vercel.** Compared in `docs/HOSTING.md`. Netlify's free
  plan pauses every site when its monthly credits run out. Codeberg Pages would suit an
  open project but separates hosting from the GitHub issue forms and Actions that Phase
  1 relies on. Vercel's Hobby plan is for non-commercial personal use only.

## Open questions

- When PDFs move from the repository to Zenodo, and whether versions below Graduated
  get Zenodo records for file storage without a DOI being shown as a citation.
