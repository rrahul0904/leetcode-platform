"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  ChevronRight,
  Gauge,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
  Trophy,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  finalizeArenaSubmission,
  generateArenaCode,
  getArenaChallenges,
  getArenaLeaderboard,
  getArenaProfile,
  isArenaExecutionComplete,
  arenaRuntime,
  type ArenaGeneration,
  type ArenaResult,
} from "@/lib/ai-arena-api";
import {
  createRuntimePracticeSession,
  getCompletedSubmission,
  getExecution,
  queueSubmitExecution,
} from "@/lib/async-execution";

import styles from "./ai-arena.module.css";

const sleep = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

export function AIArena() {
  const challenges = useQuery({
    queryKey: ["ai-arena-challenges"],
    queryFn: ({ signal }) => getArenaChallenges(signal),
  });
  const profile = useQuery({
    queryKey: ["ai-arena-profile"],
    queryFn: ({ signal }) => getArenaProfile(signal),
  });
  const leaderboard = useQuery({
    queryKey: ["ai-arena-leaderboard"],
    queryFn: ({ signal }) => getArenaLeaderboard(signal),
  });

  const [selectedSlug, setSelectedSlug] = useState("");
  const [prompt, setPrompt] = useState("");
  const [generation, setGeneration] = useState<ArenaGeneration | null>(null);
  const [result, setResult] = useState<ArenaResult | null>(null);
  const [status, setStatus] = useState("Choose a challenge and write the instruction.");
  const [busy, setBusy] = useState<"generate" | "submit" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const effectiveSelectedSlug =
    selectedSlug || challenges.data?.[0]?.slug || "";

  const selected = useMemo(
    () =>
      challenges.data?.find((item) => item.slug === effectiveSelectedSlug) ?? null,
    [challenges.data, effectiveSelectedSlug],
  );

  function selectChallenge(slug: string) {
    setSelectedSlug(slug);
    setPrompt("");
    setGeneration(null);
    setResult(null);
    setError(null);
    setStatus("Write an instruction that will make the model solve this challenge.");
  }

  async function generate() {
    if (!selected || !prompt.trim() || busy) return;
    setBusy("generate");
    setError(null);
    setResult(null);
    setStatus("Generating a Python candidate from your instruction…");
    try {
      const candidate = await generateArenaCode(
        selected.slug,
        prompt.trim(),
        crypto.randomUUID(),
      );
      setGeneration(candidate);
      setStatus(
        candidate.provider === "skillforge-fallback"
          ? "Model generation was unavailable. The deterministic fallback candidate is shown truthfully."
          : "Candidate generated. Submit it unchanged to the isolated evaluator.",
      );
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "AI candidate generation failed.";
      setError(message);
      setStatus("Generation did not complete.");
    } finally {
      setBusy(null);
    }
  }

  async function submitGeneratedCandidate() {
    if (!selected || !generation || busy) return;
    setBusy("submit");
    setError(null);
    setResult(null);
    setStatus("Creating an isolated SkillForge practice session…");
    try {
      const session = await createRuntimePracticeSession(selected.slug, arenaRuntime);
      setStatus("Submitting generated code to the SkillForge execution plane…");
      const accepted = await queueSubmitExecution(
        selected.slug,
        session.id,
        generation.generated_code,
        arenaRuntime,
        crypto.randomUUID(),
      );

      let execution = await getExecution(accepted.execution_id);
      for (let attempt = 0; attempt < 120 && !isArenaExecutionComplete(execution); attempt += 1) {
        await sleep(1_000);
        execution = await getExecution(accepted.execution_id);
        setStatus(
          execution.status === "RUNNING"
            ? "Running public and hidden tests in the isolated sandbox…"
            : "Waiting for the isolated evaluator…",
        );
      }

      if (!isArenaExecutionComplete(execution)) {
        throw new Error("Arena evaluation did not finish within the browser verification window.");
      }
      if (execution.status !== "COMPLETED" || !execution.submission_id) {
        throw new Error(
          execution.error ?? `Arena execution ended as ${execution.status.toLowerCase()}.`,
        );
      }

      await getCompletedSubmission(execution.submission_id);
      setStatus("Finalizing the server-authoritative Arena score…");
      const scored = await finalizeArenaSubmission(
        generation.id,
        execution.submission_id,
      );
      setResult(scored);
      setStatus("Arena submission scored and rating updated.");
      await Promise.all([profile.refetch(), leaderboard.refetch()]);
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Arena evaluation failed.";
      setError(message);
      setStatus("The submission was not scored.");
    } finally {
      setBusy(null);
    }
  }

  if (challenges.isLoading) {
    return (
      <section className={styles.shell}>
        <div className={styles.loading}>
          <LoaderCircle className={styles.spin} size={22} />
          Loading AI Arena challenges…
        </div>
      </section>
    );
  }

  if (challenges.isError) {
    return (
      <section className={styles.shell}>
        <div className={styles.error}>AI Arena challenges are unavailable.</div>
      </section>
    );
  }

  return (
    <section className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>
            <Sparkles size={14} /> AI ENGINEERING ARENA
          </span>
          <h1>Win with the instruction, not a hand-written solution.</h1>
          <p>
            Prompt the model, submit its generated Python unchanged, and let the existing
            SkillForge sandbox judge public and hidden tests. Hidden evidence never enters
            the model prompt or browser.
          </p>
        </div>
        <div className={styles.profileCard}>
          <span>Your Arena rating</span>
          <strong>{profile.data?.rating ?? 1000}</strong>
          <div>
            <b>{profile.data?.tier ?? "Bronze"}</b>
            <small>{profile.data?.solved_count ?? 0} solved</small>
          </div>
        </div>
      </header>

      <div className={styles.scoreLegend}>
        <div><strong>70</strong><span>Correctness</span></div>
        <div><strong>15</strong><span>Performance</span></div>
        <div><strong>10</strong><span>Code quality</span></div>
        <div><strong>5</strong><span>Prompt efficiency</span></div>
      </div>

      <div className={styles.layout}>
        <aside className={styles.challengeRail}>
          <div className={styles.railTitle}>
            <span>Challenges</span>
            <strong>{challenges.data?.length ?? 0}</strong>
          </div>
          {(challenges.data ?? []).map((challenge) => (
            <button
              className={challenge.slug === effectiveSelectedSlug ? styles.activeChallenge : ""}
              key={challenge.slug}
              onClick={() => selectChallenge(challenge.slug)}
              type="button"
            >
              <span>{challenge.difficulty}</span>
              <strong>{challenge.title}</strong>
              <small>
                {challenge.public_test_count} public · {challenge.hidden_test_count} hidden
              </small>
              <ChevronRight size={15} />
            </button>
          ))}
          {(challenges.data?.length ?? 0) === 0 && (
            <p className={styles.empty}>
              No published Python challenge currently has a complete hidden-test contract.
            </p>
          )}
        </aside>

        <main className={styles.workspace}>
          {selected ? (
            <>
              <section className={styles.problem}>
                <div className={styles.problemMeta}>
                  <span>{selected.difficulty}</span>
                  <span>{selected.public_test_count} public tests</span>
                  <span>{selected.hidden_test_count} hidden tests</span>
                </div>
                <h2>{selected.title}</h2>
                <p>{selected.problem_statement || "Use the published challenge contract."}</p>
                {selected.constraints.length > 0 && (
                  <>
                    <h3>Constraints</h3>
                    <ul>
                      {selected.constraints.map((constraint) => (
                        <li key={constraint}>{constraint}</li>
                      ))}
                    </ul>
                  </>
                )}
                {selected.public_examples.length > 0 && (
                  <>
                    <h3>Public examples</h3>
                    <div className={styles.examples}>
                      {selected.public_examples.slice(0, 3).map((example, index) => (
                        <pre key={index}>{JSON.stringify(example, null, 2)}</pre>
                      ))}
                    </div>
                  </>
                )}
              </section>

              <section className={styles.promptPanel}>
                <div className={styles.panelHeading}>
                  <div>
                    <span>PROMPT</span>
                    <h2>Instruct the model</h2>
                  </div>
                  <small>{prompt.length}/4000</small>
                </div>
                <textarea
                  aria-label="AI Arena prompt"
                  disabled={Boolean(busy)}
                  maxLength={4000}
                  onChange={(event) => {
                    setPrompt(event.target.value);
                    setGeneration(null);
                    setResult(null);
                  }}
                  placeholder="Describe the algorithm, invariant, edge cases, complexity target, and implementation constraints…"
                  value={prompt}
                />
                <button
                  className={styles.primary}
                  disabled={!prompt.trim() || Boolean(busy)}
                  onClick={() => void generate()}
                  type="button"
                >
                  {busy === "generate" ? (
                    <LoaderCircle className={styles.spin} size={16} />
                  ) : (
                    <Bot size={16} />
                  )}
                  Generate Python
                </button>

                <div className={styles.status} aria-live="polite">
                  <ShieldCheck size={16} />
                  <span>{status}</span>
                </div>
                {error && <div className={styles.error}>{error}</div>}

                {generation && (
                  <div className={styles.generated}>
                    <div className={styles.generatedHead}>
                      <div>
                        <span>GENERATED CANDIDATE</span>
                        <strong>{generation.provider} · {generation.model}</strong>
                      </div>
                      <small>Read-only by design</small>
                    </div>
                    <pre>{generation.generated_code}</pre>
                    <button
                      className={styles.submit}
                      disabled={Boolean(busy) || Boolean(result)}
                      onClick={() => void submitGeneratedCandidate()}
                      type="button"
                    >
                      {busy === "submit" ? (
                        <LoaderCircle className={styles.spin} size={16} />
                      ) : (
                        <Play size={16} />
                      )}
                      Run hidden tests & submit
                    </button>
                  </div>
                )}

                {result && (
                  <div className={styles.result}>
                    <div className={styles.resultHeadline}>
                      <div>
                        <span>ARENA SCORE</span>
                        <strong>{result.score.total}<small>/100</small></strong>
                      </div>
                      <div>
                        <span>RATING</span>
                        <strong>
                          +{result.rating_delta} → {result.rating_after}
                        </strong>
                        <small>{result.tier}</small>
                      </div>
                    </div>
                    <div className={styles.resultGrid}>
                      <div><strong>{result.score.correctness}</strong><span>Correctness</span></div>
                      <div><strong>{result.score.performance}</strong><span>Performance</span></div>
                      <div><strong>{result.score.quality}</strong><span>Quality</span></div>
                      <div><strong>{result.score.efficiency}</strong><span>Prompt efficiency</span></div>
                    </div>
                  </div>
                )}
              </section>
            </>
          ) : (
            <div className={styles.empty}>Select a published Arena challenge.</div>
          )}
        </main>

        <aside className={styles.leaderboard}>
          <div className={styles.railTitle}>
            <span><Trophy size={14} /> Leaderboard</span>
            <strong>Top 100</strong>
          </div>
          {(leaderboard.data ?? []).map((row) => (
            <div className={styles.leaderRow} key={`${row.rank}-${row.display_name}`}>
              <span>#{row.rank}</span>
              <div>
                <strong>{row.display_name}</strong>
                <small>{row.tier} · {row.solved_count} solved</small>
              </div>
              <b>{row.rating}</b>
            </div>
          ))}
          {!leaderboard.isLoading && (leaderboard.data?.length ?? 0) === 0 && (
            <p className={styles.empty}>The first scored submission will open the leaderboard.</p>
          )}
          <div className={styles.securityNote}>
            <Gauge size={16} />
            <p>
              Rating moves only on demonstrated score improvement. Replaying the same result
              does not farm rating.
            </p>
          </div>
        </aside>
      </div>
    </section>
  );
}
