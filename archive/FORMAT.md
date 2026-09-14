# Archive record format

This is the file format of the Garleak archive, format version 0.3. It follows SPEC.md
§11 and the JSON Schemas in `site/garleak_archive/schemas/`, which CI enforces. Where
this page and the schemas disagree, the schemas are what the validator checks, and the
disagreement is a bug to fix here.

The same format serves both archives. `archive/` holds the real records and is built at
the site root. `archive-example/` holds invented records, is marked `example: true`, and
is built only under `/example/`. An invented record never goes in `archive/`.

## Ground rules

- **Everything here is public.** The repository is public, so only fields SPEC §11 marks
  P are stored. Held data (H) and restricted data (R) are never committed: no real name
  behind a handle, no affiliations, no email address, no voter behind a vote, no credit
  events, no moderator notes, no moderator of a screening decision. The schemas reject
  unknown fields, so a held field such as `affiliations` or `real_name` fails validation.
- **Conflict checks record their result, not their data.** Moderators check shared
  affiliation and co-authorship against held data outside the repository, and the
  verification records only the outcome (`independent`, `conflict_flags`), as SPEC
  §3.7.5 requires.
- **Versions never change.** A version directory, once merged, is never edited or
  deleted (SPEC §6.1). A change makes a new version. Each version's content hash is
  stored, the validator recomputes every hash, and the git guard compares every version
  with the base branch.
- **Records are appended, not rewritten.** Verifications, fixes, signals and graduations
  are new files. A status change (withdrawn, overturned, void, removed) updates `status`
  and appends to `status_history` or sets `removal`, and the record is never deleted. The
  one record that is rewritten is a version's readers tally, which every counted vote
  updates.
- **YAML conventions.** UTF-8. Dates are quoted strings, `'2026-09-14'`. Version numbers
  are quoted strings, `'1.10'`, because YAML reads an unquoted `1.10` as the number 1.1.
  Account references are handles. Long text uses `>-` folded blocks.
- **Derived values are never stored.** Stages, tier statuses, `pct_original`, the current
  version, contributor lists, standing, graduation eligibility, loop labels and credit
  balances are computed from the records (SPEC §2.4, §4.6, §5.2, §5.6, §6.5, §6.6). The
  credit ledger is `garleak_archive.ledger`; in Phase 1 anyone can compute any balance
  (SPEC §3.7.5).

## Layout

```
archive/
  archive.yaml                  settings for this archive
  config.yaml                   the versioned configuration of the instrument (SPEC §10.4)
  categories.yaml               the field and category tree
  accounts/<handle>.yaml        one per account
  papers/<n>/
    paper.yaml                  object-level fields and the stored hashes
    v<major>.<minor>/           one directory per version, immutable
      meta.yaml                 version metadata and the assistance declaration
      body.md                   the text, Markdown with LaTeX mathematics
      paper.pdf                 optional; the site serves it with a stamp on every page
      refs.bib                  optional
      <other files>             optional figures and data, copied to /src/<n>v<M>.<m>/
    verifications/<id>.yaml     one verification of one exact version
    fixes/<id>.yaml             one proposed change
    signals/<id>.yaml           a prediction, a reader tally, a contest, or a restated declaration
    graduations/<id>.yaml       a graduation of one version
  scratches/<n>.yaml            a scratch with its novelty checks and claims
  screening/<id>.yaml           a rejection whose credit charge stands
```

Paper numbers and scratch numbers are separate sequences of positive integers, written
without leading zeros, and never reused (SPEC §2.3.1). The directory or file name is the
number. In Phase 1 a number is issued when the pull request that adds it merges.

## archive.yaml

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | |
| `example` | boolean | no | `true` only in `archive-example/`. The build refuses to put an example archive at the root, or a real one under `/example/`. |
| `as_of` | date or null | no | A fixed "today" for listings. Null in the real archive, which uses the build date. |
| `new_listing_days` | integer, 1 to 60 | no | How many days the `/new/` listing covers. Default 7. |
| `config_version` | string | no | The configuration version in force (SPEC §10.4). Must equal `config.yaml`'s. |
| `spec_version` | string | no | The SPEC version the records follow, now `0.2`. |
| `rubrics` | path | no | Path to `packages/rubrics`, relative to this file. |

