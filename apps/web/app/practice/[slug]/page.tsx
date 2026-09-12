import { SkillsForgePracticeWorkspace } from "@/components/skillsforge-practice-workspace";
import { TutorDock } from "@/components/tutor-dock";

export default async function PracticePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <>
      <SkillsForgePracticeWorkspace slug={slug} />
      <TutorDock slug={slug} />
    </>
  );
}
