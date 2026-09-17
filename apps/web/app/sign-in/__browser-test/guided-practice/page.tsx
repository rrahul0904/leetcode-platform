import { notFound } from "next/navigation";

import { GuidedPracticeBrowserHarness } from "./browser-harness";

export default function GuidedPracticeBrowserTestPage() {
  if (process.env.SKILLFORGE_BROWSER_TEST_HARNESS !== "1") notFound();

  return <GuidedPracticeBrowserHarness />;
}
