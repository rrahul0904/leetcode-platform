import { PersistentKnowledgeProblemWorkspace } from "@/components/persistent-knowledge-problem-workspace";

export default async function KnowledgeProblemPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <PersistentKnowledgeProblemWorkspace slug={slug} />;
}