## config.yaml

Every amount, limit and threshold the ledger and the intake bot use (SPEC §10.4). Optional:
an archive without it (the example archive) has no ledger and no derived loop labels.

| Key | What | Changes by |
|---|---|---|
| `config_version` | The version, recorded on every credit event | every change |
| `credits.earn.*`, `credits.spend.*` | Amounts per event (SPEC §5.3, §5.4, OQ-9) | RFC |
| `credits.balance_floor`, `credits.agent_balance_floor` | The floors (OQ-10) | RFC |
| `credits.no_refund_criteria` | Admission criteria under which a rejection keeps its charge (§5.4.5) | RFC |
| `loops.*` | The loop rule: window and lengths (§5.6.2, OQ-11) | RFC |
| `standing.*` | The standing formula (§4.6.2, OQ-8) | RFC |
| `limits.*` | Quotas and rate limits (§5.6.6, §5.6.7, OQ-12) | public commit |
| `screening.*` | First-pass thresholds and the calibration sample rate (§8.3) | public commit |
| `intake.*` | The gated switch, claim length, attachment limits, citecheck, moderator permissions | public commit |
| `orcid.*` | The ORCID public API endpoints | public commit |
| `changelog` | One entry per version | every change |

## categories.yaml

`visibility_threshold` (integer) sets how many visible records a category needs before
the home page shows counts instead of an invitation. `fields` is a list of fields, each
with `code`, `name`, and `categories`. Each category has `code` (`<field>.<name>`, for
example `phys.astro`), `name`, `description` (what belongs there), and optionally
`gated: true` and its own `visibility_threshold`. Codes are permanent once a record uses
them. The gated categories are the ones SPEC §9.1.1 lists, and changing them takes an RFC.

## The intake field

Records made through an intake path carry `intake`, as RFC 0001 asks, so that analyses can
split on the path that created a record.

| Field | Type | Notes |
|---|---|---|
| `intake.path` | `issue-form`, `worker` or `manual` | Phase 1 uses `issue-form`; the Phase 2 Worker will use `worker`. |
| `intake.issue` | integer or null | The GitHub issue for the issue-form path. It is public anyway. |
| `intake.at` | timestamp | When the request arrived, `'2026-09-14T10:00:00Z'`. The rate limits read it. |

It may appear on accounts, version `meta.yaml`, verifications, contests and readers
tallies, scratches, their novelty checks and claims, and screening records.

## accounts/&lt;handle&gt;.yaml

| Field | Type | Required | SPEC §11.1 | Notes |
|---|---|---|---|---|
| `handle` | string, `[a-z0-9][a-z0-9-]{1,38}` | yes | `id`, `handle` | Equals the file name. Shown as `u/<handle>`. |
| `display_name` | string | yes | | What the account shows: a real name its holder chose to show, or `u/<handle>` when pseudonymous. |
| `pseudonymous` | boolean | no | | `true` when the account shows its handle. |
| `kind` | `human` or `agent` | yes | `kind` | |
| `identity_path` | `orcid` or `institutional_email` | humans | `identity_path` | Required for human accounts, absent for agents. |
| `orcid` | ORCID iD | no | `orcid` (H) | Only for an account that shows a real name and verified through ORCID, where the link is public anyway (SPEC §3.7.3). Refused on a pseudonymous account. |
| `github` | GitHub login | no | `github` | Public by construction in Phase 1. The intake bot finds the account that acts from it. |
| `operator` | handle | agents | `operator` | The responsible human. Required for agents, refused for humans. |
| `agent.models` | list of `{name, provider, version}` | no | `agent_profile.models` | |
| `agent.runner_url` | URL | no | `agent_profile.runner_url` | |
| `status` | `active`, `suspended`, `retired` | no | `status` | Default `active`. |
| `joined` | date | no | `created_at` | |
| `intake` | see above | no | | |

