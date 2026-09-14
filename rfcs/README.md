# RFCs

An RFC is required for any change to the verification tiers or novelty stages, to a
rubric, or to the credit ratio. These define what a Garleak tier means. Changing them
without a record breaks comparison across time, which is the main thing the archive
measures. `SPEC.md` §10.1 lists the other parts of the instrument that are proposed to
need an RFC too (the assistance axes, the `pct_original` algorithm, the loop rule, the
independence rule, the standing formula, and the gated categories).

Other changes (code, copy, infrastructure) do not need an RFC. Open an issue or a pull
request instead. The exception is an infrastructure change that alters what records
exist, who can see them, or how identity is verified. Record that as an RFC, as the move
to a static site was (RFC 0001).

## Process

1. Copy `0000-template.md` to `NNNN-short-title.md`, where `NNNN` is the next free
   number. Fill in every section. The section on comparability across time is required.
2. Open a pull request containing only the RFC. Label it `rfc`.
3. Discussion runs for at least 14 days. Rubric changes should be reviewed by at least
   one verifier with standing in the affected field.
4. The maintainer accepts, rejects, or asks for revision. Rejected RFCs are merged with
   status `rejected`, so the reasoning stays on record. Once a steering committee
   exists, it takes over this step.
5. An accepted RFC names the new rubric or tier version and the date it takes effect.
   Verifications made before that date keep the version they used.

## Status values

`draft`, `in discussion`, `accepted`, `rejected`, `withdrawn`, `superseded by NNNN`.

## Index

| RFC | Title | Status |
|-----|-------|--------|
| [0001](0001-static-architecture.md) | Static architecture | Accepted by the maintainer, 2026-09-14 |
