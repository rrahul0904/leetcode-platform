import { SignIn as ClerkSignIn } from "@clerk/nextjs";
import { Suspense } from "react";

import { SignIn as LocalSignIn } from "@/components/sign-in";

export default function SignInPage() {
  if (process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE === "clerk") {
    return (
      <main className="sign-in-page">
        <ClerkSignIn fallbackRedirectUrl="/onboarding" signUpUrl="/sign-up" />
      </main>
    );
  }

  return (
    <Suspense>
      <LocalSignIn />
    </Suspense>
  );
}
