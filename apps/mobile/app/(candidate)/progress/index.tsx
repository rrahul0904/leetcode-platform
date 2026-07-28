import { colors, radius, spacing } from "@rigor/design-tokens";
import { queryKeys } from "@rigor/query";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { getNextAction, getReadiness, getSubmissions } from "../../../src/api/candidate";
import {
  Card,
  Eyebrow,
  Metric,
  PageTitle,
  PrimaryButton,
  Screen,
  SectionTitle,
  StateMessage,
  Tag,
  mobileStyles,
} from "../../../src/ui/primitives";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export default function ProgressScreen() {
  const readiness = useQuery({
    queryKey: queryKeys.me.readiness,
    queryFn: ({ signal }) => getReadiness(signal),
  });
  const submissions = useQuery({
    queryKey: queryKeys.submissions.root,
    queryFn: ({ signal }) => getSubmissions(signal),
  });
  const nextAction = useQuery({
    queryKey: queryKeys.me.nextAction,
    queryFn: ({ signal }) => getNextAction(signal),
  });

  if (readiness.isLoading || submissions.isLoading) {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Reading evidence-backed progress" />
      </Screen>
    );
  }

  if (!readiness.data) {
    return (
      <Screen>
        <StateMessage title="Progress unavailable" detail="The readiness service could not be reached." />
        <PrimaryButton label="Retry" onPress={() => void readiness.refetch()} />
      </Screen>
    );
  }

  const data = readiness.data;
  const history = submissions.data ?? [];

  return (
    <Screen>
      <Eyebrow>PROGRESS & READINESS</Eyebrow>
      <PageTitle
        title="Evidence, confidence, and the next useful move."
        description="Readiness is calculated by the backend from persisted evidence. The mobile client never reimplements the readiness model."
      />
      <View style={styles.metrics}>
        <Metric label="Role readiness" value={percent(data.overall.score)} detail={data.target_role} />
        <Metric label="Confidence" value={percent(data.overall.confidence)} />
        <Metric label="Evidence points" value={String(data.evidence_count)} />
        <Metric label="Submissions" value={String(history.length)} />
      </View>

      {nextAction.data ? (
        <Card>
          <Eyebrow>NEXT ACTION</Eyebrow>
          <SectionTitle>{nextAction.data.title}</SectionTitle>
          <Text style={mobileStyles.body}>{nextAction.data.reasons[0]}</Text>
          <PrimaryButton
            label="Start recommended practice"
            onPress={() => router.push(`/practice/${nextAction.data!.source_id}`)}
          />
        </Card>
      ) : null}

      <Card>
        <Eyebrow>COMPETENCY READINESS</Eyebrow>
        {data.competencies.length ? (
          data.competencies.map((competency) => (
            <View key={competency.competency_id} style={styles.competency}>
              <View style={styles.rowBetween}>
                <View style={styles.flex}>
                  <Text style={styles.title}>{competency.name}</Text>
                  <Text style={mobileStyles.small}>
                    {competency.evidence_count} evidence · {competency.trend}
                  </Text>
                </View>
                <Text style={styles.percent}>{percent(competency.score)}</Text>
              </View>
              <View style={styles.track}>
                <View
                  style={[
                    styles.fill,
                    { width: `${Math.max(0, Math.min(100, competency.score * 100))}%` },
                  ]}
                />
              </View>
              <Text style={mobileStyles.small}>
                {percent(competency.confidence)} confidence
              </Text>
            </View>
          ))
        ) : (
          <Text style={mobileStyles.body}>
            Complete an evaluated hosted submission to establish competency evidence.
          </Text>
        )}
      </Card>

      <Card>
        <Eyebrow>SUBMISSION HISTORY</Eyebrow>
        {history.length ? (
          history.map((submission) => (
            <View key={submission.id} style={styles.historyRow}>
              <View style={styles.flex}>
                <Text style={styles.title}>{submission.question_title}</Text>
                <Text style={mobileStyles.small}>
                  {new Date(submission.submitted_at).toLocaleString()} · {submission.runtime}
                </Text>
              </View>
              <View style={styles.historyScore}>
                <Tag>{submission.status}</Tag>
                <Text style={styles.percent}>
                  {percent(submission.evaluation.overall_score)}
                </Text>
              </View>
            </View>
          ))
        ) : (
          <Text style={mobileStyles.small}>No evaluated submission attempts yet.</Text>
        )}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  flex: { flex: 1 },
  rowBetween: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  title: { color: colors.text, fontSize: 16, fontWeight: "700" },
  percent: { color: colors.primary, fontSize: 18, fontWeight: "800" },
  competency: { gap: spacing.sm, paddingVertical: spacing.sm },
  track: {
    height: 8,
    borderRadius: radius.pill,
    overflow: "hidden",
    backgroundColor: colors.surfaceRaised,
  },
  fill: { height: "100%", backgroundColor: colors.primary },
  historyRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  historyScore: { alignItems: "flex-end", gap: spacing.xs },
});
