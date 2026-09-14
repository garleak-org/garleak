import { redirect } from "next/navigation";

type Params = Promise<{ category: string }>;

export default async function ScratchListingDefault({ params }: { params: Params }) {
  const { category } = await params;
  redirect(`/scratch/list/${category}/new`);
}
