import { colors, radius, spacing } from "@rigor/design-tokens";
import { queryKeys } from "@rigor/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Crypto from "expo-crypto";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";

import {
  createPracticeSession,
  getQuestion,
  revealHint,
  runPracticeCode,
  savePracticeDraft,
  submitPracticeCode,
} from "../../../src/api/candidate";
import type {
  CandidateSubmission,
  ExecutionResult,
  PracticeSession,
} from "../../../src/api/types";
import {
  readLocalDraft,
  removeLocalDraft,
  saveLocalDraft,
  shouldRestoreLocalDraft,
} from "../../../src/practice/drafts";
import {
  Card,
  Eyebrow,
  PrimaryButton,
  Screen,
  StateMessage,
  Tag,
  mobileStyles,
} from "../../../src/ui/primitives";

type Pane = "problem" | "editor" | "results";

function ResultView({
  execution,
  submission,
}: {
  execution: ExecutionResult | null;
  submission: CandidateSubmission | null;
}) {
  if (!execution) {
    return (
      <StateMessage
        title="No execution yet"
        detail="Run public tests to inspect visible cases. Hidden tests remain server-side and are evaluated only through the submission flow."
      />
    );
  }

  return (
    <View style={styles.stack}>
      <Card>
        <View style={styles.resultHeader}>
          <Tag>{execution.state}</Tag>
          <Text style={mobileStyles.small}>{execution.runtime_ms ?? 0} ms</Text>
        </View>
        <Text style={mobileStyles.body}>
          {execution.candidate_message ?? "Execution finished."}
        </Text>
      </Card>
      {execution.public_results.map((test) => (
        <Card key={test.test_id}>
          <View style={styles.resultHeader}>
            <Text style={styles.cardTitle}>{test.name}</Text>
            <Tag>{test.passed ? "PASS" : "FAIL"}</Tag>
          </View>
          {!test.passed ? (
            <Text selectable style={styles.codeSmall}>
              {JSON.stringify({ expected: test.expected, actual: test.actual }, null, 2)}
            </Text>
          ) : null}
        </Card>
      ))}
      {submission ? (
        <Card>
          <Eyebrow>DETERMINISTIC EVALUATION</Eyebrow>
          <Text style={styles.score}>
            {Math.round(submission.evaluation.overall_score * 100)}%
          </Text>
          <Text style={mobileStyles.small}>
            Correctness {Math.round(submission.evaluation.correctness_score * 100)}% · Quality{" "}
            {Math.round(submission.evaluation.code_quality_score * 100)}% · Robustness{" "}
            {Math.round(submission.evaluation.robustness_score * 100)}%
          </Text>
          <PrimaryButton label="View updated readiness" onPress={() => router.push("/progress")} />
        </Card>
      ) : null}
    </View>
  );
}

