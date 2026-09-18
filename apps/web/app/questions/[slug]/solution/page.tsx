import { SolutionReview } from "@/components/solution-review";

export default async function QuestionSolutionPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <SolutionReview slug={slug} />;
}
