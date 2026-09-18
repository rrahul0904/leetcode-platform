import { SignUp } from "@clerk/nextjs";
import { redirect } from "next/navigation";

export default function SignUpPage() {
  if (process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE !== "clerk") {
    redirect("/sign-in");
  }

  return (
    <main className="sign-in-page">
      <SignUp fallbackRedirectUrl="/onboarding" signInUrl="/sign-in" />
    </main>
  );
}
