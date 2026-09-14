import type { Metadata } from "next";
import Link from "next/link";

import { robotsFor } from "@/lib/robots";

// Only for URLs outside the archive's route space. Archive identifiers never reach
// this page; /abs/<id> renders its own "here is what exists" state.
export const metadata: Metadata = {
  title: "Page not found",
  robots: robotsFor({ stage: null, gated: false }),
};

export default function NotFound() {
  return (
    <>
      <h1>No page here</h1>
      <p>
        Start from the <Link href="/">home page</Link>, or look up an identifier at{" "}
        <code>/abs/paper:NUMBER</code> or <code>/abs/scratch:NUMBER</code>.
      </p>
    </>
  );
}
