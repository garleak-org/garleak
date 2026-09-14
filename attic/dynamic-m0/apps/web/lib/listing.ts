/**
 * Categories and listing periods.
 *
 * The category list is a placeholder until SPEC.md defines the taxonomy. It holds
 * the three launch fields from the master plan plus one gated example so the
 * noindex path is exercised.
 */

export interface Category {
  slug: string;
  name: string;
  gated: boolean;
}

export const CATEGORIES: readonly Category[] = [
  { slug: "physics", name: "Physics", gated: false },
  { slug: "cs", name: "Computer science", gated: false },
  { slug: "math", name: "Mathematics", gated: false },
  { slug: "clinical", name: "Clinical", gated: true },
];

export function findCategory(slug: string): Category | undefined {
  return CATEGORIES.find((c) => c.slug === slug.toLowerCase());
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export type Period =
  | { ok: true; slug: string; label: string }
  | { ok: false; input: string };

/** Accepts new, recent, YYYY, and YYYY-MM. */
export function parsePeriod(raw: string): Period {
  const slug = raw.toLowerCase();
  if (slug === "new") return { ok: true, slug, label: "new submissions" };
  if (slug === "recent") return { ok: true, slug, label: "recent" };
  const year = /^(\d{4})$/.exec(slug);
  if (year) return { ok: true, slug, label: year[1]! };
  const ym = /^(\d{4})-(\d{2})$/.exec(slug);
  if (ym) {
    const month = MONTHS[Number(ym[2]) - 1];
    if (month) return { ok: true, slug, label: `${month} ${ym[1]}` };
  }
  return { ok: false, input: raw };
}

export const DEFAULT_PERIODS = ["new", "recent"] as const;
