import { Text } from "react-native";

import {
  Card,
  Eyebrow,
  PageTitle,
  Screen,
  SectionTitle,
  Tag,
  mobileStyles,
} from "../../../src/ui/primitives";

export default function InterviewsScreen() {
  return (
    <Screen>
      <Eyebrow>INTERVIEWS</Eyebrow>
      <PageTitle
        title="Mock interview workflows"
        description="Rigor will expose interview sessions here only after they are durable backend records shared across clients."
      />
      <Card>
        <Tag>FOUNDATION</Tag>
        <SectionTitle>Shared interview history is not wired yet</SectionTitle>
        <Text style={mobileStyles.body}>
          The current web mock-interview surface is a deterministic local timer and explicitly does not persist or score a session. The mobile client does not manufacture a separate interview history or pretend local state is canonical.
        </Text>
        <Text style={mobileStyles.small}>
          The next interview milestone is a FastAPI interview-session model with shared session state, evidence capture, authorization, and cross-device history. Until that exists, this tab remains intentionally non-destructive and read-safe.
        </Text>
      </Card>
    </Screen>
  );
}
