import { Redirect } from "expo-router";

import { useAuth } from "../../src/auth/provider";
import { Screen, StateMessage } from "../../src/ui/primitives";

export default function AuthCallbackScreen() {
  const { status } = useAuth();

  if (status === "authenticated") return <Redirect href="/home" />;
  if (status === "anonymous") return <Redirect href="/sign-in" />;

  return (
    <Screen scroll={false}>
      <StateMessage loading title="Completing secure sign-in" />
    </Screen>
  );
}
