import type { Metadata } from "next";

import { ListingView, listingMetadata } from "@/components/ListingView";
import { decodeSegment } from "@/lib/ids";

type Params = Promise<{ category: string; period: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { category, period } = await params;
  return listingMetadata("scratch", decodeSegment(category), decodeSegment(period));
}

export default async function ScratchListing({ params }: { params: Params }) {
  const { category, period } = await params;
  return (
    <ListingView
      kind="scratch"
      categorySlug={decodeSegment(category)}
      periodSlug={decodeSegment(period)}
    />
  );
}
