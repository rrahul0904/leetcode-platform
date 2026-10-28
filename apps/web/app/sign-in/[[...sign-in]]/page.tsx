import { SignIn as ClerkSignIn } from "@clerk/nextjs";
import { Suspense } from "react";

import { SignIn as LocalSignIn } from "@/components/sign-in";
import { safeSignInReturnPath } from "@/lib/assessment-invitation-link";

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ returnTo?: string | string[] }>;
}) {
  const params = await searchParams;
  const returnTo = safeSignInReturnPath(
    typeof params.returnTo === "string" ? params.returnTo : null,
  );
  if (process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE === "clerk") {
    return (
      <main className="sign-in-page">
        <ClerkSignIn fallbackRedirectUrl={returnTo} forceRedirectUrl={returnTo} signUpUrl="/sign-up" />
      </main>
    );
  }

  return (
    <Suspense>
      <LocalSignIn />
    </Suspense>
  );
}
