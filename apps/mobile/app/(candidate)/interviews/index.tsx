import { colors, radius, spacing } from "@rigor/design-tokens";
import { useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";

import {
  answerMockInterview,
  createMockInterview,
  getMockInterview,
  getMockInterviews,
  getMockInterviewTemplates,
  updateMockInterviewState,
} from "../../../src/api/candidate";
import type {
  MockInterviewSession,
  MockInterviewSessionSummary,
  MockInterviewTemplate,
} from "../../../src/api/types";
import {
  Card,
  Eyebrow,
  PageTitle,
  PrimaryButton,
  Screen,
  SectionTitle,
  StateMessage,
  Tag,
  mobileStyles,
} from "../../../src/ui/primitives";

type BusyState = "load" | "create" | "open" | "answer" | "action" | null;

export default function InterviewsScreen() {
  const [templates, setTemplates] = useState<MockInterviewTemplate[]>([]);
  const [history, setHistory] = useState<MockInterviewSessionSummary[]>([]);
  const [session, setSession] = useState<MockInterviewSession | null>(null);
  const [selectedFocus, setSelectedFocus] = useState("");
  const [targetRole, setTargetRole] = useState("Senior Data Engineer");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState<BusyState>("load");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      getMockInterviewTemplates(controller.signal),
      getMockInterviews(controller.signal),
    ])
      .then(([templateItems, sessions]) => {
        setTemplates(templateItems);
        setHistory(sessions);
        if (templateItems.length > 0) {
          setSelectedFocus(templateItems[0].slug);
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : "Mock interviews failed to load.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(null);
      });
    return () => controller.abort();
  }, []);

  const selectedTemplate = useMemo(
    () => templates.find((item) => item.slug === selectedFocus) ?? null,
    [selectedFocus, templates],
  );

  const currentPrompt = useMemo(
    () =>
      [...(session?.messages ?? [])]
        .reverse()
        .find((message) => message.role === "interviewer") ?? null,
    [session?.messages],
  );

  async function refreshHistory() {
    setHistory(await getMockInterviews());
  }

  async function startInterview(template: MockInterviewTemplate) {
    if (!targetRole.trim() || busy) return;
    setBusy("create");
    setError(null);
    try {
      const created = await createMockInterview(template.slug, targetRole.trim());
      setSession(created);
      setSelectedFocus(created.focus);
      setAnswer("");
      await refreshHistory();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Interview could not start.");
    } finally {
      setBusy(null);
    }
  }

  async function openInterview(sessionId: string) {
    if (busy) return;
    setBusy("open");
    setError(null);
    try {
      const opened = await getMockInterview(sessionId);
      setSession(opened);
      setSelectedFocus(opened.focus);
      setAnswer("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Interview could not open.");
    } finally {
      setBusy(null);
    }
  }

  async function submitAnswer() {
    if (!session || !answer.trim() || busy || session.status !== "IN_PROGRESS") {
      return;
    }
    setBusy("answer");
    setError(null);
    try {
      const updated = await answerMockInterview(session.id, answer.trim());
      setSession(updated);
      setAnswer("");
      await refreshHistory();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Response could not be saved.");
    } finally {
      setBusy(null);
    }
  }

  async function act(action: "pause" | "resume" | "cancel") {
    if (!session || busy) return;
    setBusy("action");
    setError(null);
    try {
      setSession(await updateMockInterviewState(session.id, action));
      await refreshHistory();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Interview state could not change.",
      );
    } finally {
      setBusy(null);
    }
  }

  if (busy === "load" && templates.length === 0) {
    return (
      <Screen>
        <StateMessage
          loading
          title="Loading interview workspace"
          detail="Reading shared templates and candidate-owned interview history."
        />
      </Screen>
    );
  }

  return (
    <Screen>
      <Eyebrow>MOCK INTERVIEWS</Eyebrow>
      <PageTitle
        title="Practice the technical conversation"
        description="Web and mobile share the same candidate-owned sessions, phase responses, deterministic rubric evidence, reports, and readiness history."
      />

      {error ? (
        <StateMessage title="Interview workspace needs attention" detail={error} />
      ) : null}

      {session ? (
        <>
          <Card>
            <View style={mobileStyles.rowWrap}>
              <Tag>{session.focus_label}</Tag>
              <Tag>{session.status.replaceAll("_", " ")}</Tag>
            </View>
            <SectionTitle>{session.target_role}</SectionTitle>
            <Text style={mobileStyles.small}>
              Phase: {session.current_phase.replaceAll("-", " ")}
            </Text>
          </Card>

          {session.report ? (
            <Card>
              <Tag>INTERVIEW COMPLETE</Tag>
              <SectionTitle>
                Evidence score {Math.round(session.report.overall_score * 100)}/100
              </SectionTitle>
              <Text style={styles.reportLabel}>Strengths</Text>
              {session.report.strengths.map((item) => (
                <Text key={item} style={mobileStyles.body}>
                  • {item}
                </Text>
              ))}
              <Text style={styles.reportLabel}>Growth areas</Text>
              {session.report.growth_areas.map((item) => (
                <Text key={item} style={mobileStyles.body}>
                  • {item}
                </Text>
              ))}
              <Text style={styles.reportLabel}>Next steps</Text>
              {session.report.next_steps.map((item) => (
                <Text key={item} style={mobileStyles.body}>
                  • {item}
                </Text>
              ))}
            </Card>
          ) : (
            <Card>
              <Tag>{currentPrompt?.phase?.replaceAll("-", " ") ?? "INTERVIEW"}</Tag>
              <SectionTitle>
                {currentPrompt?.content ?? "Interview prompt is loading."}
              </SectionTitle>

              {session.messages
                .filter((message) => message.role === "candidate")
                .map((message) => (
                  <View key={message.id} style={styles.response}>
                    <Text style={styles.reportLabel}>
                      {message.phase.replaceAll("-", " ")}
                    </Text>
                    <Text style={mobileStyles.body}>{message.content}</Text>
                    {typeof message.evidence.score === "number" ? (
                      <Text style={mobileStyles.small}>
                        Phase evidence {Math.round(message.evidence.score * 100)}/100
                      </Text>
                    ) : null}
                  </View>
                ))}

              {session.status === "IN_PROGRESS" ? (
                <>
                  <TextInput
                    accessibilityLabel="Interview response"
                    multiline
                    onChangeText={setAnswer}
                    placeholder="State assumptions, trade-offs, evidence, and decisions clearly."
                    placeholderTextColor={colors.textMuted}
                    style={styles.answer}
                    value={answer}
                  />
                  <PrimaryButton
                    busy={busy === "answer"}
                    disabled={!answer.trim()}
                    label="Submit response"
                    onPress={() => void submitAnswer()}
                  />
                </>
              ) : null}

              <View style={styles.actions}>
                {session.status === "IN_PROGRESS" ? (
                  <PrimaryButton
                    busy={busy === "action"}
                    label="Pause interview"
                    onPress={() => void act("pause")}
                    variant="secondary"
                  />
                ) : null}
                {session.status === "PAUSED" ? (
                  <PrimaryButton
                    busy={busy === "action"}
                    label="Resume interview"
                    onPress={() => void act("resume")}
                  />
                ) : null}
                {session.status === "IN_PROGRESS" || session.status === "PAUSED" ? (
                  <PrimaryButton
                    busy={busy === "action"}
                    label="Cancel interview"
                    onPress={() => void act("cancel")}
                    variant="danger"
                  />
                ) : null}
              </View>
            </Card>
          )}

          <PrimaryButton
            label="Back to interview library"
            onPress={() => {
              setSession(null);
              setAnswer("");
              setError(null);
            }}
            variant="secondary"
          />
        </>
      ) : (
        <>
          <Card>
            <Tag>TARGET ROLE</Tag>
            <TextInput
              accessibilityLabel="Target role"
              maxLength={160}
              onChangeText={setTargetRole}
              placeholder="Senior Data Engineer"
              placeholderTextColor={colors.textMuted}
              style={styles.roleInput}
              value={targetRole}
            />
          </Card>

          <SectionTitle>Interview focus</SectionTitle>
          {templates.map((template) => (
            <Card key={template.slug}>
              <View style={mobileStyles.rowWrap}>
                <Tag>{template.phases.length} PHASES</Tag>
                {template.slug === selectedFocus ? <Tag>SELECTED</Tag> : null}
              </View>
              <SectionTitle>{template.label}</SectionTitle>
              <Text style={mobileStyles.body}>{template.description}</Text>
              <Text style={mobileStyles.small}>
                {template.competencies.join(" · ").replaceAll("-", " ")}
              </Text>
              <PrimaryButton
                busy={busy === "create" && template.slug === selectedFocus}
                disabled={!targetRole.trim()}
                label={`Start ${template.label}`}
                onPress={() => {
                  setSelectedFocus(template.slug);
                  void startInterview(template);
                }}
              />
            </Card>
          ))}

          <SectionTitle>Recent sessions</SectionTitle>
          {history.length === 0 ? (
            <Card>
              <Text style={mobileStyles.small}>
                Your first persisted mock interview will appear here on every client.
              </Text>
            </Card>
          ) : (
            history.slice(0, 12).map((item) => (
              <Card key={item.id}>
                <View style={mobileStyles.rowWrap}>
                  <Tag>{item.status.replaceAll("_", " ")}</Tag>
                  <Tag>{item.focus_label}</Tag>
                </View>
                <SectionTitle>{item.target_role}</SectionTitle>
                <Text style={mobileStyles.small}>
                  Current phase: {item.current_phase.replaceAll("-", " ")}
                </Text>
                <PrimaryButton
                  busy={busy === "open"}
                  label={item.status === "COMPLETED" ? "View report" : "Open session"}
                  onPress={() => void openInterview(item.id)}
                  variant="secondary"
                />
              </Card>
            ))
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  roleInput: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.text,
    backgroundColor: colors.surfaceRaised,
  },
  answer: {
    minHeight: 180,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    color: colors.text,
    backgroundColor: colors.surfaceRaised,
    textAlignVertical: "top",
  },
  response: {
    gap: spacing.xs,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  reportLabel: {
    color: colors.textMuted,
    fontWeight: "700",
    marginTop: spacing.sm,
  },
  actions: {
    gap: spacing.sm,
  },
});
