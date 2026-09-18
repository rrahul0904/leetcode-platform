import { Redirect } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { useAuth } from "../src/auth/provider";
import {
  Card,
  Eyebrow,
  PageTitle,
  PrimaryButton,
  Screen,
  StateMessage,
  mobileStyles,
} from "../src/ui/primitives";

export default function SignInScreen() {
  const { status, error, signIn } = useAuth();

  if (status === "authenticated") return <Redirect href="/home" />;
  if (status === "restoring") {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Checking your secure session" />
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={styles.hero}>
        <Eyebrow>RIGOR INTERVIEW SYSTEMS LAB</Eyebrow>
        <PageTitle
          title="Practice like the interview matters."
          description="One candidate profile across web, iPhone, iPad, and Android. Your submissions, evidence, and readiness stay on the shared backend."
        />
      </View>
      <Card>
        <Text style={mobileStyles.body}>
          Sign in through the platform identity provider. Native authentication uses Authorization Code + PKCE and stores tokens in the device secure store.
        </Text>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <PrimaryButton
          label={status === "authenticating" ? "Opening secure sign-in…" : "Sign in"}
          busy={status === "authenticating"}
          onPress={() => void signIn()}
        />
        {__DEV__ ? (
          <Text style={mobileStyles.small}>
            Local development uses the repository&apos;s local OIDC candidate identity. Production uses the configured OIDC issuer and public mobile client ID.
          </Text>
        ) : null}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: {
    gap: 12,
    marginTop: 48,
  },
  error: {
    color: "#FF7A8A",
    lineHeight: 22,
  },
});
