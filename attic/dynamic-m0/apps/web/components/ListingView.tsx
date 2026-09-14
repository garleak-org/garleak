import type { Metadata } from "next";
import Link from "next/link";

import type { ObjectKind } from "@/lib/ids";
import { CATEGORIES, DEFAULT_PERIODS, findCategory, parsePeriod } from "@/lib/listing";
import { robotsFor } from "@/lib/robots";

/**
 * One listing page for one object kind. Papers and scratches share this row shape
 * but never share a listing: each route passes exactly one kind.
 */

const NOUN: Record<ObjectKind, { plural: string; singular: string }> = {
  paper: { plural: "Papers", singular: "paper" },
  scratch: { plural: "Scratches", singular: "scratch" },
};

export function listingBase(kind: ObjectKind): string {
  return kind === "paper" ? "/list" : "/scratch/list";
}

export function listingMetadata(
  kind: ObjectKind,
  categorySlug: string,
  periodSlug: string,
): Metadata {
  const category = findCategory(categorySlug);
  const period = parsePeriod(periodSlug);
  const title =
    category && period.ok
      ? `${NOUN[kind].plural} in ${category.name}, ${period.label}`
      : `${NOUN[kind].plural}`;
  // No records exist in M0, so every listing resolves to nothing and stays out of
  // the index. Gated categories stay out regardless.
  return { title, robots: robotsFor({ stage: null, gated: category?.gated ?? false }) };
}

export function ListingView({
  kind,
  categorySlug,
  periodSlug,
}: {
  kind: ObjectKind;
  categorySlug: string;
  periodSlug: string;
}) {
  const base = listingBase(kind);
  const other: ObjectKind = kind === "paper" ? "scratch" : "paper";
  const category = findCategory(categorySlug);
  const period = parsePeriod(periodSlug);

  if (!category) {
    return (
      <>
        <h1>No category called {categorySlug}</h1>
        <p>These categories exist.</p>
        <ul>
          {CATEGORIES.map((c) => (
            <li key={c.slug}>
              <Link href={`${base}/${c.slug}/new`}>{c.name}</Link>
            </li>
          ))}
        </ul>
      </>
    );
  }

  if (!period.ok) {
    return (
      <>
        <h1>
          {NOUN[kind].plural} in {category.name}
        </h1>
        <p>
          The period {period.input} is not recognized. Periods are new, recent, a year such as
          2026, or a month such as 2026-09.
        </p>
        <PeriodLinks base={base} slug={category.slug} />
      </>
    );
  }

  return (
    <>
      <h1>
        {NOUN[kind].plural} in {category.name}, {period.label}
      </h1>
      <PeriodLinks base={base} slug={category.slug} />
      <section aria-label={`${NOUN[kind].plural} listing`}>
        <p>
          No {NOUN[kind].plural.toLowerCase()} in {category.name} yet. A {NOUN[kind].singular}{" "}
          belongs here when its subject is {category.name.toLowerCase()} and it declares the
          model and the level of assistance. Submission opens in milestone M2.
        </p>
        {category.gated ? (
          <p>
            {category.name} is a gated category. Everything filed here is held for human review
            and stays out of search indexes.
          </p>
        ) : null}
      </section>
      <p>
        {NOUN[other].plural} in this category are listed separately at{" "}
        <Link href={`${listingBase(other)}/${category.slug}/${period.slug}`}>
          {listingBase(other)}/{category.slug}/{period.slug}
        </Link>
        .
      </p>
    </>
  );
}

function PeriodLinks({ base, slug }: { base: string; slug: string }) {
  return (
    <nav aria-label="Periods">
      <ul>
        {DEFAULT_PERIODS.map((p) => (
          <li key={p}>
            <Link href={`${base}/${slug}/${p}`}>{p}</Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
