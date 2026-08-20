import { createSupabaseBrowserClient } from "@/lib/supabase-browser";

export type PersistAttemptInput = {
  publicId: string;
  answerBody: string;
  isCorrect?: boolean | null;
  runtimeMs?: number | null;
  feedback?: string | null;
};

function isConfigured() {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}

export async function persistAttempt(input: PersistAttemptInput): Promise<{ synced: boolean; reason?: string }> {
  if (!isConfigured()) return { synced: false, reason: "Supabase is not configured" };
  const supabase = createSupabaseBrowserClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) return { synced: false, reason: "No authenticated user" };

  const { data: question, error: questionError } = await supabase
    .from("questions")
    .select("id")
    .eq("public_id", input.publicId)
    .maybeSingle();
  if (questionError) throw questionError;
  if (!question) return { synced: false, reason: "Question is not present in Supabase" };

  const { error } = await supabase.from("attempts").insert({
    user_id: user.id,
    question_id: question.id,
    answer_body: input.answerBody,
    is_correct: input.isCorrect ?? null,
    runtime_ms: input.runtimeMs ?? null,
    feedback: input.feedback ?? null,
  });
  if (error) throw error;
  return { synced: true };
}

export async function toggleBookmark(publicId: string): Promise<{ bookmarked: boolean; synced: boolean; reason?: string }> {
  if (!isConfigured()) return { bookmarked: false, synced: false, reason: "Supabase is not configured" };
  const supabase = createSupabaseBrowserClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) return { bookmarked: false, synced: false, reason: "No authenticated user" };

  const { data: question, error: questionError } = await supabase
    .from("questions")
    .select("id")
    .eq("public_id", publicId)
    .maybeSingle();
  if (questionError) throw questionError;
  if (!question) return { bookmarked: false, synced: false, reason: "Question is not present in Supabase" };

  const { data: existing, error: lookupError } = await supabase
    .from("bookmarks")
    .select("id")
    .eq("user_id", user.id)
    .eq("question_id", question.id)
    .maybeSingle();
  if (lookupError) throw lookupError;

  if (existing) {
    const { error } = await supabase.from("bookmarks").delete().eq("id", existing.id);
    if (error) throw error;
    return { bookmarked: false, synced: true };
  }

  const { error } = await supabase.from("bookmarks").insert({ user_id: user.id, question_id: question.id });
  if (error) throw error;
  return { bookmarked: true, synced: true };
}

export async function isBookmarked(publicId: string): Promise<boolean> {
  if (!isConfigured()) return false;
  const supabase = createSupabaseBrowserClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return false;
  const { data: question } = await supabase.from("questions").select("id").eq("public_id", publicId).maybeSingle();
  if (!question) return false;
  const { data } = await supabase
    .from("bookmarks")
    .select("id")
    .eq("user_id", user.id)
    .eq("question_id", question.id)
    .maybeSingle();
  return Boolean(data);
}
