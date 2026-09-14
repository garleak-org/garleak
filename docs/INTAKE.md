# Intake, Phase 1

How submissions, verifications and identity links reach the archive while Garleak runs as
a static site (RFC 0001). People open a GitHub issue from a form, a workflow checks it and
opens a pull request that adds records to `archive/`, and the record appears on the site
once the pull request merges. This page is for contributors and for moderators. The rules
behind it are in SPEC.md, mainly §3.7, §4, §5 and §8.

The forms open at launch. Until then the site says so, and nothing here accepts real
submissions.

## What is public

Everything. In Phase 1 the repository, its issues and its pull requests are public.

- Every action is made from a GitHub account, and the handle is public on every record it
  creates (SPEC §3.7.1).
- An issue is public from the moment it is opened, before any screening. The site shows a
  paper only after a moderator merges it, but GitHub shows the issue at once (§3.7.7).
- An ORCID link is public on ORCID's side, so anyone can connect an ORCID-verified GitHub
  account to a real name (§3.7.3). If you need a pseudonym, use the institutional email path.
- A vote on assistance shows who cast it, in the issue. The archive stores only the counts.
- Every credit balance can be computed from the public records by anyone (§3.7.5). Run
  `garleak-intake ledger` to see them.
- Never put an email address, an affiliation or anything private in an issue. Write to
  contact@garleak.org instead. Moderators keep affiliations outside the repository and use
  them only for conflict checks, and only the result of a check is recorded.

## For contributors

### Link your identity (once)

Open the **Link your identity** form.

- **ORCID.** Add `https://github.com/YOUR-LOGIN` to your ORCID record under Websites and
  social links, with visibility set to Everyone. Give your ORCID iD in the form. The bot
  checks the iD's check digit, reads your public record through ORCID's public API, and
  looks for that exact URL. If it is missing, add it and comment `/recheck`.
- **Institutional email.** Choose this path in the form, then write to contact@garleak.org
  from your institutional address and quote the issue number. A moderator checks it and
  comments `/approve-email` on the issue. The evidence never enters the repository.
- **Handle or real name.** A handle-only account shows `u/handle` and may post scratches,
  and papers before graduation (SPEC OQ-1). With a handle-only account the ORCID iD is not
  stored, but ORCID still lists your GitHub account.
- **Agents.** The agent's own GitHub account opens the form, names its operator, and lists
  its models. The operator confirms by commenting `/confirm-operator` on the issue. Agents
  pay from the operator's credits, have tighter quotas, never enter gated categories, and
  every agent submission waits for a person.

A moderator merges every account link. The account can act once it is merged.

### Submit a scratch or a paper

Use **Submit a scratch** or **Submit a paper**. Declare writing (W0 to W3) and analysis (A0
to A2) separately, and every model you used. For a paper, drag a `.md` file into the Body
field if it is long, a `.bib` into References, and a `.pdf` into PDF. v1.0 is kept exactly as
submitted, forever.

A scratch costs 1.5 credits and a paper 2, in the category's field. A new account can submit
one paper per field before it has verified anything. A new version, from **Add a new
version**, costs nothing and is open to the paper's maintainers.

### Verify, and check scratches for novelty

Use **Verify a paper version** or **Check a scratch for novelty**. Name the exact version
(`paper:12v1.0`) and give one line per rubric item:

```
cit.T1.exists | pass | https://example.org/citecheck-report.json | 42 of 42 resolved
cit.T1.supports-sample | na | | the paper cites fewer references than the sample size
```

A pass or fail needs evidence (a link, a log or a commit hash). `na` needs a reason and is
allowed only where the rubric item says so. The result follows from the items. A
verification earns 1 credit whether it passes or fails; a novelty check earns 0.5.

### Everything else

- **Claim a scratch** you mean to test. Claims are non-exclusive and expire after 90 days.
- **Contest an assistance prediction** on a version you contributed to. The contest is shown
  beside the prediction and never removes it.
- **Vote on assistance** for a version you did not contribute to. A later vote on the same
  version replaces your earlier one.
- **Report content or appeal a decision.** Appeals go to a different moderator from the one
  who decided, within 30 days. Private matters go to contact@garleak.org.

### After you open an issue

The bot comments with a table of what it checked, what passed, what did not and why, and
your balance before and after. Every refusal names the rule it rests on. Fix the form by
editing the issue, or comment `/recheck` once the cause is fixed elsewhere (for example after
you have earned credits, or after your account link merged). Records never change once
merged, so editing an issue that is already recorded does nothing.

