import { PersistentKnowledgeProblemWorkspace } from "@/components/persistent-knowledge-problem-workspace";
import { VerifiedPracticeLaunch } from "@/components/verified-practice-launch";

export default async function KnowledgeProblemPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <>
      <VerifiedPracticeLaunch slug={slug} />
      <PersistentKnowledgeProblemWorkspace slug={slug} />
    </>
  );
}