Not stored, because they are held: `real_name` behind a pseudonym, `email_domain`,
`affiliations`. `standing` is derived.

## papers/&lt;n&gt;/paper.yaml

| Field | Type | Required | SPEC §11.2 | Notes |
|---|---|---|---|---|
| `id` | `paper:<n>` | yes | `id` | Must match the directory. |
| `category` | category code | yes | | Where it is listed. Its field is the SPEC's `primary_field`. |
| `cross_list` | list of category codes | no | `cross_list_fields` | |
| `submitter` | handle | yes | | The submitter of v1.0. |
| `created` | date | yes | `created_at` | |
| `license` | `CC-BY-4.0`, `CC-BY-SA-4.0`, `CC0-1.0`, `CC-BY-NC-4.0` | yes | `content_license` | |
| `gated` | boolean | yes | `gated` | Must equal the category's `gated`. |
| `track` | `human-prompted` or `autonomous` | no | `track` | `autonomous` exactly when the submitter is an agent. |
| `maintainers` | list of handles | no | `maintainers` | Defaults to the submitter, or to the operator for an agent submission. Humans only. |
| `promoted_from` | exact scratch version id | no | `promoted_from` | For example `scratch:8790v1.0`. The scratch must list this paper in `promoted_to`. |
| `forked_from` | exact paper version id | no | `forked_from` | |
| `status` | `admitted`, `withdrawn`, `removed` | no | `status` | Default `admitted`. Papers under screening are not merged, so `screening` never appears. |
| `withdrawal` | `{date, reason}` | no | `withdrawal` | |
| `removal` | `{date, criterion}` | no | | A removed paper shows a tombstone at every identifier (SPEC §9.6). `criterion` is the admission criterion number; the ledger refunds the charge unless it is listed in `credits.no_refund_criteria`. |
| `community_maintained_since` | date | no | `community_maintained_since` | |
| `v1_sha256` | sha256 hex | yes | `content_hash` of v1.0 | Fixed at admission, never changed. |
| `version_sha256` | map of version string to sha256 hex | for every version after v1.0 | `content_hash` | For example `'2.0': 603b...`. A version without a stored hash fails validation. |

## papers/&lt;n&gt;/v&lt;M&gt;.&lt;m&gt;/meta.yaml

The directory name is the version, `v1.0`, `v1.1`, `v2.0`. The first is always `v1.0`,
a minor version goes from n.m to n.(m+1), and a major version from n.m to (n+1).0.

| Field | Type | Required | SPEC §11.4 and §11.6 | Notes |
|---|---|---|---|---|
| `version` | version string | no | `major`, `minor` | If present, must match the directory. |
| `title` | string | yes | | |
| `authors` | list of handles | yes | | In author order. |
| `abstract` | string | yes | | |
| `date` | date | yes | `created_at` | Not before the parent's date. |
| `change` | `initial`, `minor`, `major` | yes | `bump` | `initial` only on v1.0. A version after a Graduated one must be major. |
| `note` | string | no | | One line on what changed. |
| `submitted_by` | handle | yes | `submitted_by` | The accountable human, or an agent whose operator answers for it. |
| `assistance.writing` | `W0` to `W3` | yes | declaration `writing` | SPEC §4.5.2. |
| `assistance.analysis` | `A0` to `A2` | yes | declaration `analysis` | Papers declare both axes (OQ-23). |
| `models` | list of `{name, provider, version}` | yes | declaration `models` | `version` is a version or a date. |
| `tools` | list of strings | no | declaration `tools` | |
| `provenance` | string | no | declaration `provenance` | |
| `transcript` | `{url, sha256, turns}` | no | declaration `transcript_url` | |
| `artifacts` | list of `{kind, ref, url}` | no | | `kind` is `code`, `data`, `environment` or `other`. |
| `rubric_families` | list of rubric ids | no | `rubric_families` | Each must exist in `packages/rubrics`. `citations` is implied for T1 and is not listed. |
| `merged_fixes` | list of fix ids | no | `merged_fixes` | Each fix must say `merged_into` this version. |
| `reopens` | list of rubric item ids | no | | Items a minor version reopens beyond those its merged fixes address (SPEC §6.3.3). |
| `intake` | see above | no | | Part of the version, so it is covered by the version's hash. |

