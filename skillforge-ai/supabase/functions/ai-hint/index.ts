Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const { question, attempt } = await req.json();
  if (!question) return Response.json({ error: "question is required" }, { status: 400 });
  const key = Deno.env.get("OPENAI_API_KEY");
  if (!key) return Response.json({ hint: "AI is not configured. Re-read the constraints and identify the smallest invariant that determines the result.", provider: "fallback" });

  const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "gpt-5-mini",
      messages: [
        { role: "system", content: "You are SkillForge AI. Give one concise hint. Do not reveal the full solution unless explicitly requested." },
        { role: "user", content: `Question:\n${question}\n\nCurrent attempt:\n${attempt ?? ""}` },
      ],
    }),
  });
  if (!upstream.ok) return Response.json({ error: "AI provider request failed" }, { status: 502 });
  const body = await upstream.json();
  return Response.json({ hint: body.choices?.[0]?.message?.content ?? "", provider: "openai" });
});
