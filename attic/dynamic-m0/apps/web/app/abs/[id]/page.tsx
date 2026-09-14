import type { Metadata } from "next";
import Link from "next/link";

import { listingBase } from "@/components/ListingView";
import { absPath, decodeSegment, parseId, type ParsedId } from "@/lib/ids";
import { CATEGORIES } from "@/lib/listing";
import { robotsFor } from "@/lib/robots";

/**
 * /abs/<id>. Nothing here ever 404s. An id that resolves to nothing renders a page
 * that says so and points at what does exist.
 *
 * M0 has no records, so every id lands in one of the placeholder states below. M4
 * replaces the resolved branch with the full page, in the order DESIGN.md sets out
 * (title and authors, tier block, abstract, three assistance signals, version
 * timeline, model card, downloads).
 */

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const parsed = parseId(decodeSegment(id));
  const title = parsed.ok ? parsed.canonical : "Identifier not found";
  // Nothing resolves in M0. When records exist, pass the version's real tier and
  // the category's gated flag here.
  return { title, robots: robotsFor({ stage: null, gated: false }) };
}

export default async function AbsPage({ params }: { params: Params }) {
  const { id } = await params;
  const parsed = parseId(decodeSegment(id));
  return <NotFoundState parsed={parsed} />;
}

function NotFoundState({ parsed }: { parsed: ParsedId }) {
  if (parsed.ok) {
    const noun = parsed.kind === "paper" ? "paper" : "scratch";
    return (
      <>
        <h1>
          No {noun} at <code>{parsed.canonical}</code>
        </h1>
        <p>
          The identifier is well formed, but nothing is stored under it. The archive has no
          records until milestone M1.
        </p>
        {parsed.version ? (
          <p>
            The latest version of this {noun} would be at{" "}
            <Link href={absPath(parsed.concept)}>{parsed.concept}</Link>.
          </p>
        ) : null}
        <WhatExists kind={parsed.kind} />
      </>
    );
  }

  if (parsed.reason === "bare-number") {
    return (
      <>
        <h1>
          Which <code>{parsed.number}</code>?
        </h1>
        <p>
          Papers and scratches are numbered separately, so a bare number could mean either one.
        </p>
        <ul>
          <li>
            <Link href={absPath(`paper:${parsed.number}`)}>paper:{parsed.number}</Link>
          </li>
          <li>
            <Link href={absPath(`scratch:${parsed.number}`)}>scratch:{parsed.number}</Link>
          </li>
        </ul>
      </>
    );
  }

  return (
    <>
      <h1>
        <code>{parsed.input || "(empty)"}</code> is not a Garleak identifier
      </h1>
      <p>
        Identifiers look like <code>paper:4471</code> for the latest version of a paper,{" "}
        <code>paper:4471v3</code> for a specific version, and <code>scratch:8812</code> for a
        scratch.
      </p>
      <WhatExists kind="paper" />
      <WhatExists kind="scratch" />
    </>
  );
}

function WhatExists({ kind }: { kind: "paper" | "scratch" }) {
  const heading = kind === "paper" ? "Paper listings" : "Scratch listings";
  return (
    <section aria-label={heading}>
      <h2>{heading}</h2>
      <ul>
        {CATEGORIES.map((c) => (
          <li key={c.slug}>
            <Link href={`${listingBase(kind)}/${c.slug}/new`}>{c.name}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
