import Link from "next/link";

import { CATEGORIES } from "@/lib/listing";

export default function Home() {
  return (
    <>
      <h1>Garleak</h1>
      <p>
        An open archive of AI-assisted papers and research scratches. Every submission declares
        which model helped and how, and carries a public record of who checked it and what they
        found.
      </p>
      <p>This is the M0 scaffold. The archive holds no records yet.</p>

      <h2>Papers</h2>
      <ul>
        {CATEGORIES.map((c) => (
          <li key={c.slug}>
            <Link href={`/list/${c.slug}/new`}>{c.name}</Link>
          </li>
        ))}
      </ul>

      <h2>Scratches</h2>
      <ul>
        {CATEGORIES.map((c) => (
          <li key={c.slug}>
            <Link href={`/scratch/list/${c.slug}/new`}>{c.name}</Link>
          </li>
        ))}
      </ul>
    </>
  );
}
