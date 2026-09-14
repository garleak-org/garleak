#!/usr/bin/env node
// Fails if web source carries the other archive's name or its maroon identity color.
// Both are trademark risks (MASTER-PLAN.md section 2, DESIGN.md "What never to copy").
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const SCAN = ["app", "components", "lib", "public"];
const EXT = /\.(tsx?|jsx?|mjs|css|html|svg|json|txt|md)$/;
const RULES = [
  { name: "arxiv name", re: /ar\s*[-_.]?\s*xiv/i },
  { name: "maroon #b31b1b", re: /b31b1b/i },
  { name: "maroon rgb(179,27,27)", re: /179\s*,\s*27\s*,\s*27/ },
];

function* walk(dir) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return;
  }
  for (const name of entries) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (EXT.test(name)) yield p;
  }
}

const hits = [];
for (const dir of SCAN) {
  for (const file of walk(join(root, dir))) {
    const lines = readFileSync(file, "utf8").split("\n");
    lines.forEach((line, i) => {
      for (const rule of RULES) {
        if (rule.re.test(line)) hits.push(`${relative(root, file)}:${i + 1} ${rule.name}`);
      }
    });
  }
}

if (hits.length) {
  console.error("Branding check failed:\n" + hits.join("\n"));
  process.exit(1);
}
console.log("Branding check passed.");
