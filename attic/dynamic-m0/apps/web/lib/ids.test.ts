import assert from "node:assert/strict";
import { test } from "node:test";

import { decodeSegment, parseId } from "./ids.ts";

test("canonical paper id", () => {
  const p = parseId("paper:4471");
  assert.equal(p.ok, true);
  if (p.ok) {
    assert.equal(p.kind, "paper");
    assert.equal(p.number, 4471);
    assert.equal(p.version, null);
    assert.equal(p.canonical, "paper:4471");
  }
});

test("versioned ids", () => {
  const a = parseId("paper:4471v3");
  assert.ok(a.ok && a.version?.major === 3 && a.version.minor === null);
  const b = parseId("Scratch:8812V2.1");
  assert.ok(b.ok && b.kind === "scratch" && b.canonical === "scratch:8812v2.1");
  if (a.ok) assert.equal(a.concept, "paper:4471");
});

test("bare numbers are ambiguous, not errors", () => {
  const p = parseId("4471");
  assert.deepEqual(p, { ok: false, reason: "bare-number", number: 4471, input: "4471" });
});

test("malformed ids never throw", () => {
  for (const bad of ["", "paper:", "paper:0", "paper:12v0", "fix:3", "paper:1v1.x", "%%%", "paper:4471v"]) {
    const p = parseId(bad);
    assert.equal(p.ok, false, bad);
  }
});

test("decodeSegment tolerates bad escapes", () => {
  assert.equal(decodeSegment("paper%3A4471"), "paper:4471");
  assert.equal(decodeSegment("%E0%A4%A"), "%E0%A4%A");
});
