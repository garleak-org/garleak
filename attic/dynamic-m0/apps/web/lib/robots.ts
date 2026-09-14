/**
 * Indexing rules. T0 (unverified) papers and anything in a gated category carry
 * noindex, to blunt citation laundering. Pages that resolve to nothing also carry
 * noindex, so placeholder states never enter a search index.
 *
 * Every page that renders an archive object must set its metadata through
 * robotsFor(). Do not write a robots value by hand.
 */

export type PaperTier = "T0" | "T1" | "T2" | "T3" | "T4";
export type ScratchStage = "N0" | "N1" | "N2" | "N3";
export type Stage = PaperTier | ScratchStage;

export interface IndexingInput {
  /** Current tier or stage of the version shown. null when nothing resolved. */
  stage: Stage | null;
  /** True when the object sits in a gated category (clinical, legal, and so on). */
  gated: boolean;
}

export interface RobotsDirective {
  index: boolean;
  follow: boolean;
}

export function robotsFor({ stage, gated }: IndexingInput): RobotsDirective {
  if (gated || stage === null || stage === "T0") {
    return { index: false, follow: false };
  }
  return { index: true, follow: true };
}
