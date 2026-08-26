"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import {
  authConfigured,
  readableAuthError,
  signIn,
  signUp,
  watchUser,
} from "@/lib/auth";

/**
 * Sign in and sign up, on one surface.
 *
 * A film held in an account nobody else can reach is the entire privacy model,
 * so this is a real boundary rather than a formality. It is also the first
 * screen someone sees after the landing page, so it keeps the cinematic
 * register — the frame behind it, the same typography — without turning into
 * a second marketing page.
 */
export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignIn />
    </Suspense>
  );
}

function SignIn() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/projects";
  const [mode, setMode] = useState<"in" | "up">(
    params.get("mode") === "up" ? "up" : "in",
  );

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Someone who is already signed in should not be looking at this page.
  useEffect(
    () =>
      watchUser((user) => {
        if (user) router.replace(next);
      }),
    [router, next],
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "up") {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
      router.replace(next);
    } catch (caught) {
      setError(readableAuthError(caught));
      setBusy(false);
    }
  }

  return (
    <main id="main" className="relative flex min-h-screen items-center justify-center px-6 py-16">
      {/* The frame from the landing page, pushed well back. It keeps the two
          surfaces feeling like one product without competing with the form. */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/film/still.jpg"
          alt=""
          className="still h-full w-full object-cover opacity-[0.16]"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-ink-000 via-ink-000/85 to-ink-000" />
      </div>

      <div className="relative w-full max-w-sm">
        <Link href="/" className="font-display text-xl text-paper-000">
          Preflight
        </Link>

        <h1 className="mt-8 font-display text-3xl leading-tight text-paper-000">
          {mode === "up" ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-paper-300">
          {mode === "up"
            ? "Your account starts empty. Nothing is shared, and nothing is visible to anyone else."
            : "Sign in to prepare a finished film for delivery."}
        </p>

        <form onSubmit={submit} className="mt-8 space-y-4">
          <Field
            id="email"
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={setEmail}
            required
          />
          <Field
            id="password"
            label="Password"
            type="password"
            autoComplete={mode === "up" ? "new-password" : "current-password"}
            value={password}
            onChange={setPassword}
            required
            hint={mode === "up" ? "At least six characters." : undefined}
          />

          {error && (
            <p
              role="alert"
              className="rounded-[3px] border-l-2 border-stop bg-stop-bg/50 py-2.5 pl-3 pr-4
                         text-sm text-paper-100"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !authConfigured}
            className="w-full rounded-[3px] bg-paper-000 px-5 py-3 text-sm font-medium
                       text-ink-000 transition hover:bg-white disabled:opacity-50"
          >
            {busy
              ? mode === "up"
                ? "Creating your account…"
                : "Signing in…"
              : mode === "up"
                ? "Create account"
                : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-sm text-paper-300">
          {mode === "up" ? "Already have an account?" : "No account yet?"}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "up" ? "in" : "up");
              setError(null);
            }}
            className="text-paper-000 underline underline-offset-4"
          >
            {mode === "up" ? "Sign in" : "Create one"}
          </button>
        </p>

        {!authConfigured && (
          <p className="mt-6 text-xs text-paper-400">
            This deployment has no identity provider configured, so sign-in is
            unavailable.
          </p>
        )}
      </div>
    </main>
  );
}

function Field({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  required,
  hint,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  required?: boolean;
  hint?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="slate block text-paper-300">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        required={required}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3.5 py-2.5
                   text-[15px] text-paper-000 outline-none transition
                   placeholder:text-paper-400 focus:border-line-strong"
      />
      {hint && (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-paper-400">
          {hint}
        </p>
      )}
    </div>
  );
}