function PaneTabs({ pane, onChange }: { pane: Pane; onChange: (pane: Pane) => void }) {
  return (
    <View accessibilityRole="tablist" style={styles.tabs}>
      {(["problem", "editor", "results"] as const).map((value) => (
        <Pressable
          accessibilityRole="tab"
          accessibilityState={{ selected: pane === value }}
          key={value}
          onPress={() => onChange(value)}
          style={[styles.tab, pane === value && styles.tabActive]}
        >
          <Text style={[styles.tabText, pane === value && styles.tabTextActive]}>
            {value.toUpperCase()}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

export default function PracticeWorkspaceScreen() {
  const params = useLocalSearchParams<{ slug?: string | string[] }>();
  const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
  const queryClient = useQueryClient();
  const { width } = useWindowDimensions();
  const isTablet = width >= 768;
  const [pane, setPane] = useState<Pane>("problem");
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [source, setSource] = useState("");
  const sourceRef = useRef("");
  const [elapsed, setElapsed] = useState(0);
  const [execution, setExecution] = useState<ExecutionResult | null>(null);
  const [submission, setSubmission] = useState<CandidateSubmission | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [notice, setNotice] = useState("Preparing workspace…");
  const initialized = useRef(false);

  useEffect(() => {
    sourceRef.current = source;
  }, [source]);

  const question = useQuery({
    queryKey: slug ? queryKeys.questions.detail(slug) : ["questions", "missing-slug"],
    queryFn: ({ signal }) => getQuestion(slug!, signal),
    enabled: Boolean(slug),
  });

  const sessionMutation = useMutation({
    mutationFn: () => createPracticeSession(slug!),
    onSuccess: (created) => {
      setSession(created);
      void readLocalDraft(created.id).then((local) => {
        if (local && shouldRestoreLocalDraft(local, created.updated_at)) {
          setSource(local.sourceCode);
          setElapsed(local.elapsedSeconds);
          setNotice("Recovered unsynced device draft");
          return;
        }
        setSource(created.draft_code);
        setElapsed(created.elapsed_seconds);
        setNotice("Synced");
        const baselineTime = Date.parse(created.updated_at);
        void saveLocalDraft({
          sessionId: created.id,
          questionSlug: slug!,
          sourceCode: created.draft_code,
          elapsedSeconds: created.elapsed_seconds,
          localUpdatedAt: Number.isFinite(baselineTime) ? baselineTime : Date.now(),
          serverUpdatedAt: created.updated_at,
        });
      });
    },
    onError: () => setNotice("Could not start practice session"),
  });

  const saveMutation = useMutation({
    mutationFn: (draft: { sourceCode: string; elapsedSeconds: number }) =>
      savePracticeDraft(session!.id, draft.sourceCode, draft.elapsedSeconds),
    onSuccess: (updated, variables) => {
      if (sourceRef.current !== variables.sourceCode) return;
      const syncedAt = Date.parse(updated.updated_at);
      void saveLocalDraft({
        sessionId: updated.id,
        questionSlug: updated.question_slug,
        sourceCode: variables.sourceCode,
        elapsedSeconds: variables.elapsedSeconds,
        localUpdatedAt: Number.isFinite(syncedAt) ? syncedAt : Date.now(),
        serverUpdatedAt: updated.updated_at,
      });
      setNotice("Synced");
    },
    onError: () => setNotice("Saved on device · server sync pending"),
  });

  const runMutation = useMutation({
    mutationFn: () => runPracticeCode(slug!, session!.id, source),
    onSuccess: (result) => {
      setExecution(result);
      setSubmission(null);
      setNotice("Run completed");
      if (!isTablet) setPane("results");
    },
    onError: () => setNotice("Execution unavailable"),
  });

  const submitMutation = useMutation({
    mutationFn: (idempotencyKey: string) =>
      submitPracticeCode(slug!, session!.id, source, idempotencyKey),
    onSuccess: (result) => {
      setExecution(result.execution);
      setSubmission(result);
      setNotice("Submission evaluated and saved");
      void removeLocalDraft(result.practice_session_id);
      void queryClient.invalidateQueries({ queryKey: queryKeys.me.readiness });
      void queryClient.invalidateQueries({ queryKey: queryKeys.me.competencies });
      void queryClient.invalidateQueries({ queryKey: queryKeys.me.evidence });
      void queryClient.invalidateQueries({ queryKey: queryKeys.me.nextAction });
      void queryClient.invalidateQueries({ queryKey: queryKeys.submissions.root });
      if (!isTablet) setPane("results");
    },
    onError: () => setNotice("Submission was not confirmed · safe to retry"),
  });

  const hintMutation = useMutation({
    mutationFn: () => revealHint(session!.id),
    onSuccess: (result) => setHint(result.text),
    onError: () => setHint("No additional hint is available."),
  });

  useEffect(() => {
    const item = question.data;
    if (!item || initialized.current) return;
    initialized.current = true;
    if (!item.starter_code?.trimStart().startsWith("def ")) {
      setNotice("Guided study only · executable workspace unavailable for this question type");
      return;
    }
    sessionMutation.mutate();
  }, [question.data, sessionMutation]);

  useEffect(() => {
    if (!session || submission) return;
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [session, submission]);

  useEffect(() => {
    if (!session || submission || !source) return;
    const timer = setTimeout(() => {
      void saveLocalDraft({
        sessionId: session.id,
        questionSlug: session.question_slug,
        sourceCode: source,
        elapsedSeconds: elapsed,
        localUpdatedAt: Date.now(),
        serverUpdatedAt: session.updated_at,
      });
      setNotice("Saved on device");
    }, 350);
    return () => clearTimeout(timer);
  }, [elapsed, session, source, submission]);

  useEffect(() => {
    if (!session || submission || !source) return;
    const timer = setTimeout(() => {
      saveMutation.mutate({ sourceCode: source, elapsedSeconds: elapsed });
    }, 1200);
    return () => clearTimeout(timer);
  }, [elapsed, session, source, submission, saveMutation]);

  if (!slug) {
    return (
      <Screen>
        <StateMessage title="Question not found" detail="The practice link is missing a question slug." />
      </Screen>
    );
  }

  if (question.isLoading) {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Preparing practice workspace" />
      </Screen>
    );
  }

  if (question.isError || !question.data) {
    return (
      <Screen>
        <StateMessage
          title="Published question unavailable"
          detail="Only candidate-safe published questions can open in practice."
        />
        <PrimaryButton label="Back to practice" onPress={() => router.replace("/practice")} />
      </Screen>
    );
  }

  const item = question.data;
  const executable = item.starter_code?.trimStart().startsWith("def ") ?? false;
  const busy = !session || runMutation.isPending || submitMutation.isPending;

  const problemView = (
    <View style={styles.stack}>
      <View style={styles.headerRow}>
        <View style={styles.flex}>
          <Text style={styles.questionId}>{item.external_id}</Text>
          <Text accessibilityRole="header" style={styles.title}>
            {item.title}
          </Text>
        </View>
        <Tag>{item.difficulty}</Tag>
      </View>
      <Text style={mobileStyles.body}>{item.problem_statement}</Text>
      <Text style={styles.cardTitle}>Instructions</Text>
      {item.candidate_instructions.map((instruction) => (
        <Text key={instruction} style={mobileStyles.body}>
          • {instruction}
        </Text>
      ))}
      <Text style={styles.cardTitle}>Public constraints</Text>
      {item.public_constraints.map((constraint) => (
        <Text key={constraint} style={mobileStyles.body}>
          • {constraint}
        </Text>
      ))}
      {item.public_examples.map((example) => (
        <Card key={example.id}>
          <Text style={styles.cardTitle}>{example.name}</Text>
          <Text selectable style={styles.codeSmall}>
            {JSON.stringify(
              { input: example.input, expected_output: example.expected_output },
              null,
              2,
            )}
          </Text>
        </Card>
      ))}
      {executable ? (
        <>
          <PrimaryButton
            label="Reveal next hint"
            variant="secondary"
            busy={hintMutation.isPending}
            disabled={!session}
            onPress={() => hintMutation.mutate()}
          />
          {hint ? (
            <Card>
              <Eyebrow>HINT</Eyebrow>
              <Text style={mobileStyles.body}>{hint}</Text>
            </Card>
          ) : null}
        </>
      ) : (
        <Card>
          <Text style={mobileStyles.body}>
            This question is available for guided study, but its current mode does not expose an executable Python function workspace.
          </Text>
        </Card>
      )}
    </View>
  );

  const editorView = (
    <View style={styles.stack}>
      <View style={styles.editorHeader}>
        <Eyebrow>PYTHON 3.13</Eyebrow>
        <Text style={mobileStyles.small}>
          {Math.floor(elapsed / 60).toString().padStart(2, "0")}:
          {(elapsed % 60).toString().padStart(2, "0")} · {notice}
        </Text>
      </View>
      <TextInput
        accessibilityLabel="Python source code"
        autoCapitalize="none"
        autoCorrect={false}
        editable={Boolean(session) && !submission}
        multiline
        onChangeText={(value) => {
          setSource(value);
          setNotice("Unsynced changes");
        }}
        selectTextOnFocus={false}
        spellCheck={false}
        style={styles.editor}
        textAlignVertical="top"
        value={source}
      />
      <View style={styles.actions}>
        <View style={styles.action}>
          <PrimaryButton
            label="Run public tests"
            variant="secondary"
            busy={runMutation.isPending}
            disabled={busy || !source || Boolean(submission)}
            onPress={() => runMutation.mutate()}
          />
        </View>
        <View style={styles.action}>
          <PrimaryButton
            label="Submit"
            busy={submitMutation.isPending}
            disabled={busy || !source || Boolean(submission)}
            onPress={() => submitMutation.mutate(`mobile-submit-${Crypto.randomUUID()}`)}
          />
        </View>
      </View>
      <Text style={mobileStyles.small}>
        Drafts are persisted on-device first and synchronized to the shared practice session. A failed network request never counts as a confirmed submission.
      </Text>
    </View>
  );

  return (
    <Screen>
      {!isTablet ? <PaneTabs pane={pane} onChange={setPane} /> : null}
      {isTablet ? (
        <View style={styles.tabletLayout}>
          <View style={styles.tabletPane}>{problemView}</View>
          <View style={styles.tabletPane}>
            {editorView}
            <ResultView execution={execution} submission={submission} />
          </View>
        </View>
      ) : pane === "problem" ? (
        problemView
      ) : pane === "editor" ? (
        editorView
      ) : (
        <ResultView execution={execution} submission={submission} />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  stack: { gap: spacing.md },
  tabletLayout: { flexDirection: "row", alignItems: "flex-start", gap: spacing.lg },
  tabletPane: { flex: 1, minWidth: 0, gap: spacing.lg },
  tabs: {
    flexDirection: "row",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    overflow: "hidden",
  },
  tab: { flex: 1, minHeight: 44, alignItems: "center", justifyContent: "center" },
  tabActive: { backgroundColor: colors.surfaceRaised },
  tabText: { color: colors.textMuted, fontSize: 12, fontWeight: "700" },
  tabTextActive: { color: colors.primary },
  headerRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  questionId: { color: colors.primary, fontSize: 12, fontWeight: "700" },
  title: { color: colors.text, fontSize: 26, fontWeight: "800", lineHeight: 32 },
  cardTitle: { color: colors.text, fontSize: 16, fontWeight: "800" },
  editorHeader: { gap: spacing.xs },
  editor: {
    minHeight: 420,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: "#070B15",
    color: colors.text,
    padding: spacing.md,
    fontFamily: "monospace",
    fontSize: 14,
    lineHeight: 21,
  },
  actions: { flexDirection: "row", gap: spacing.sm },
  action: { flex: 1 },
  resultHeader: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md },
  codeSmall: {
    color: colors.text,
    fontFamily: "monospace",
    fontSize: 12,
    lineHeight: 18,
  },
  score: { color: colors.primary, fontSize: 42, fontWeight: "900" },
});
