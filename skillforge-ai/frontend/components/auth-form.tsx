"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Use at least 8 characters"),
  displayName: z.string().max(80).optional(),
});

type FormValues = z.infer<typeof schema>;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    defaultValues: { email: "", password: "", displayName: "" },
  });

  async function submit(values: FormValues) {
    setError("");
    setNotice("");
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check the form and try again.");
      return;
    }
    setBusy(true);
    try {
      const supabase = createSupabaseBrowserClient();
      if (mode === "login") {
        const { error: authError } = await supabase.auth.signInWithPassword({
          email: parsed.data.email,
          password: parsed.data.password,
        });
        if (authError) throw authError;
        router.replace("/dashboard");
        router.refresh();
      } else {
        const { data, error: authError } = await supabase.auth.signUp({
          email: parsed.data.email,
          password: parsed.data.password,
          options: { data: { display_name: parsed.data.displayName || parsed.data.email.split("@")[0] } },
        });
        if (authError) throw authError;
        if (data.session) {
          router.replace("/dashboard");
          router.refresh();
        } else {
          setNotice("Account created. Check your email to confirm the address, then sign in.");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return <main className="min-h-screen bg-[#0b0d10] text-white flex items-center justify-center p-6">
    <section className="w-full max-w-md rounded-3xl border border-white/10 bg-white/[0.035] p-8 shadow-2xl">
      <Link href="/" className="text-sm text-white/55 hover:text-white">← SkillForge AI</Link>
      <div className="mt-8">
        <p className="text-xs uppercase tracking-[0.22em] text-violet-300">Secure workspace</p>
        <h1 className="mt-3 text-3xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="mt-2 text-sm leading-6 text-white/55">{mode === "login" ? "Sign in to sync attempts, bookmarks and readiness progress." : "Create a Supabase-backed account for personalized interview preparation."}</p>
      </div>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit(submit)}>
        {mode === "signup" && <label className="block text-sm text-white/70">Display name
          <input {...register("displayName")} className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 outline-none focus:border-violet-400" placeholder="Rahul" />
        </label>}
        <label className="block text-sm text-white/70">Email
          <input type="email" {...register("email")} className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 outline-none focus:border-violet-400" placeholder="you@example.com" />
          {errors.email && <span className="mt-1 block text-xs text-red-300">{errors.email.message}</span>}
        </label>
        <label className="block text-sm text-white/70">Password
          <input type="password" {...register("password")} className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-4 py-3 outline-none focus:border-violet-400" placeholder="••••••••" />
          {errors.password && <span className="mt-1 block text-xs text-red-300">{errors.password.message}</span>}
        </label>
        {error && <div className="rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-200">{error}</div>}
        {notice && <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200">{notice}</div>}
        <button disabled={busy} className="w-full rounded-xl bg-white px-4 py-3 font-semibold text-black transition hover:bg-violet-100 disabled:opacity-50">
          {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-white/50">
        {mode === "login" ? "New to SkillForge? " : "Already have an account? "}
        <Link className="text-violet-300 hover:text-violet-200" href={mode === "login" ? "/signup" : "/login"}>{mode === "login" ? "Create account" : "Sign in"}</Link>
      </p>
    </section>
  </main>;
}
