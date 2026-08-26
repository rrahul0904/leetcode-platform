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

export default function CandidateHomeScreen() {
  const readiness = useQuery({
    queryKey: queryKeys.me.readiness,
    queryFn: ({ signal }) => getReadiness(signal),
  });
  const nextAction = useQuery({
    queryKey: queryKeys.me.nextAction,
    queryFn: ({ signal }) => getNextAction(signal),
  });
  const submissions = useQuery({
    queryKey: queryKeys.submissions.root,
    queryFn: ({ signal }) => getSubmissions(signal),
  });

  if (readiness.isLoading) {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Calculating your next move" />
      </Screen>
    );
  }

  if (readiness.isError || !readiness.data) {
    return (
      <Screen>
        <StateMessage
          title="Readiness is unavailable"
          detail="Your canonical profile is still safe. Reconnect and retry when the API is available."
        />
        <PrimaryButton label="Retry" onPress={() => void readiness.refetch()} />
      </Screen>
    );
  }

  const data = readiness.data;
  const recent = submissions.data?.slice(0, 3) ?? [];
  const next = nextAction.data;

  return (
    <Screen>
      <View style={styles.header}>
        <Eyebrow>YOUR RIGOR PLAN</Eyebrow>
        <PageTitle
          title="What should you work on next?"
          description={`${data.target_role} readiness is based on persisted evidence, not browsing activity.`}
        />
      </View>

      <View style={styles.metrics}>
        <Metric label="Readiness" value={percent(data.overall.score)} />
        <Metric label="Confidence" value={percent(data.overall.confidence)} />
        <Metric label="Evidence" value={String(data.evidence_count)} />
      </View>

      <Card>
        <Eyebrow>NEXT RECOMMENDED EXERCISE</Eyebrow>
        {next ? (
          <>
            <SectionTitle>{next.title}</SectionTitle>
            <Text style={mobileStyles.body}>{next.reasons[0]}</Text>
            {next.competency_slug ? <Tag>{next.competency_slug}</Tag> : null}
            <PrimaryButton
              label="Open recommended practice"
              onPress={() => router.push(`/practice/${next.source_id}`)}
            />
          </>
        ) : (
          <>
            <SectionTitle>Choose your first published exercise</SectionTitle>
            <Text style={mobileStyles.body}>
              Complete an evaluated submission to establish an evidence baseline.
            </Text>
            <PrimaryButton label="Browse practice" onPress={() => router.push("/practice")} />
          </>
        )}
      </Card>

      <View style={styles.twoColumn}>
        <Card>
          <Eyebrow>STRONGEST SKILLS</Eyebrow>
          {data.strongest_areas.length ? (
            data.strongest_areas.map((item) => (
              <View key={item.competency_id} style={styles.skillRow}>
                <View style={styles.flex}>
                  <Text style={styles.skillTitle}>{item.name}</Text>
                  <Text style={mobileStyles.small}>
                    {item.evidence_count} evidence · {percent(item.confidence)} confidence
                  </Text>
                </View>
                <Text style={styles.score}>{percent(item.score)}</Text>
              </View>
            ))
          ) : (
            <Text style={mobileStyles.small}>Strengths appear after evaluated evidence exists.</Text>
          )}
        </Card>

        <Card>
          <Eyebrow>CRITICAL GAPS</Eyebrow>
          {data.critical_gaps.length ? (
            data.critical_gaps.map((item) => (
              <View key={item.competency_id} style={styles.skillRow}>
                <View style={styles.flex}>
                  <Text style={styles.skillTitle}>{item.name}</Text>
                  <Text style={mobileStyles.small}>{item.trend}</Text>
                </View>
                <Text style={styles.score}>{percent(item.score)}</Text>
              </View>
            ))
          ) : (
            <Text style={mobileStyles.small}>No measured gaps yet.</Text>
          )}
        </Card>
      </View>

      <Card>
        <View style={styles.sectionHeader}>
          <Eyebrow>RECENT ACTIVITY</Eyebrow>
          <PrimaryButton
            label="View progress"
            variant="secondary"
            onPress={() => router.push("/progress")}
          />
        </View>
        {recent.length ? (
          recent.map((submission) => (
            <View key={submission.id} style={styles.activityRow}>
              <View style={styles.flex}>
                <Text style={styles.skillTitle}>{submission.question_title}</Text>
                <Text style={mobileStyles.small}>
                  {new Date(submission.submitted_at).toLocaleString()}
                </Text>
              </View>
              <Tag>{submission.status}</Tag>
            </View>
          ))
        ) : (
          <Text style={mobileStyles.small}>No evaluated submissions yet.</Text>
        )}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { gap: 8 },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  twoColumn: { gap: 16 },
  flex: { flex: 1 },
  skillRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  skillTitle: { color: "#F7F9FC", fontSize: 16, fontWeight: "700" },
  score: { color: "#8FA8FF", fontSize: 18, fontWeight: "800" },
  sectionHeader: { gap: 12 },
  activityRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 8,
  },
});
