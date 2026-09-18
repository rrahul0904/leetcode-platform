import { ApiError } from "@rigor/api-client/client";
import { queryKeys } from "@rigor/query";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { getProfile } from "../../../src/api/candidate";
import { useAuth } from "../../../src/auth/provider";
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

export default function ProfileScreen() {
  const { principal, signOut } = useAuth();
  const profile = useQuery({
    queryKey: queryKeys.me.profile,
    queryFn: ({ signal }) => getProfile(signal),
    retry: false,
  });

  if (profile.isLoading) {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Loading candidate profile" />
      </Screen>
    );
  }

  const missing = profile.error instanceof ApiError && profile.error.status === 404;
  if (missing) {
    return (
      <Screen>
        <Eyebrow>PROFILE</Eyebrow>
        <PageTitle title="Finish setting up your target." />
        <Card>
          <Text style={mobileStyles.body}>
            Your authenticated account exists, but a candidate preparation profile has not been saved yet.
          </Text>
          <PrimaryButton label="Complete onboarding" onPress={() => router.push("/onboarding")} />
        </Card>
      </Screen>
    );
  }

  if (profile.isError || !profile.data) {
    return (
      <Screen>
        <StateMessage title="Profile unavailable" detail="Reconnect and retry when the API is available." />
        <PrimaryButton label="Retry" onPress={() => void profile.refetch()} />
      </Screen>
    );
  }

  const data = profile.data;
  return (
    <Screen>
      <Eyebrow>PROFILE</Eyebrow>
      <PageTitle
        title="Your preparation target"
        description="This is shared candidate state from FastAPI/PostgreSQL, not a device-only profile."
      />
      <Card>
        <Text style={styles.label}>Signed in as</Text>
        <Text style={styles.value}>{principal?.email ?? principal?.subject_id ?? "Candidate"}</Text>
        <Text style={styles.label}>Experience level</Text>
        <Text style={styles.value}>{data.experience_level}</Text>
        <Text style={styles.label}>Preferred practice language</Text>
        <Text style={styles.value}>{data.preferred_programming_language}</Text>
        <Text style={styles.label}>Weekly study time</Text>
        <Text style={styles.value}>{data.weekly_study_hours} hours</Text>
        <Text style={styles.label}>Preparation intensity</Text>
        <Text style={styles.value}>{data.preparation_intensity}</Text>
      </Card>
      <Card>
        <Eyebrow>TARGET ROLES</Eyebrow>
        <View style={styles.tags}>
          {data.target_roles.map((role) => <Tag key={role}>{role}</Tag>)}
        </View>
        {data.target_companies?.length ? (
          <>
            <Text style={styles.label}>Target context</Text>
            <Text style={mobileStyles.body}>{data.target_companies.join(", ")}</Text>
          </>
        ) : null}
      </Card>
      <PrimaryButton label="Edit candidate profile" onPress={() => router.push("/onboarding")} />
      <PrimaryButton label="Sign out" variant="secondary" onPress={() => void signOut()} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  label: { color: "#A9B4C8", fontSize: 13, fontWeight: "700" },
  value: { color: "#F7F9FC", fontSize: 18, fontWeight: "700" },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
