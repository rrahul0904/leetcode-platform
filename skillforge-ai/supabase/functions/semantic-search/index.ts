import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

type SearchMode = "keyword" | "semantic" | "hybrid";

const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, x-client-info, apikey, content-type",
};

async function createEmbedding(query: string): Promise<number[] | null> {
  const apiKey = Deno.env.get("AI_API_KEY") ?? Deno.env.get("OPENAI_API_KEY");
  if (!apiKey) return null;

  const baseUrl = (Deno.env.get("AI_BASE_URL") ?? "https://api.openai.com/v1").replace(/\/$/, "");
  const model = Deno.env.get("AI_EMBEDDING_MODEL") ?? "text-embedding-3-small";
  const response = await fetch(`${baseUrl}/embeddings`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${apiKey}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ model, input: query }),
  });

  if (!response.ok) {
    console.error("embedding provider error", response.status, await response.text());
    return null;
  }

  const body = await response.json();
  const embedding = body?.data?.[0]?.embedding;
  return Array.isArray(embedding) ? embedding : null;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405, headers: corsHeaders });

  try {
    const payload = await req.json();
    const query = String(payload.query ?? "").trim();
    const requestedMode = String(payload.mode ?? "hybrid").toLowerCase() as SearchMode;
    const mode: SearchMode = ["keyword", "semantic", "hybrid"].includes(requestedMode) ? requestedMode : "hybrid";
    const limit = Math.min(Math.max(Number(payload.limit) || 20, 1), 50);

    if (!query) return Response.json({ error: "query is required" }, { status: 400, headers: corsHeaders });

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    );

    if (mode === "keyword") {
      const { data, error } = await supabase.rpc("keyword_question_search", {
        query_text: query,
        match_count: limit,
      });
      if (error) return Response.json({ error: error.message }, { status: 400, headers: corsHeaders });
      return Response.json({ query, requested_mode: mode, executed_mode: "keyword", results: data ?? [] }, { headers: corsHeaders });
    }

    const suppliedEmbedding = Array.isArray(payload.embedding) ? payload.embedding : null;
    const embedding = suppliedEmbedding ?? await createEmbedding(query);

    if (!embedding) {
      const { data, error } = await supabase.rpc("keyword_question_search", {
        query_text: query,
        match_count: limit,
      });
      if (error) return Response.json({ error: error.message }, { status: 400, headers: corsHeaders });
      return Response.json({
        query,
        requested_mode: mode,
        executed_mode: "keyword-fallback",
        warning: "Embedding provider is not configured or unavailable; full-text search was used.",
        results: data ?? [],
      }, { headers: corsHeaders });
    }

    const { data, error } = await supabase.rpc("hybrid_question_search", {
      query_text: query,
      query_embedding: embedding,
      match_count: limit,
      semantic_weight: mode === "semantic" ? 1 : 0.65,
      keyword_weight: mode === "semantic" ? 0 : 0.35,
    });
    if (error) return Response.json({ error: error.message }, { status: 400, headers: corsHeaders });

    return Response.json({ query, requested_mode: mode, executed_mode: mode, results: data ?? [] }, { headers: corsHeaders });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Search failed" }, { status: 500, headers: corsHeaders });
  }
});
