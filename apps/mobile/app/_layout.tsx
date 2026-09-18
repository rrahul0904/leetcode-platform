import { colors } from "@rigor/design-tokens";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { AuthProvider } from "../src/auth/provider";
import { MobileQueryProvider } from "../src/query/provider";

export default function RootLayout() {
  return (
    <MobileQueryProvider>
      <AuthProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: colors.background },
            headerTintColor: colors.text,
            contentStyle: { backgroundColor: colors.background },
          }}
        >
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="sign-in" options={{ headerShown: false }} />
          <Stack.Screen name="auth/callback" options={{ headerShown: false }} />
          <Stack.Screen name="onboarding/index" options={{ title: "Get started" }} />
          <Stack.Screen name="(candidate)" options={{ headerShown: false }} />
        </Stack>
      </AuthProvider>
    </MobileQueryProvider>
  );
}
