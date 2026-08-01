import { SystemDesignArticle } from "@/components/system-design-article";

export default async function SystemDesignArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <SystemDesignArticle slug={slug} />;
}
