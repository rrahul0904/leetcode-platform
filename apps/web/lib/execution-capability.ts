export type ExecutionCapability = {
  question_version_id: string;
  availability: "runnable" | "hosted";
  runtime: "python3.13" | "postgresql18" | null;
  starter_source: string;
  public_test_count: number;
  hidden_test_count: number;
  reason: string | null;
};

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "/api/backend";
const useLocalAccessToken = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE === "local";

export async function getExecutionCapability(
  slug: string,
  signal?: AbortSignal,
): Promise<ExecutionCapability> {
  const accessToken =
    !useLocalAccessToken ||
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
      ? null
      : window.localStorage.getItem("rigor.auth.access-token");
  const response = await fetch(
    `${apiUrl}/api/v1/questions/${encodeURIComponent(slug)}/execution-capability`,
    {
      headers: {
        Accept: "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      ...(signal ? { signal } : {}),
    },
  );
  if (!response.ok) {
    throw new Error(`Execution capability returned ${response.status}`);
  }
  return (await response.json()) as ExecutionCapability;
}
