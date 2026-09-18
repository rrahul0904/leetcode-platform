import { Redirect } from "expo-router";

import { useAuth } from "../src/auth/provider";
import { Screen, StateMessage } from "../src/ui/primitives";

export default function IndexScreen() {
  const { status } = useAuth();

  if (status === "restoring" || status === "authenticating") {
    return (
      <Screen scroll={false}>
        <StateMessage loading title="Restoring your Rigor session" />
      </Screen>
    );
  }

  if (status === "anonymous") {
    return <Redirect href="/sign-in" />;
  }

  return <Redirect href="/home" />;
}
