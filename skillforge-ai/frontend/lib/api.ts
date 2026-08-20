export type RunnerResult = { status: string; output: string; runtime_ms: number };
export type SearchMode = "keyword" | "semantic" | "hybrid";
export type SemanticSearchHit = {
  question_id?: string;
  public_id: string;
  title: string;
  difficulty: "Easy" | "Medium" | "Hard" | string;
  score: number;
};
export type SemanticSearchResponse = {
  query: string;
  requested_mode: SearchMode;
  executed_mode: string;
  warning?: string;
  results: SemanticSearchHit[];
};

const apiBase = () => process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

async function parseError(response: Response) {
  try {
    const body = await response.json();
    return body.detail || body.error || body.message || JSON.stringify(body);
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

function edgeHeaders() {
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!anonKey) return null;
  return {
    "content-type": "application/json",
    authorization: `Bearer ${anonKey}`,
    apikey: anonKey,
  };
}

export async function requestSemanticSearch(
  query: string,
  mode: SearchMode = "hybrid",
): Promise<SemanticSearchResponse | null> {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  const headers = edgeHeaders();
  if (!supabaseUrl || !headers) return null;
  const response = await fetch(`${supabaseUrl}/functions/v1/semantic-search`, {
    method: "POST",
    headers,
    body: JSON.stringify({ query, limit: 12, mode }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function requestAIExplanation(input: {
  questionId?: string;
  question: string;
  answer?: string;
  focus?: "explain" | "review" | "tradeoffs" | "simpler-example";
}) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  const headers = edgeHeaders();
  if (!supabaseUrl || !headers) {
    return {
      provider: "local-fallback",
      model: "rule-based",
      explanation:
        "State the requirement and invariant first. Then compare alternatives, identify operational risks, and define measurable validation plus rollback criteria.",
    };
  }
  const response = await fetch(`${supabaseUrl}/functions/v1/ai-explanation`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      question_id: input.questionId,
      question: input.question,
      answer: input.answer,
      focus: input.focus ?? "explain",
    }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}