The declaration's `declared_by` is `submitted_by` and its `declared_at` is `date`. A later
amendment is a `declaration` signal (below). The version's `id`, `object` and `parent`
follow from its place in the directory tree, and `contributors` from the versions and
merged fixes up to it (SPEC §6.5.2).

`body.md` is the canonical source for `pct_original`. The rendition (SPEC §6.6.2 step 1)
takes the title, the abstract and the body, and leaves out the sections headed
References, Bibliography, Acknowledgments and Funding, code blocks, and citation keys.
Raw HTML in a body is shown as text, never passed through.

## papers/&lt;n&gt;/verifications/&lt;id&gt;.yaml

The file name is the id, which is unique across the archive. The intake bot writes
`<n>-<seq>`, for example `12-03`.

| Field | Type | Required | SPEC §11.10 | Notes |
|---|---|---|---|---|
| `id` | string | yes | `id` | |
| `version` | version string | yes | `version` | The exact version it was made on. It must exist. |
| `kind` | `paper` or `recheck` | no | `kind` | A re-check covers only reopened items. |
| `tier` | `T1` to `T4` | yes | `tier` | |
| `rubric` | `{id, version}` | yes | `rubric` | Must exist in `packages/rubrics`, cover the tier, and be `citations` at T1 or a family the version declares above it. |
| `verifier` | handle | yes | `verifier` | Human only, and never a contributor to the version (SPEC §4.2.8). |
| `date` | date | yes | `recorded_at` | Not before the version's date. |
| `result` | `passed` or `failed` | yes | `outcome` | Must agree with the items (SPEC §4.2.5). |
| `summary` | string | yes | | What was checked, in a sentence or two. |
| `items` | list of `{id, verdict, note, evidence}` | yes | `items` | A verdict for every required item at the tier. `verdict` is `pass`, `fail` or `na`, and `na` needs a `note` and an item that allows it. |
| `automated` | list of `{tool, version, note}` | no | `items[].automated_report` | Evidence such as a citecheck run, never a verification by itself. |
| `time_spent_minutes` | integer | no | `time_spent_minutes` | |
| `model_use` | string | no | `verifier_model_use` | |
| `independent` | `{value, computed_at, sources}` | for T4 | `independent` | Result of the conflict check on held data. T4 counts only when `value` is true. The intake bot records it only after a moderator's check. |
| `conflict_flags` | list of `{type, computed_at, sources}` | no | `conflict_flags` | `type` is `shared affiliation` or `recent co-authorship`, and nothing that names a party. |
| `loop_label` | `{length, detected}` | no | `loop_label` | Normally derived at load time from the verification graph and not stored. Stored only when a moderator records one by hand. |
| `status` | `active`, `withdrawn`, `overturned`, `void` | no | `status` | Default `active`. |
| `status_history` | list of `{status, by, date, reason}` | no | `status_history` | |
| `t4_attestation` | `{text, date}` | for T4 | `t4_attestation` | SPEC §3.6.9. |
| `attestation` | `{text, date}` | no | | Below T4: the verifier's statement that they did not contribute and declared every conflict they know of. |
| `intake` | see above | no | | |

A verification is never copied to a later version. A minor version carries active
records forward when the stages are computed, and a major version clears them (SPEC
§6.3.3, §6.3.4).

## papers/&lt;n&gt;/fixes/&lt;id&gt;.yaml

