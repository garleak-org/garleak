# garleak-rubrics

The checklists Garleak verifiers work through, as versioned YAML. A rubric says what a
verifier checks at each tier, what counts as pass, fail, or not applicable, what evidence
to attach, and which parts a tool can help with.

This package is standalone. It has no dependency on the rest of the repository, so you
can read, use, or propose changes to the rubrics without running the platform. The
definitions of tiers, verifications, and versions it relies on are in
[SPEC.md](../../SPEC.md), mainly sections 2.4, 4.2, and 10.3.

## What is here

| Path | What it is |
|---|---|
| `citations/v1.0.0.yaml` | T1, citations. Universal across every field and always the first tier. |
| `computational/v1.0.0.yaml` | T2 to T4 for results that come from running code. |
| `mathematics/v1.0.0.yaml` | T2 to T4 for theorems with proofs. For a proof, reproduction means independent re-verification of the argument. |
| `schema/rubric.schema.json` | JSON Schema every rubric file must satisfy. |
| `scripts/validate.py` | Validator for the schema and the rules below. |
| `tests/test_rubrics.py` | Tests for the files and the validator. |

All three rubrics are drafts (`status: draft`), circulated with SPEC.md 0.1 for comment.
They become `active` when an RFC adopts them.

## Running the checks

```sh
cd packages/rubrics
python3.12 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python scripts/validate.py
.venv/bin/pytest
```

`validate.py` with no arguments checks every rubric in this directory. Pass file or
directory paths to check others. It exits 0 when clean and 1 otherwise.

## Versioning

The tiers and rubrics are the scientific instrument. If they change silently, a T2 from
this year cannot be compared with a T2 from next year. So the rules are strict.

- **Rubric changes go through an RFC.** Use the template in [rfcs/](../../rfcs/). An
  accepted RFC names the new version and the date it takes effect.
- **Every verification records the rubric id and version it used**, for example
  `computational@1.0.0`. New verifications use the current active version. Old
  verifications keep their version and are never re-scored.
- **A new version is a new file.** Copy `v1.0.0.yaml` to `v1.1.0.yaml` (or whatever the
  bump is) and edit the copy. Once a version is `active`, its file does not change. A
  draft may be edited in place during its comment period.
- **Items are never renumbered, removed, or reused.** An item id such as
  `comp.T2.env-declared` means the same check forever. To retire an item, set its
  `deprecated_in` to the version that retires it, and `replaced_by` if something replaces
  it. The item stays in the file.
- **Semantic versions have fixed meanings.**
  - MAJOR changes the pass, fail, or not-applicable criteria of an existing item, changes
    whether an item is required, adds a required item, or deprecates an item.
  - MINOR adds an advisory item, or clarifies wording without changing any criterion.
  - PATCH fixes typos or formatting.
- **The changelog keeps its history.** Add a new entry at the top and leave the old ones
  as they were.

The validator enforces the parts of this that can be checked by machine. It fails if an
item disappears between versions, changes tier, has its deprecation undone, or has its
criteria changed without a MAJOR bump, or if a required item is added without one.

## File format in brief

Each file names its rubric (`id`, which must match the directory), the rubric family
(`field`, or `universal` for citations), the tiers it covers, its version and status, the
SPEC version it was written against, its maintainers, a summary, what each tier means for
this family, definitions of terms, a changelog, and the items.

Each item has a stable id of the form `<prefix>.<tier>.<slug>`, the tier it gates,
whether it is required or advisory, a prompt for the verifier, pass, fail, and
not-applicable criteria (`not_applicable: null` means the item is never not applicable),
the evidence to attach, and an automation note. Automation is `none` or `partial`. No item
is fully automated, because the human verifier owns every verdict. Items checked over a
sample carry a `sampling` block. The one in this version, `cit.T1.supports-sample`, is a
proposed default and open for comment.

## Licenses

The rubric YAML files and the schema are dedicated to the public domain under CC0 1.0,
like the specification and the verification records. The validator and tests are under
the repository's AGPL-3.0 license.
