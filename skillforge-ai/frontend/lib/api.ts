export type RunnerResult = { status: string; output: string; runtime_ms: number };

const apiBase = () => process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

async function parseError(response: Response) {
  try {
    const body = await response.json();
    return body.detail || body.message || JSON.stringify(body);
  } catch {
    return await response.text() || `HTTP ${response.status}`;
  }
}

export async function runCode(language: "python" | "sql", code: string): Promise<RunnerResult> {
  const endpoint = language === "python" ? "/runner/python" : "/runner/sql";
  const payload = language === "python" ? { code, stdin: "" } : { query: code };
  const response = await fetch(`${apiBase()}${endpoint}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function requestSemanticSearch(query: string) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !anonKey) return null;
  const response = await fetch(`${supabaseUrl}/functions/v1/semantic-search`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${anonKey}`, apikey: anonKey },
    body: JSON.stringify({ query, limit: 8, mode: "hybrid" }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}
