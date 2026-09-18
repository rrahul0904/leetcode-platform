import { colors, radius, spacing } from "@rigor/design-tokens";
import { queryKeys } from "@rigor/query";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useDeferredValue, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { getQuestions } from "../../../src/api/candidate";
import type { CatalogQuestion } from "../../../src/api/types";
import {
  Card,
  Eyebrow,
  PageTitle,
  PrimaryButton,
  Screen,
  StateMessage,
  Tag,
  mobileStyles,
} from "../../../src/ui/primitives";

function QuestionRow({ question }: { question: CatalogQuestion }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Open ${question.title}`}
      onPress={() => router.push(`/practice/${question.slug}`)}
      style={({ pressed }) => [styles.questionRow, pressed && styles.pressed]}
    >
      <View style={styles.questionHeading}>
        <View style={styles.flex}>
          <Text style={styles.questionId}>{question.external_id}</Text>
          <Text style={styles.questionTitle}>{question.title}</Text>
        </View>
        <Tag>{question.difficulty}</Tag>
      </View>
      <Text style={mobileStyles.small} numberOfLines={2}>
        {question.learning_objectives[0] ?? "Practice this published interview skill."}
      </Text>
      <View style={styles.tags}>
        {question.skills.slice(0, 3).map((skill) => (
          <Tag key={skill}>{skill}</Tag>
        ))}
      </View>
      <Text style={mobileStyles.small}>
        {question.track} · {question.estimated_duration_minutes} min · {question.role_level}
      </Text>
    </Pressable>
  );
}

export default function PracticeCatalogScreen() {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const filters = useMemo(
    () => ({ query: deferredQuery, page: 1, pageSize: 30, sort: "relevance" }),
    [deferredQuery],
  );
  const questions = useQuery({
    queryKey: queryKeys.questions.list(filters),
    queryFn: ({ signal }) => getQuestions(filters, signal),
  });

  return (
    <Screen>
      <Eyebrow>PRACTICE</Eyebrow>
      <PageTitle
        title="Published interview questions"
        description="These are candidate-safe projections from the same question bank used on the web. Hidden tests, solutions, rubrics, and interviewer-only content remain server-side."
      />
      <TextInput
        accessibilityLabel="Search published questions"
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="Search skills, systems, or objectives"
        placeholderTextColor={colors.textMuted}
        style={styles.search}
        value={query}
        onChangeText={setQuery}
      />

      {questions.isLoading ? (
        <StateMessage loading title="Loading published questions" />
      ) : null}
      {questions.isError ? (
        <Card>
          <StateMessage
            title="Question catalog unavailable"
            detail="Reconnect and retry. Draft or unpublished content will never be substituted for the candidate catalog."
          />
          <PrimaryButton label="Retry" onPress={() => void questions.refetch()} />
        </Card>
      ) : null}
      {questions.data ? (
        <>
          <Text style={mobileStyles.small}>
            {questions.data.total.toLocaleString()} published question
            {questions.data.total === 1 ? "" : "s"}
          </Text>
          <View style={styles.list}>
            {questions.data.items.map((question) => (
              <QuestionRow question={question} key={question.slug} />
            ))}
          </View>
          {questions.data.items.length === 0 ? (
            <Card>
              <Text style={mobileStyles.body}>No published questions match this search.</Text>
              <PrimaryButton label="Clear search" variant="secondary" onPress={() => setQuery("")} />
            </Card>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  search: {
    minHeight: 50,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    color: colors.text,
    paddingHorizontal: spacing.md,
    fontSize: 16,
  },
  list: { gap: spacing.md },
  questionRow: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  pressed: { opacity: 0.78 },
  questionHeading: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  questionId: { color: colors.primary, fontSize: 12, fontWeight: "700" },
  questionTitle: { color: colors.text, fontSize: 19, fontWeight: "800", marginTop: 4 },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
});
