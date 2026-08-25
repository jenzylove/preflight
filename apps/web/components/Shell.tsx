"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { User } from "firebase/auth";

import {
  authConfigured,
  readableAuthError,
  signIn,
  signOut,
  signUp,
  watchUser,
} from "@/lib/auth";

/**
 * Authentication gate and page chrome.
 *
 * Preflight holds unreleased films, so there is no anonymous browsing of
 * project state and no demo account with pre-seeded data. Signing in creates a
 * real, empty account.
 */
export function Shell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(
    () =>
      watchUser((u) => {
        setUser(u);
        setReady(true);
      }),
    [],
  );

  if (!authConfigured) {
    return (
      <Centered title="Sign-in is not configured">
        <p className="text-neutral-400">
          This deployment has no Firebase credentials, so accounts are
          unavailable. The API itself is running and its endpoints are
          documented at{" "}
          <a
            className="text-sky-400 underline"
            href={`${process.env.NEXT_PUBLIC_API_BASE_URL}/docs`}
          >
            /docs
          </a>
          .
        </p>
      </Centered>
    );
  }

  if (!ready) {
    return <Centered title="Preflight">
      <p className="text-neutral-500">Checking your session…</p>
    </Centered>;
  }

  if (!user) return <SignInForm />;

  return (
    <div className="min-h-screen">
      <header className="border-b border-neutral-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
          <Link href="/projects" className="text-sm font-medium tracking-wide">
            Preflight
          </Link>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-neutral-500">{user.email}</span>
            <button
              onClick={() => signOut()}
              className="text-neutral-400 underline underline-offset-2 hover:text-neutral-200"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}

function Centered({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="text-2xl font-semibold text-neutral-100">{title}</h1>
      <div className="mt-4 space-y-4">{children}</div>
    </main>
  );
}

function SignInForm() {
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await (mode === "in" ? signIn(email, password) : signUp(email, password));
    } catch (err) {
      setError(readableAuthError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Centered title={mode === "in" ? "Sign in to Preflight" : "Create an account"}>
      <p className="text-sm text-neutral-400">
        Your account starts empty. Preflight holds unreleased work, so there is no
        shared demo project to browse.
      </p>

      <form onSubmit={submit} className="space-y-3">
        <label className="block">
          <span className="text-sm text-neutral-400">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border border-neutral-800 bg-neutral-900 px-3 py-2
                       text-neutral-100 focus:border-neutral-600 focus:outline-none"
          />
        </label>

        <label className="block">
          <span className="text-sm text-neutral-400">Password</span>
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border border-neutral-800 bg-neutral-900 px-3 py-2
                       text-neutral-100 focus:border-neutral-600 focus:outline-none"
          />
        </label>

        {error && (
          <p role="alert" className="text-sm text-rose-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-neutral-100 px-4 py-2 font-medium text-neutral-950
                     transition hover:bg-white disabled:opacity-50"
        >
          {busy ? "Working…" : mode === "in" ? "Sign in" : "Create account"}
        </button>
      </form>

      <button
        onClick={() => {
          setMode(mode === "in" ? "up" : "in");
          setError("");
        }}
        className="text-sm text-neutral-400 underline underline-offset-2 hover:text-neutral-200"
      >
        {mode === "in"
          ? "No account? Create one"
          : "Already have an account? Sign in"}
      </button>
    </Centered>
  );
}
