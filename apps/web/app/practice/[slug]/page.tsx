import { GuidedPracticeExperience } from "@/components/guided-practice-experience";

export default async function PracticePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <GuidedPracticeExperience slug={slug} />;
}
