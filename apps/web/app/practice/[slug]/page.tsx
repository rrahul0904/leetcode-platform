import { PracticeWorkspace } from "@/components/practice-workspace";

export default async function PracticePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <PracticeWorkspace slug={slug} />;
}
