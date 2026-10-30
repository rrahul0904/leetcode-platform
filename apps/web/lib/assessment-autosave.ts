/** Select the oldest question with non-empty edits that the server hasn't acknowledged.
 * Avoid replaying exactly the same failed payload forever, but allow a later edit
 * or a different question to proceed. Works independently of the visible tab.
 */
export function nextPendingAssessmentResponse(
  attemptId: string,
  questionNumbers: readonly number[],
  saved: Readonly<Record<string, string>>,
  drafts: Readonly<Record<string, string>>,
  lastAttemptedRevision: string | null,
): { number: number; source: string; revision: string } | null {
  for (const number of questionNumbers) {
    const source = drafts[String(number)] ?? "";
    if (source === (saved[String(number)] ?? "")) continue;
    const revision = JSON.stringify([attemptId, number, source]);
    if (revision === lastAttemptedRevision) continue;
    return { number, source, revision };
  }
  return null;
}
