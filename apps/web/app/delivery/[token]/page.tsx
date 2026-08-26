"use client";

import { use, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";
import type { PublicRoom } from "@/lib/types";

/**
 * The recipient's view.
 *
 * This is the only unauthenticated surface in the product, and it points at
 * someone's unreleased film, so it shows exactly what the server sends and
 * asks for nothing. No sign-in, no account, no tracking of who opened it.
 *
 * It deliberately does not use the workspace client: that attaches an ID token
 * to every call, and a recipient has no account. These two requests are the
 * whole surface, and they carry no credential at all.
 *
 * Every failure looks identical. Expired, revoked, mistyped and never-existed
 * all render the same page, because distinguishing them tells someone probing
 * for links which ones are real.
 */
export default function DeliveryPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  return <Delivery token={token} />;
}

function Delivery({ token }: { token: string }) {
  const [room, setRoom] = useState<PublicRoom | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "gone">("loading");
  const [downloading, setDownloading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/v1/delivery/${token}`, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("unavailable");
        return response.json();
      })
      .then((body: PublicRoom) => {
        setRoom(body);
        setState("ready");
      })
      .catch(() => setState("gone"));
  }, [token]);

  async function download() {
    setDownloading(true);
    setProblem(null);
    try {
      const response = await fetch(`${API_BASE}/v1/delivery/${token}/download-intent`, {
        method: "POST",
        cache: "no-store",
      });
      if (!response.ok) throw new Error("unavailable");
      const body = (await response.json()) as { url: string };
      window.location.href = body.url;
    } catch {
      setProblem(
        "This download is temporarily unavailable. The link itself is still valid.",
      );
    } finally {
      setDownloading(false);
    }
  }

  if (state === "loading") {
    return (
      <Centre>
        <p className="slate text-paper-400" role="status">
          Opening
        </p>
      </Centre>
    );
  }

  if (state === "gone" || !room) {
    return (
      <Centre>
        <h1 className="font-display text-3xl text-paper-000">
          This link is not available
        </h1>
        <p className="mt-4 max-w-measure text-paper-300">
          It may have expired, or been withdrawn by whoever sent it. Ask them
          for a new one.
        </p>
      </Centre>
    );
  }

  return (
    <main id="main" className="mx-auto max-w-2xl px-6 py-20">
      <p className="slate text-paper-400">Delivered with Preflight</p>

      <h1 className="mt-5 font-display text-display-sm leading-tight text-paper-000">
        {room.project_title}
      </h1>
      <p className="mt-3 text-[15px] text-paper-300">
        Prepared for {room.destination}
      </p>

      <div className="mt-10 rounded-[3px] border border-line bg-ink-100 p-6">
        <dl className="space-y-2.5 text-sm">
          <Row
            label="Files"
            value={`${room.file_count} file${room.file_count === 1 ? "" : "s"}`}
          />
          <Row label="Available until" value={formatDate(room.expires_at)} />
          {room.package_sha256 && (
            <Row label="Package hash" value={room.package_sha256} mono />
          )}
        </dl>

        <button
          type="button"
          onClick={download}
          disabled={downloading}
          className="mt-6 w-full rounded-[3px] bg-paper-000 px-5 py-3 text-sm font-medium
                     text-ink-000 transition hover:bg-white disabled:opacity-50"
        >
          {downloading ? "Preparing…" : "Download the package"}
        </button>

        {room.package_sha256 && (
          <p className="mt-3 text-xs text-paper-400">
            Check this hash against the file you receive to confirm it arrived
            intact.
          </p>
        )}

        {problem && (
          <p role="alert" className="mt-3 text-sm text-stop">
            {problem}
          </p>
        )}
      </div>

      {room.limitations.length > 0 && (
        <section className="mt-8">
          <h2 className="slate mb-3 text-paper-400">Stated limitations</h2>
          <ul className="space-y-2">
            {room.limitations.map((limitation, index) => (
              <li
                key={index}
                className="border-l-2 border-line-strong pl-4 text-sm leading-relaxed
                           text-paper-300"
              >
                {limitation}
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="mt-10 border-t border-line pt-6 text-sm leading-relaxed text-paper-400">
        Preflight checked this package against the requirements
        {room.destination ? ` ${room.destination}` : " the destination"} published,
        at the dates recorded above. That is not a guarantee of acceptance.
      </p>
    </main>
  );
}

function Centre({ children }: { children: React.ReactNode }) {
  return (
    <main id="main" className="flex min-h-screen items-center justify-center px-6">
      <div className="max-w-measure text-center">{children}</div>
    </main>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 border-b border-line/60 pb-2">
      <dt className="text-paper-400">{label}</dt>
      <dd className={`break-all text-right text-paper-100 ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}
