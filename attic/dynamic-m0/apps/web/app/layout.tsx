import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Garleak", template: "%s | Garleak" },
  description:
    "An open archive of AI-assisted papers and research scratches, each with a declared provenance and a public verification record.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header>
          <nav aria-label="Site">
            <Link href="/">Garleak</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer>
          <p>
            Screening checks scope and form only. Admission to Garleak makes no claim that a
            paper or scratch is correct. Verification tiers say exactly what was checked, and
            nothing more.
          </p>
        </footer>
      </body>
    </html>
  );
}