## What the bot checks

| Check | Refuses or flags | Rule |
|---|---|---|
| The GitHub account is linked to an active Garleak account | refuses | SPEC §3.1, §3.7.2 |
| The form is complete and readable | refuses | the issue form |
| The category exists; gated categories are not accepted in Phase 1 | refuses | §3.7.7 (OQ-24) |
| Agents stay out of gated categories | refuses | §3.4.5 |
| The balance stays at or above the floor (-2.0, or 0 for an agent's operator) | refuses | §5.4.3, §5.4.4 |
| Daily quotas: 3 papers and 10 scratches for a person, 1 and 3 per agent, 2 and 6 per operator | refuses | §5.6.7 (OQ-12) |
| Daily limits: 5 paper verifications and 10 novelty checks | refuses | §5.6.6 (OQ-12) |
| More than 3 records within an hour | flags, never blocks | §5.6.6 |
| The verifier or checker did not contribute and operates no contributing agent | refuses | §4.2.8, §4.4.3 |
| The rubric is the current version and covers the tier; items, evidence and na reasons | refuses | §4.2.4, §10.3.2 |
| T4 needs the moderators' conflict check on held data, and no loop | waits, or refuses | §2.4.7, §3.6.9 |
| A reciprocal loop of 2 to 4 accounts within 180 days | labels, earns nothing | §5.6.3, §5.6.4 |
| Identical or near-identical text (content hash, shingle similarity) | flags | §8.3.1 |
| Empty, truncated or test-like text | flags | §8.3.1 |
| Words that suggest a gated category filed elsewhere | flags | criterion 3 |
| citecheck on a paper's references, when citecheck is installed | flags | §8.3.1 |
| A minor version that touches numbers, mathematics, tables or references | flags | §6.3.6 |
| A random 5 per cent of otherwise unflagged scratches | flags | §8.3.5 |

The automated checks admit or flag. They never reject (§8.3.2), and the assistance
classifier plays no part (§8.3.3). Each automated result carries a check id and version,
and a score where it has one (§8.3.4). All thresholds and amounts live in
`archive/config.yaml`.

## Which requests merge on their own

| Request | Outcome when every check passes |
|---|---|
| Scratch | merges on its own; a moderator may remove it later (§8.2.2) |
| Scratch that was flagged or drawn for the calibration sample | waits for a moderator |
| Paper, new version | waits for a moderator (§8.2.1) |
| Anything from an agent account | waits for a moderator (§8.2.4) |
| Verification at T1 to T3, novelty check | merges on its own |
| Verification at T4 | waits for `/conflict-check`, then merges on its own |
| Claim, contest, vote | merges on its own |
| Account link (ORCID, email or agent) | waits for a moderator, who checks the display name |
| Report or appeal | no pull request; labeled for the moderators |

A merge by the bot happens only after the site checks pass on the pull request and after a
last check that no other run took the same number in the meantime.

## For moderators

Screening checks admissibility, never quality (SPEC §8.1). Recuse from anything you
contributed to or are not independent of (§8.5.3).

- **Admit** a held submission by reviewing and merging its pull request. The team
  `@garleak-org/moderators` owns `archive/papers/` and `archive/accounts/`, so GitHub asks for
  its review.
- **Commands**, as the first line of a comment on the issue (moderators only):

  | Command | Effect |
  |---|---|
  | `/reject N` | Closes the pull request and the issue, citing admission criterion N (1 to 4). Under criterion 1 the credit charge stands, and a `screening/` record keeps it. |
  | `/remove N` | Takes down a merged scratch or paper behind a tombstone, citing criterion N. The charge is refunded unless N is 1. |
  | `/approve-email` | Records that you checked the person's institutional email. Keep the evidence and their affiliations outside the repository. |
  | `/conflict-check independent` | Records that a T4 verifier is independent of every contributor, after checking held affiliation and co-authorship data. Anything else refuses the T4. |
  | `/recheck` | Runs the checks again. The issue's author can use it too. |

  Anything after the command on the same line is for people. The bot never copies it into
  the repository, because a moderator's reason is restricted (§11.15).
- **Appeals** arrive labeled `moderation:appeal`. A different moderator from the one who
  decided reviews each one, with a target of 14 days (§8.4.4).
- **Holds** have a target of 7 days (§8.2.5). Filter issues by `status:held`.

## How it works

`.github/workflows/intake.yml` runs on issues from a form (opened, edited, or re-labeled by
someone other than the author), on slash commands, and when dispatched with an issue number.
It runs the code on the default branch and never checks out a pull request.

1. A shell step collects the issue, its comments, the open pull requests, the author's
   earlier votes and the repository permission of everyone who used a command, with `gh`,
   into files.
2. For identity issues, one step reads the public ORCID record. It is the only step that
   sees the optional ORCID credentials.
3. `garleak-intake process` reads those files, runs the checks, writes the records into the
   working tree, and writes the comment, the pull request texts and the labels to files. It
   holds no token.
4. The records are validated and the immutability guard runs against the default branch.
5. The bot commits them, signed off, to `intake/issue-N`, opens or updates the pull request,
   and dispatches `site.yml` on that branch, because a pull request opened with
   `GITHUB_TOKEN` starts no workflow by itself.
6. For requests that merge on their own, it waits for the site checks, runs
   `garleak-intake check-pr` against the default branch, merges, then dispatches `site.yml`
   on the default branch to redeploy and `intake-sync.yml` to renumber anything that now
   collides.

`intake-sync.yml` runs after every change to `archive/` on main, once a day, and on demand.
It processes again every open intake pull request whose number was taken meanwhile or that
no longer merges cleanly, and rebuilds the site daily. `intake-labels.yml` creates the labels
in `.github/labels.yml`.

Issue text is untrusted. It reaches the workflow only as files that Python reads. No `run:`
line interpolates an issue, comment or label field, every job declares its own
permissions, actions are pinned to major versions, one run per issue at a time, and
`pull_request_target` is never used. `site/tests/test_workflows.py` checks this.

## Repository settings, once the repository exists

1. **Moderators team.** Create `garleak-org/moderators` in the organization, give it write
   access, and add the moderators. Until it exists, CODEOWNERS requires no review.
2. **Labels.** Run the `intake-labels` workflow once (Actions, intake-labels, Run workflow).
3. **Actions.** In Settings, Actions, General: allow GitHub Actions, set workflow permissions
   to read and write, and tick "Allow GitHub Actions to create and approve pull requests".
4. **Branch protection on `main`** (a ruleset or classic protection): require a pull request
   before merging, with required approvals set to 0 and "Require review from Code Owners" on;
   require the status check `build` (from `site.yml`); block force pushes and deletion. Do not
   require the `ci.yml` checks, because they never run on the bot's pull requests. Allow squash
   merging.
5. **Pages.** Source: GitHub Actions (docs/HOSTING.md).
6. **Redeploy after a bot merge.** Nothing to do. `site.yml` deploys on any event from
   `main` except a pull request, so the `workflow_dispatch` the bot sends after a merge
   deploys the site.
7. **Secrets, all optional.** `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET` of a registered
   ORCID public-API client, or `ORCID_READ_PUBLIC_TOKEN`. They raise the ORCID limit from
   25,000 reads a day per IP address, which Actions runners share, to 100,000 per client.
   Nothing else changes without them.

## Running it locally

```sh
cd site
.venv/bin/pip install -e ".[test]"
.venv/bin/garleak-intake process --event event.json --archive ../archive --dry-run
.venv/bin/garleak-intake process --event event.json --archive ../archive --dry-run --offline
.venv/bin/garleak-intake ledger --archive ../archive
.venv/bin/garleak-intake labels
.venv/bin/pytest tests/test_intake_e2e.py
```

`event.json` is a GitHub `issues` event payload, or any JSON with an `issue` object that has
`number`, `body`, `labels`, `user.login` and `created_at`. The body is the markdown GitHub
renders from a form; `garleak_intake.forms.render_body` makes one from answers, as the tests
do. A dry run writes to a temporary copy of the archive and prints the comment, the pull
request and every file it would add. `--offline` skips ORCID and attachments; `--context DIR`
supplies comments, permissions and open pull requests as the workflow collects them.

## Limits of Phase 1

- Gated categories are closed until a private intake exists (`intake.accept_gated`).
- Moderation earns no credit yet. Deriving it from the records would mean storing the
  moderator of each decision, which SPEC §11.15 restricts.
- A number is issued when its pull request merges. A number proposed in a closed pull request
  was never issued.
- Editing a vote issue after it was counted changes nothing. Open a new vote instead.
