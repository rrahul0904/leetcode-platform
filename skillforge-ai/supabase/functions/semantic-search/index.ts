import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const { query, embedding, limit = 20 } = await req.json();
  if (!query || !Array.isArray(embedding)) return Response.json({ error: "query and embedding are required" }, { status: 400 });

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
  );
  const { data, error } = await supabase.rpc("hybrid_question_search", {
    query_text: query,
    query_embedding: embedding,
    match_count: Math.min(Number(limit) || 20, 50),
  });
  if (error) return Response.json({ error: error.message }, { status: 400 });
  return Response.json({ data });
});
