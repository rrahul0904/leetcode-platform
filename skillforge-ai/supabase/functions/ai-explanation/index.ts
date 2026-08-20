import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405, headers: corsHeaders });

  try {
    const { question_id, question, answer, focus = "explain" } = await req.json();
    const apiKey = Deno.env.get("AI_API_KEY") ?? Deno.env.get("OPENAI_API_KEY");
    const baseUrl = (Deno.env.get("AI_BASE_URL") ?? "https://api.openai.com/v1").replace(/\/$/, "");
    const model = Deno.env.get("AI_CHAT_MODEL") ?? "gpt-4.1-mini";

    if (!question) return Response.json({ error: "question is required" }, { status: 400, headers: corsHeaders });

    if (!apiKey) {
      return Response.json({
        provider: "fallback",
        model: "rule-based",
        explanation: "Identify the requirement, state the governing invariant, compare at least two approaches, then validate your choice with correctness, reliability, performance, cost, and rollback criteria.",
      }, { headers: corsHeaders });
    }

    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model,
        temperature: 0.2,
        messages: [
          {
            role: "system",
            content: "You are SkillForge AI, a rigorous data-engineering interview tutor. Explain reasoning clearly, call out tradeoffs and operational validation, and do not invent facts not present in the prompt. If reviewing a candidate answer, distinguish what is correct, missing, and risky.",
          },
          {
            role: "user",
            content: `Focus: ${focus}\n\nQuestion:\n${question}\n\nCandidate answer:\n${answer ?? "Not provided"}`,
          },
        ],
      }),
    });

    if (!response.ok) {
      return Response.json({ error: `AI provider returned ${response.status}` }, { status: 502, headers: corsHeaders });
    }

    const body = await response.json();
    const explanation = body?.choices?.[0]?.message?.content?.trim();
    if (!explanation) return Response.json({ error: "AI provider returned no explanation" }, { status: 502, headers: corsHeaders });

    const authHeader = req.headers.get("Authorization") ?? "";
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: authHeader } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      await supabase.from("ai_interactions").insert({
        user_id: user.id,
        question_id: question_id || null,
        interaction_type: focus === "review" ? "answer_review" : "explanation",
        model_provider: Deno.env.get("AI_PROVIDER") ?? "openai-compatible",
        model_name: model,
        prompt_tokens: body?.usage?.prompt_tokens ?? null,
        completion_tokens: body?.usage?.completion_tokens ?? null,
      });
    }

    return Response.json({
      provider: Deno.env.get("AI_PROVIDER") ?? "openai-compatible",
      model,
      explanation,
      usage: body?.usage ?? null,
    }, { headers: corsHeaders });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "AI explanation failed" }, { status: 500, headers: corsHeaders });
  }
});
