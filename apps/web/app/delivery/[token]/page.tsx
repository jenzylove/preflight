"use client";

import { use, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

/**
 * The recipient's view.
 *
 * The only unauthenticated page in the product. It carries no project id, no
 * owner, no storage path — only what the API's public response model allows.
 *
 * Every failure looks the same. Expired, revoked, mistyped and never-existed
 * are one message, because distinguishing them tells an attacker which tokens
 * are real.
 */

interface PublicRoom {
  project_title: string;
  destination: string;
  verified: boolean;
  package_sha256: string | null;
  file_count: number;
  expires_at: string;
  limitations: string[];
}

export default function DeliveryPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const [room, setRoom] = useState<PublicRoom | null>(null);
  const [gone, setGone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/v1/delivery/${token}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setRoom)
      .catch(() => setGone(true));
  }, [token]);

  async function download() {
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/v1/delivery/${token}/download-intent`, {
        method: "POST",
      });
      if (!res.ok) throw new Error();
      const body = await res.json();
      setNote(body.note ?? "");
      window.location.href = body.url;
    } catch {
      setGone(true);
    } finally {
      setBusy(false);
    }
  }

  if (gone) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
        <h1 className="text-xl font-semibold text-neutral-100">
          This link is not available
        </h1>
        <p className="mt-3 text-sm text-neutral-400">
          It may have expired or been withdrawn. Ask whoever sent it for a new one.
        </p>
      </main>
    );
  }

  if (!room) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
        <p className="text-neutral-500">Opening…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <p className="text-xs uppercase tracking-widest text-neutral-500">
        Delivery from Preflight
      </p>
      <h1 className="mt-3 text-2xl font-semibold text-neutral-100">
        {room.project_title}
      </h1>
      <p className="mt-1 text-sm text-neutral-400">
        Prepared for {room.destination} · {room.file_count} files
      </p>

      <div className="mt-6 rounded-lg border border-neutral-800 p-4">
        <p className="text-sm text-emerald-300">
          Checked against {room.destination}&apos;s published requirements.
        </p>
        {room.package_sha256 && (
          <p className="mt-2 break-all font-mono text-xs text-neutral-500">
            sha256 {room.package_sha256}
          </p>
        )}
        <p className="mt-2 text-xs text-neutral-500">
          Link expires {new Date(room.expires_at).toLocaleString()}
        </p>
      </div>

      <button
        onClick={download}
        disabled={busy}
        className="mt-6 rounded bg-neutral-100 px-5 py-2 font-medium text-neutral-950
                   transition hover:bg-white disabled:opacity-50"
      >
        {busy ? "Preparing…" : "Download package"}
      </button>

      {note && <p className="mt-3 text-xs text-neutral-400">{note}</p>}

      {room.limitations.length > 0 && (
        <section className="mt-8 border-t border-neutral-900 pt-5">
          <h2 className="text-sm font-medium text-neutral-300">Worth knowing</h2>
          <ul className="mt-2 space-y-1 text-sm text-neutral-400">
            {room.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </section>
      )}

      <p className="mt-10 text-xs text-neutral-600">
        Preflight verifies against requirements published by the destination. It is
        not a guarantee that the destination will accept this delivery.
      </p>
    </main>
  );
}