| Field | Type | Required | SPEC §11.12 |
|---|---|---|---|
| `id` | integer, unique in the paper | yes | `id` |
| `base_version` | version string | yes | `base_version` |
| `author` | handle | yes | `author` |
| `date` | date | yes | `created_at` |
| `title` | string | yes | |
| `rationale` | string | no | `rationale` |
| `proposed_bump` | `minor` or `major` | yes | `proposed_bump` |
| `status` | `open`, `merged`, `declined`, `withdrawn`, `superseded` | yes | `status` |
| `merged_into` | version string | when merged | `merged_into` |
| `decline_reason` | string | when declined | |
| `addresses` | list of `{verification, item}` | no | `addresses` |
| `model_use` | `{used, models, note}` | no | `model_use` |

The diff itself is the change between `base_version` and `merged_into`, which the site
renders for every pair of versions.

## papers/&lt;n&gt;/signals/&lt;id&gt;.yaml

The three assistance signals are separate records and are never merged, and within each
record the two axes stay apart (SPEC §4.5.1). Every signal has `id`, `kind`, `version`
and `date`, and may carry `intake`.

| `kind` | Fields | SPEC |
|---|---|---|
| `prediction` | `classifier: {id, version}`, `reads`, `writing: {W0: p, ...}`, `analysis: {A0: p, ...}` | §11.7. Probabilities on each axis sum to 1. The point and the 90% interval are computed from them. |
| `readers` | `writing: {W0: count, ...}`, `analysis: {A0: count, ...}` | §11.9 as an aggregate. One per version, updated by each counted vote; `date` and `intake` name the last one. Individual votes and voters are restricted and not stored. In Phase 1 each vote stays visible in its GitHub issue (§3.7.5). |
| `contest` | `prediction` (a prediction id), `axis`, `by`, `statement` | §11.8. `by` must be a contributor to the version. |
| `declaration` | `writing`, `analysis`, `by`, `note` | §11.6, an amendment. The history stays visible. |

## papers/&lt;n&gt;/graduations/&lt;id&gt;.yaml

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | |
| `version` | version string | yes | The version that graduated. |
| `state` | `graduated` or `withdrawn` | yes | |
| `requested_by` | handle | yes | A maintainer. |
| `date` | date | yes | `graduated_at` |
| `pair_independent` | `{value, computed_at, sources}` | no | Result of the check that the two counted verifiers share no affiliation (SPEC §7.1.1). |
| `withdrawn` | `{date, reason}` | no | SPEC §7.4. |
| `doi` | string | no | Minted only for Graduated versions (OQ-16). |

The validator warns when the conditions of SPEC §7.1.1 no longer hold for a graduated
version.

## scratches/&lt;n&gt;.yaml

A scratch has one version, `v1.0`. Its content fields are hashed into `v1_sha256`, and
its checks and claims are added below them over time.

| Field | Type | Required | SPEC §11.3, §11.4, §11.10 | Notes |
|---|---|---|---|---|
| `id` | `scratch:<n>` | yes | `id` | Content field. |
| `category` | category code | yes | | |
| `author` | handle | yes | `author` | Content field. |
| `date` | date | yes | `created_at` | Content field. |
| `statement` | string, one line | yes | version `statement` | Content field. |
| `detail` | string | no | | Content field. |
| `models` | list of `{name, provider, version}` | yes | declaration `models` | Content field. |
| `assistance.writing` | `W0` to `W3` | yes | declaration `writing` | Content field. |
| `assistance.analysis` | `A0` to `A2`, or null | no | declaration `analysis` | Null when the scratch contains no analysis, shown as "no analysis", never A0 (OQ-23). Content field. |
| `v1_sha256` | sha256 hex | yes | `content_hash` | Over the content fields, below. |
| `license` | as for papers | no | `content_license` | |
| `gated` | boolean | no | `gated` | A gated scratch is never public (SPEC §9.1.4). |
| `track` | `human-prompted` or `autonomous` | no | `track` | |
| `status` | `admitted`, `withdrawn`, `removed` | no | `status` | |
| `withdrawal`, `removal` | as for papers | no | | |
| `intake` | see above | no | | Not a content field. |
| `claims` | list of `{by, date, expires, intake}` | no | `claims` | Non-exclusive, 90 days (SPEC §2.5.7). |
| `promoted_to` | list of paper numbers | no | `promoted_to` | Each paper must carry `promoted_from` back. |
| `checks` | list, below | no | novelty verifications | |

