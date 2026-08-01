import { KnowledgeProblemWorkspace } from "@/components/knowledge-problem-workspace";

export default async function KnowledgeProblemPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <KnowledgeProblemWorkspace slug={slug} />;
}
