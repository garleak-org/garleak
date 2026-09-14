import assert from "node:assert/strict";
import { test } from "node:test";

import { robotsFor } from "./robots.ts";

const NOINDEX = { index: false, follow: false };
const INDEX = { index: true, follow: true };

test("T0 is never indexed", () => {
  assert.deepEqual(robotsFor({ stage: "T0", gated: false }), NOINDEX);
});

test("gated content is never indexed, at any tier", () => {
  for (const stage of ["T0", "T1", "T2", "T3", "T4", "N0", "N3"] as const) {
    assert.deepEqual(robotsFor({ stage, gated: true }), NOINDEX, stage);
  }
});

test("unresolved pages are not indexed", () => {
  assert.deepEqual(robotsFor({ stage: null, gated: false }), NOINDEX);
});

test("verified papers and scratches are indexed", () => {
  assert.deepEqual(robotsFor({ stage: "T1", gated: false }), INDEX);
  assert.deepEqual(robotsFor({ stage: "T4", gated: false }), INDEX);
  assert.deepEqual(robotsFor({ stage: "N0", gated: false }), INDEX);
});