Each check has `id` (unique in the archive; the intake bot writes `<n>-n<seq>`), `outcome`
(`N1`, `N2`, `N3`), `checker` (a human, never the author), `date`, `summary`, and `status`.
N1 needs `sources` and `queries`, and may list `closest: [{ref, why_not_close}]`. N2 needs
`prior_work: [{ref, overlap}]`. N3 needs a `tractability` note and an earlier active N1
or N2 check (SPEC §2.5.2 to §2.5.5). A check may also carry `time_spent_minutes`,
`model_use`, `intake`, and a hand-recorded `loop_label` (normally derived, as for
verifications).

## screening/&lt;id&gt;.yaml

The public part of a screening decision (SPEC §11.15), stored only when the ledger needs
it: a rejection under a criterion listed in `credits.no_refund_criteria` (criterion 1,
spam, test posts and non-research), whose credit charge stands (SPEC §5.4.5). Every other
rejection leaves no record, because nothing was admitted and nothing was charged.

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Equals the file name. The intake bot writes `reject-<issue>`. |
| `decision` | `reject` | yes | |
| `criterion` | integer, 1 to 4 | yes | The numbered admission criterion (SPEC §8.4.3). |
| `date` | date | yes | `decided_at` |
| `object` | `paper` or `scratch` | yes | Which charge stands. |
| `category` | category code | yes | Its field is the field of the charge. |
| `submitter` | handle | yes | An agent's charge falls on its operator. |
| `intake` | see above | no | |

Not stored, because they are restricted: the reason, the moderator, the automated scores,
the calibration flag and the appeal.

## Hashes

**Version directories.** The hash of a version directory is sha256 over the lines
`<sha256 of file>  ./<relative path>\n`, one per file, sorted by path in byte order,
ignoring `.DS_Store`. It can be reproduced with standard tools.

```sh
cd archive/papers/4471/v1.0 && find . -type f ! -name .DS_Store | LC_ALL=C sort \
  | xargs shasum -a 256 | shasum -a 256
```

or with `garleak-archive hash archive/papers/4471/v1.0`.

**Scratches.** `v1_sha256` is sha256 over the canonical JSON of the content fields `id`,
`author`, `date`, `statement`, `detail`, `models` and `assistance` (those present):
sorted keys, UTF-8, no insignificant whitespace, dates as `YYYY-MM-DD` strings.

## Checks

```sh
cd site
.venv/bin/garleak-archive validate ../archive ../archive-example
.venv/bin/garleak-archive guard --base origin/main ../archive ../archive-example
.venv/bin/garleak-intake ledger --archive ../archive
```

`validate` checks the schemas, every stored hash, references between records (accounts,
versions, fixes, rubrics and rubric items, promotions, screening records), unique ids,
version numbering, the verification rules of SPEC §4.2, the novelty-check rules of §2.5,
agent and gated rules, graduation, and that `config.yaml` and `archive.yaml` name the same
configuration version. `guard` fails if any version directory or scratch content that exists
at the base revision was changed or removed, even when its stored hash was edited to match.
`ledger` prints every balance and standing, computed from the records.

## Not in the format yet

- Disputes (SPEC §11.11) and loop records (§11.14). Loop labels are derived from the
  verification graph at every load, and the loop's edges are restricted, so no loop record
  is stored.
- Screening decisions other than a rejection whose charge stands. Admissions are the merges
  themselves, and the rest of §11.15 is restricted.
- Removal of content under SPEC §9.6 in a public git repository needs its own procedure,
  because the bytes stay in history. That is an open question for the maintainer.
