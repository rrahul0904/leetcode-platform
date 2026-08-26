import { colors } from "@rigor/design-tokens";
import { Redirect, Tabs } from "expo-router";

import { useAuth } from "../../src/auth/provider";
import { Screen, StateMessage } from "../../src/ui/primitives";

export default function CandidateLayout() {
  const { status } = useAuth();

  if (status === "restoring" || status === "authenticating") {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Loading candidate workspace" />
      </Screen>
    );
  }

  if (status !== "authenticated") return <Redirect href="/sign-in" />;

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
      }}
    >
      <Tabs.Screen name="home" options={{ title: "Home", headerShown: false }} />
      <Tabs.Screen name="practice" options={{ title: "Practice", headerShown: false }} />
      <Tabs.Screen
        name="interviews"
        options={{ title: "Interviews", headerShown: false }}
      />
      <Tabs.Screen name="progress" options={{ title: "Progress", headerShown: false }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", headerShown: false }} />
    </Tabs>
  );
}
