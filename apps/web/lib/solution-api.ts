export type QuestionSolutionReveal = {
  question_slug: string;
  title: string;
  reference_solution: string;
  explanation: string;
  trade_off_analysis: unknown;
  time_complexity: string | null;
  space_complexity: string | null;
  common_mistakes: unknown;
  expected_approach: unknown;
  best_practices: unknown;
  hidden_tests_revealed: false;
};

export class SolutionRevealError extends Error {
  constructor(public status: number) {
    super(`Solution reveal returned ${status}`);
  }
}

const apiUrl = process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "http://localhost:8002";

export async function getQuestionSolution(
  slug: string,
  signal?: AbortSignal,
): Promise<QuestionSolutionReveal> {
  const accessToken =
    typeof window === "undefined" || typeof window.localStorage === "undefined"
      ? null
      : window.localStorage.getItem("rigor.auth.access-token");
  const response = await fetch(
    `${apiUrl}/api/v1/questions/${encodeURIComponent(slug)}/solution`,
    {
      headers: {
        Accept: "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      ...(signal ? { signal } : {}),
    },
  );
  if (!response.ok) {
    throw new SolutionRevealError(response.status);
  }
  return (await response.json()) as QuestionSolutionReveal;
}
