import { notFound } from "next/navigation";

import { JournalArticleView } from "@/components/journal-article";
import { journalArticle, journalArticles } from "@/lib/editorial-content";

export function generateStaticParams() {
  return journalArticles.map((article) => ({ slug: article.slug }));
}

export default async function JournalArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const article = journalArticle(slug);
  if (!article) notFound();
  return <JournalArticleView article={article} />;
}
