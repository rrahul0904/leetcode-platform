import { ApiError } from "@rigor/api-client/client";
import { queryKeys } from "@rigor/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Redirect, router } from "expo-router";
import { Text } from "react-native";

import { getProfile, putProfile } from "../../src/api/candidate";
import type { CandidateProfileInput } from "../../src/api/types";
import { useAuth } from "../../src/auth/provider";
import { CandidateProfileEditor } from "../../src/profile/editor";
import { Eyebrow, PageTitle, Screen, StateMessage, mobileStyles } from "../../src/ui/primitives";

export default function OnboardingScreen() {
  const { status } = useAuth();
  const queryClient = useQueryClient();
  const profile = useQuery({
    queryKey: queryKeys.me.profile,
    queryFn: ({ signal }) => getProfile(signal),
    retry: false,
    enabled: status === "authenticated",
  });
  const save = useMutation({
    mutationFn: (input: CandidateProfileInput) => putProfile(input),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.me.profile, saved);
      void queryClient.invalidateQueries({ queryKey: queryKeys.me.nextAction });
      router.replace("/home");
    },
  });

  if (status === "anonymous") return <Redirect href="/sign-in" />;
  if (status !== "authenticated" || profile.isLoading) {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Preparing candidate profile" />
      </Screen>
    );
  }

  const missingProfile = profile.error instanceof ApiError && profile.error.status === 404;
  if (profile.isError && !missingProfile) {
    return (
      <Screen>
        <StateMessage title="Profile service unavailable" detail="Your account is signed in, but the candidate profile could not be loaded." />
      </Screen>
    );
  }

  return (
    <Screen>
      <Eyebrow>{profile.data ? "EDIT CANDIDATE PROFILE" : "FIRST-LOGIN ONBOARDING"}</Eyebrow>
      <PageTitle
        title={
          profile.data
            ? "Keep the preparation plan aligned with your target."
            : "Turn a target interview into a bounded preparation system."
        }
        description="This profile is stored in the shared backend and is the same profile used by web, iOS, and Android."
      />
      {save.isError ? (
        <Text accessibilityRole="alert" style={mobileStyles.body}>
          The profile could not be saved. Review the fields and retry.
        </Text>
      ) : null}
      <CandidateProfileEditor
        initial={profile.data}
        saving={save.isPending}
        onSave={async (input) => {
          await save.mutateAsync(input);
        }}
      />
    </Screen>
  );
}
