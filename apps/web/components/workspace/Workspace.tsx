"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { User } from "firebase/auth";

import { authConfigured, signOut, watchUser } from "@/lib/auth";

/**
 * The authenticated frame.
 *
 * Preflight holds unreleased films, so there is no anonymous browsing of
 * project state and no demo account with pre-seeded data. Signing in creates a
 * real, empty account, and the first thing in it is whatever the user uploads.
 *
 * The chrome is deliberately thin. Three destinations in the nav, no sidebar,
 * no counters. The project is the mental model; anything that competes with it
 * is noise on the screen where someone is deciding whether their film can
 * ship.
 */

const NAV = [
  { href: "/projects", label: "Projects" },
  { href: "/deliveries", label: "Deliveries" },
  { href: "/settings", label: "Settings" },
];

export function Workspace({
  children,
  wide = false,
}: {
  children: React.ReactNode;
  wide?: boolean;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(
    () =>
      watchUser((u) => {
        setUser(u);
        setReady(true);
      }),
    [],
  );

  // A signed-out visitor is sent to sign in, carrying where they were headed
  // so they land there rather than at a generic home.
  useEffect(() => {
    if (ready && !user && authConfigured) {
      const next = encodeURIComponent(pathname ?? "/projects");
      router.replace(`/signin?next=${next}`);
    }
  }, [ready, user, pathname, router]);

  if (!authConfigured) {
    return <NotConfigured />;
  }

  if (!ready) {
    return <Restoring />;
  }

  if (!user) {
    // The redirect is already in flight; showing a form here would flash a
    // second sign-in surface for a fraction of a second.
    return <Restoring />;
  }

  return (
    <div className="min-h-screen">
      <TopBar user={user} />
      <main
        id="main"
        className={`mx-auto px-6 pb-32 pt-10 ${wide ? "max-w-6xl" : "max-w-5xl"}`}
      >
        {children}
      </main>
    </div>
  );
}

function TopBar({ user }: { user: User }) {
  const pathname = usePathname() ?? "";
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-ink-000/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3.5">
        <Link
          href="/projects"
          className="font-display text-lg leading-none text-paper-000"
        >
          Preflight
        </Link>

        <nav aria-label="Workspace" className="hidden gap-1 sm:flex">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-[3px] px-3 py-1.5 text-sm transition ${
                  active
                    ? "text-paper-000"
                    : "text-paper-300 hover:text-paper-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <Link
            href="/projects/new"
            className="hidden rounded-[3px] bg-paper-000 px-3.5 py-1.5 text-sm font-medium
                       text-ink-000 transition hover:bg-white sm:block"
          >
            New delivery
          </Link>

          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-ink-200
                         text-xs font-medium text-paper-200 ring-1 ring-inset ring-line
                         transition hover:text-paper-000"
            >
              <span className="sr-only">Account</span>
              <span aria-hidden="true">{initial(user)}</span>
            </button>

            {menuOpen && (
              <>
                <button
                  type="button"
                  className="fixed inset-0 z-10 cursor-default"
                  aria-hidden="true"
                  tabIndex={-1}
                  onClick={() => setMenuOpen(false)}
                />
                <div
                  role="menu"
                  className="absolute right-0 z-20 mt-2 w-60 overflow-hidden rounded-[3px]
                             border border-line bg-ink-100 shadow-2xl"
                >
                  <div className="border-b border-line px-4 py-3">
                    <p className="truncate text-sm text-paper-100">{user.email}</p>
                    <p className="mt-0.5 text-xs text-paper-400">Signed in</p>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => signOut()}
                    className="block w-full px-4 py-2.5 text-left text-sm text-paper-200
                               hover:bg-ink-150 hover:text-paper-000"
                  >
                    Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* The nav collapses to a row beneath the bar on small screens rather
          than hiding behind a menu button: three links do not need a drawer. */}
      <nav
        aria-label="Workspace"
        className="flex gap-1 border-t border-line px-4 py-1.5 sm:hidden"
      >
        {NAV.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`rounded-[3px] px-3 py-1.5 text-sm ${
                active ? "text-paper-000" : "text-paper-300"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

function initial(user: User) {
  const source = user.displayName || user.email || "?";
  return source.trim().charAt(0).toUpperCase();
}

/** The gap between page load and Firebase restoring the session. */
function Restoring() {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <p className="slate text-paper-400" role="status">
        Restoring your session
      </p>
    </div>
  );
}

function NotConfigured() {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="max-w-measure text-center">
        <h1 className="font-display text-3xl text-paper-000">
          Accounts are unavailable here
        </h1>
        <p className="mt-4 text-paper-300">
          This deployment has no identity provider configured, so there is no
          way to sign in. The API is running and its endpoints are documented at{" "}
          <a
            className="text-accent underline underline-offset-4"
            href={`${process.env.NEXT_PUBLIC_API_BASE_URL}/docs`}
          >
            /docs
          </a>
          .
        </p>
      </div>
    </div>
  );
}

/** Page heading used across the workspace, so hierarchy stays consistent. */
export function PageHead({
  eyebrow,
  title,
  lede,
  actions,
}: {
  eyebrow?: string;
  title: string;
  lede?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-10">
      {eyebrow && <p className="slate text-paper-400">{eyebrow}</p>}
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <h1 className="font-display text-display-sm leading-none text-paper-000">
          {title}
        </h1>
        {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
      </div>
      {lede && (
        <p className="mt-4 max-w-measure text-[15px] leading-relaxed text-paper-300">
          {lede}
        </p>
      )}
    </header>
  );
}
