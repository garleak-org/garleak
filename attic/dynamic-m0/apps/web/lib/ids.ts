/**
 * Identifier grammar for /abs/<id>.
 *
 *   paper:4471        canonical, resolves to the latest version
 *   paper:4471v3      a specific major version
 *   paper:4471v3.1    a specific major.minor version
 *   scratch:8812      scratches use their own number space
 *
 * Provisional until SPEC.md fixes the grammar. Nothing here may throw on bad input:
 * unknown or malformed ids render a "here is what exists" page, never a 404.
 */

export type ObjectKind = "paper" | "scratch";

export interface VersionRef {
  major: number;
  minor: number | null;
}

export type ParsedId =
  | {
      ok: true;
      kind: ObjectKind;
      number: number;
      version: VersionRef | null;
      /** Normalized form, e.g. "paper:4471v3". */
      canonical: string;
      /** The identifier without a version, e.g. "paper:4471". */
      concept: string;
    }
  | { ok: false; reason: "bare-number"; number: number; input: string }
  | { ok: false; reason: "malformed"; input: string };

const ID_RE = /^(paper|scratch):([1-9]\d{0,11})(?:v([1-9]\d{0,5})(?:\.(\d{1,5}))?)?$/;
const BARE_RE = /^([1-9]\d{0,11})$/;

/** Decode a route segment without throwing on stray percent signs. */
export function decodeSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

export function parseId(raw: string): ParsedId {
  const input = raw.trim();
  const lowered = input.toLowerCase();

  const m = ID_RE.exec(lowered);
  if (m) {
    const kind = m[1] as ObjectKind;
    const number = Number(m[2]);
    const version: VersionRef | null = m[3]
      ? { major: Number(m[3]), minor: m[4] !== undefined ? Number(m[4]) : null }
      : null;
    const concept = `${kind}:${number}`;
    const canonical = version
      ? `${concept}v${version.major}${version.minor !== null ? `.${version.minor}` : ""}`
      : concept;
    return { ok: true, kind, number, version, canonical, concept };
  }

  const bare = BARE_RE.exec(lowered);
  if (bare) {
    return { ok: false, reason: "bare-number", number: Number(bare[1]), input };
  }

  return { ok: false, reason: "malformed", input };
}

export function absPath(id: string): string {
  return `/abs/${id}`;
}
