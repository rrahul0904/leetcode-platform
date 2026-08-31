import { SkillsForgePracticeWorkspace } from "@/components/skillsforge-practice-workspace";

export default async function PracticePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <SkillsForgePracticeWorkspace slug={slug} />;
}
