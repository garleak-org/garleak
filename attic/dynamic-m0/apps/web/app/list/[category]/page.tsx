import { redirect } from "next/navigation";

type Params = Promise<{ category: string }>;

export default async function PaperListingDefault({ params }: { params: Params }) {
  const { category } = await params;
  redirect(`/list/${category}/new`);
}
