import { redirect } from "next/navigation";

export default async function ProblemPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  redirect(`/question-bank/${encodeURIComponent(slug)}`);
}
