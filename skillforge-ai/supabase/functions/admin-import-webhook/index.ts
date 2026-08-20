import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  const auth = req.headers.get("Authorization") ?? "";
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth } } });
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return Response.json({ error: "unauthorized" }, { status: 401 });
  const { data: profile } = await supabase.from("profiles").select("role").eq("id", user.id).single();
  if (!profile || !["admin","content_reviewer","enterprise_admin"].includes(profile.role)) return Response.json({ error: "forbidden" }, { status: 403 });

  const payload = await req.json();
  const apiUrl = Deno.env.get("FASTAPI_INTERNAL_URL");
  if (!apiUrl) return Response.json({ error: "FASTAPI_INTERNAL_URL not configured" }, { status: 503 });
  const upstream = await fetch(`${apiUrl}/imports/process`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  return new Response(await upstream.text(), { status: upstream.status, headers: { "Content-Type": "application/json" } });
});
