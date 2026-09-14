import type { Metadata } from "next";

import { ListingView, listingMetadata } from "@/components/ListingView";
import { decodeSegment } from "@/lib/ids";

type Params = Promise<{ category: string; period: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { category, period } = await params;
  return listingMetadata("paper", decodeSegment(category), decodeSegment(period));
}

export default async function PaperListing({ params }: { params: Params }) {
  const { category, period } = await params;
  return (
    <ListingView
      kind="paper"
      categorySlug={decodeSegment(category)}
      periodSlug={decodeSegment(period)}
    />
  );
}
