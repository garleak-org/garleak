# Contributing to Garleak

Thanks for helping. This page covers sign-off, the RFC rule, the standalone packages, and
what a pull request needs before it can merge. Posting a paper or a sketch, or verifying
one, goes through the issue forms once they open, not through a hand-written pull
request.

## Sign off every commit (DCO)

Garleak uses the [Developer Certificate of Origin](https://developercertificate.org/),
not a contributor license agreement. By signing off you state that you wrote the change,
or otherwise have the right to submit it under the project's license.

Add the sign-off with `git commit -s`. It appends a line like this, using your git name
and email.

```
Signed-off-by: Your Name <you@example.org>
```

CI checks every commit in a pull request. The sign-off must match the commit author. To
fix commits you already made, run `git rebase --signoff main` and force-push your branch.

## Changes that need an RFC

Open an RFC before writing code for anything that touches

- the verification tiers (T0 to T4) or the novelty stages (N0 to N3),
- a rubric, including wording changes to a rubric item,
- the credit ratio or how credits are earned and spent,
- the other parts of the instrument that `SPEC.md` §10.1 lists, such as the assistance
  axes (writing W0 to W3, analysis A0 to A2) and the `pct_original` algorithm.

These are the scientific instrument. If they change silently, a T2 from this year and a
T2 from last year stop meaning the same thing, and the archive's longitudinal data loses
its value. Rubrics are versioned, and every verification records the rubric version it
used. See [rfcs/README.md](rfcs/README.md) for the process. If you are unsure whether a
change needs an RFC, assume it does and ask in an issue.

## Standalone packages

`packages/rubrics` and `services/citecheck` are separate packages with their own
maintainers, tests, and release cycles. They must never import from `site/` or from
anything else in this repository. They are how many people first find the project, so
they should install and run on their own. Send changes to them as pull requests against
those directories, and follow the README in each.

## Before you open a pull request

- Generator and template changes in `site/` pass the checks listed in `site/README.md`,
  which are the same checks the `site.yml` workflow runs.
- citecheck changes pass `pytest -m "not network"` in `services/citecheck`. Rubric
  changes pass `python scripts/validate.py` and `pytest` in `packages/rubrics`.
- Records under `archive/` validate against `archive/FORMAT.md`. No change edits an
  existing v1, and CI rejects one that does.
- Invented example records go only in `archive-example/`, which the site shows under
  `/example/` with a banner and `noindex`.
- The invariants in [CLAUDE.md](CLAUDE.md) still hold. The short version is that v1
  never changes, verifications attach to versions, the assistance axes and their three
  signals are never merged, failed verifications stay visible, and T0 and gated content
  carry `noindex`.
- User-facing text never calls Garleak a journal, a preprint server, or peer review, and
  never says "published". Use Verified, Graduated, and admitted.
- No real credentials anywhere. Tokens that workflows need live in repository secrets.

## Visual design

Colors, type, and spacing come from `design/` (the tokens in `design/tokens.css`). Do not
pick them by hand in a template. The brief is in [DESIGN.md](DESIGN.md).

## License

Code in this repository is licensed AGPL-3.0-or-later ([LICENSE](LICENSE)), and your
signed-off contribution is made under it. Rubric YAML, the specification, and
verification records are CC0. The README lists every license the project uses.

## Governance

The project starts with a single maintainer who makes final calls. When there are
roughly 20 active contributors it moves to a steering committee with per-field rubric
maintainers. Accepted RFCs are the record of every decision that affects the instrument.

## Security and takedowns

Report security problems privately to contact@garleak.org rather than in a public
issue. (The address forwards through Namecheap once it is set up, see
[docs/HOSTING.md](docs/HOSTING.md).) A named contact and a takedown path will be listed
here before launch.
