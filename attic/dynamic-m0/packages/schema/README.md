# packages/schema

Shared JSON Schemas for Garleak's core objects. Empty at M0.

In M1 this package will hold one schema per core object, following the definitions in
[SPEC.md](../../SPEC.md).

- Paper
- Scratch
- Version
- Verification
- Fix
- Account

The schemas are the single source of truth for object shape. Neither the API nor the web
app defines these objects by hand.

## How the apps consume it

- **API (`apps/api`).** Pydantic models are generated from the schemas (for example with
  `datamodel-code-generator`) into a module the API imports. Request and response models
  build on the generated ones. SQLAlchemy tables are written by hand, since storage shape
  (diffs against v1, figure hashes) differs from the wire shape, but a test checks that
  every schema field has a home in the database.
- **Web (`apps/web`).** TypeScript types are generated from the same schemas (for example
  with `json-schema-to-typescript`) and imported by server components.
- **CI.** A job regenerates both outputs and fails if the committed files differ, so the
  schemas, the Python models, and the TypeScript types cannot drift.

Whether the schemas are written by hand or generated from a single source is decided in
M1. Either way the JSON Schema files in this directory are what gets reviewed.

## Rules

- A change that alters what a tier, stage, or verification means needs an RFC first (see
  [rfcs/README.md](../../rfcs/README.md)).
- Verification objects reference a Version, never a Paper or Scratch directly.
- The three assistance signals (declared, predicted, community) are separate fields.
  There is no combined field, and none may be added.
- Verification and metadata records are released under CC0.
