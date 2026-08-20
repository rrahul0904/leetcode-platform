Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const { text } = await req.json();
  if (!text) return Response.json({ error: "text is required" }, { status: 400 });
  const key = Deno.env.get("OPENAI_API_KEY");
  if (!key) return Response.json({ error: "embedding provider is not configured" }, { status: 503 });

  const upstream = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: "text-embedding-3-small", input: text, dimensions: 1536 }),
  });
  if (!upstream.ok) return Response.json({ error: "embedding provider request failed" }, { status: 502 });
  const body = await upstream.json();
  return Response.json({ embedding: body.data?.[0]?.embedding ?? [] });
});
