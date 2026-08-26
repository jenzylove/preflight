"use client";

import Link from "next/link";
import {
  AudioLayer,
  LayerFrame,
  MetadataLayer,
  PackageLayer,
  PictureLayer,
  SpecLayer,
  SubtitleLayer,
} from "./Layers";
import { ease, range, useScrollProgress, usePrefersReducedMotion } from "./useScrollProgress";

/**
 * The hero.
 *
 * One finished frame comes apart into the things Preflight inspects, the
 * destination's requirements arrive and are checked against them, and the
 * pieces resolve back into a package that carries its own evidence.
 *
 * The sequence is the argument. A film is not a file — it is picture, sound,
 * subtitles and metadata that have to satisfy someone else's published rules,
 * and the only way to know whether they do is to take it apart and measure.
 *
 * Scroll drives one number. Every layer derives its depth, offset and opacity
 * from it, so the whole thing moves as one object rather than as five
 * independently animated elements.
 */

type LayerSpec = {
  key: string;
  label: string;
  value?: string;
  render: () => React.ReactNode;
  /** Where this plane sits once separated, as a fraction of the spread. */
  depth: number;
  x: number;
  tone?: "neutral" | "ok" | "warn";
};

const LAYERS: LayerSpec[] = [
  { key: "picture", label: "Picture", render: () => <PictureLayer />, depth: 0, x: 0 },
  {
    key: "audio",
    label: "Audio",
    value: "−19.4 LUFS",
    render: () => <AudioLayer />,
    depth: 1,
    x: -0.055,
    tone: "warn",
  },
  {
    key: "subtitles",
    label: "Subtitles",
    value: "SRT",
    render: () => <SubtitleLayer />,
    depth: 2,
    x: 0.048,
  },
  { key: "metadata", label: "Metadata", render: () => <MetadataLayer />, depth: 3, x: -0.038 },
  {
    key: "spec",
    label: "Destination spec",
    render: () => <SpecLayer />,
    depth: 4,
    x: 0.066,
    tone: "neutral",
  },
];

export function Hero() {
  const { ref, progress } = useScrollProgress<HTMLDivElement>();
  const reduced = usePrefersReducedMotion();

  // Four movements. Slow, and overlapping, so nothing snaps.
  const settle = ease(range(progress, 0.0, 0.12));      // the frame arrives
  const spread = ease(range(progress, 0.12, 0.46));     // it comes apart
  const inspect = ease(range(progress, 0.46, 0.70));    // requirements land on it
  const resolve = ease(range(progress, 0.72, 0.94));    // it becomes a package

  const closing = range(progress, 0.88, 1.0);

  return (
    <section
      ref={ref}
      className="relative h-[420vh] motion-only"
      aria-labelledby="hero-heading"
    >
      <div className="sticky top-0 flex h-screen items-center justify-center overflow-hidden">
        {/* A faint horizon behind everything, so the frame reads as floating in
            a space rather than pasted onto a black rectangle. */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 70% at 50% 62%, rgba(217,164,65,0.07), transparent 62%)",
            opacity: 0.6 + settle * 0.4 - resolve * 0.2,
          }}
          aria-hidden="true"
        />

        <div
          className="relative w-[min(92vw,1120px)]"
          style={{ perspective: "1800px" }}
        >
          <div
            className="relative aspect-[2.39/1] w-full"
            style={{
              transformStyle: "preserve-3d",
              transform: `translateY(${(1 - settle) * 26}px) scale(${
                0.94 + settle * 0.06 - resolve * 0.02
              })`,
              opacity: 0.25 + settle * 0.75,
            }}
          >
            {LAYERS.map((layer) => {
              // Each plane pulls away from the picture, then returns. The
              // picture itself barely moves: everything else separates from it.
              const rank = layer.depth;
              const apart = spread * (1 - resolve);

              const z = -rank * 128 * apart;
              const y = rank * 34 * apart;
              const x = layer.x * 620 * apart;
              const rotate = apart * (rank === 0 ? -3 : -9 - rank * 1.4);

              // The spec sheet is the last to arrive and the first to leave: it
              // is not part of the film, it is what the film is measured against.
              const isSpec = layer.key === "spec";
              const opacity = isSpec
                ? Math.min(1, apart * 1.4) * (1 - resolve)
                : rank === 0
                  ? 1
                  : (0.15 + apart * 0.85) * (1 - resolve * 0.9);

              return (
                <div
                  key={layer.key}
                  className="absolute inset-0"
                  style={{
                    transform: `translate3d(${x}px, ${y}px, ${z}px) rotateX(${rotate}deg)`,
                    opacity,
                    zIndex: 10 - rank,
                    willChange: "transform, opacity",
                  }}
                  aria-hidden={rank > 0 ? "true" : undefined}
                >
                  <LayerFrame
                    label={layer.label}
                    value={apart > 0.4 ? layer.value : undefined}
                    tone={inspect > 0.5 ? layer.tone : "neutral"}
                  >
                    {layer.render()}
                  </LayerFrame>
                </div>
              );
            })}

            {/* The findings. They appear only once the layers are apart and the
                spec has arrived, because that is the only moment they mean
                anything. */}
            <Findings amount={inspect * (1 - resolve)} />

            {/* The resolved package fades in over the stack as it closes. */}
            <div
              className="absolute inset-0"
              style={{ opacity: resolve, zIndex: 20, pointerEvents: "none" }}
              aria-hidden="true"
            >
              <PackageLayer />
            </div>
          </div>
        </div>

        {/* Opening statement, out before the layers separate. */}
        <div
          className="pointer-events-none absolute inset-x-0 bottom-[8vh] px-6 text-center"
          style={{ opacity: (1 - range(progress, 0.02, 0.14)) * settle }}
        >
          <p className="slate text-paper-400">A finished film is not a file</p>
        </div>

        {/* Closing statement and the way in. */}
        <div
          className="absolute inset-x-0 bottom-0 top-0 flex flex-col items-center justify-center px-6 text-center"
          style={{
            opacity: closing,
            pointerEvents: closing > 0.6 ? "auto" : "none",
            transform: `translateY(${(1 - closing) * 14}px)`,
          }}
        >
          <div className="rounded-sm bg-ink-000/70 px-6 py-8 backdrop-blur-[2px] sm:px-10">
            <h1
              id="hero-heading"
              className="font-display text-display-sm text-paper-000 sm:text-display-md"
            >
              Your film is finished.
              <br />
              <span className="text-paper-200">Make sure it’s ready to leave.</span>
            </h1>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/projects"
                className="rounded-[3px] bg-paper-000 px-6 py-3 text-sm font-medium text-ink-000
                           transition hover:bg-white"
              >
                Prepare your film
              </Link>
              <Link
                href="/signin"
                className="rounded-[3px] px-5 py-3 text-sm text-paper-200 ring-1 ring-inset
                           ring-line-strong transition hover:text-paper-000"
              >
                Sign in
              </Link>
            </div>
          </div>
        </div>

        <ScrollHint visible={progress < 0.04} />
      </div>
    </section>
  );
}

/**
 * What inspection actually produces: a small number of specific findings.
 *
 * Three, not thirty. The point being made is that Preflight tells you the
 * thing that will stop your delivery, not that it can generate a long report.
 */
function Findings({ amount }: { amount: number }) {
  const findings = [
    {
      at: { top: "18%", left: "-6%" },
      tone: "ok" as const,
      label: "Resolution",
      detail: "1920 × 1080 · meets requirement",
    },
    {
      at: { top: "48%", right: "-8%" },
      tone: "warn" as const,
      label: "Loudness",
      detail: "−26.6 LUFS · outside −18…−21",
    },
    {
      at: { bottom: "6%", left: "2%" },
      tone: "warn" as const,
      label: "Subtitles",
      detail: "WebVTT · SubRip required",
    },
  ];

  return (
    <>
      {findings.map((finding, i) => {
        const local = Math.min(1, Math.max(0, amount * 3 - i * 0.55));
        return (
          <div
            key={finding.label}
            className="absolute hidden lg:block"
            style={{
              ...finding.at,
              opacity: local,
              transform: `translateX(${(1 - local) * (finding.at.right ? 18 : -18)}px)`,
              zIndex: 30,
            }}
            aria-hidden="true"
          >
            <div
              className={`rounded-[2px] border-l-2 bg-ink-000/85 py-1.5 pl-3 pr-4 backdrop-blur-sm
                          ${finding.tone === "ok" ? "border-ok" : "border-review"}`}
            >
              <p className="slate text-paper-400">{finding.label}</p>
              <p className="mt-0.5 font-mono text-[11px] text-paper-100 tnum">
                {finding.detail}
              </p>
            </div>
          </div>
        );
      })}
    </>
  );
}

function ScrollHint({ visible }: { visible: boolean }) {
  return (
    <div
      className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2"
      style={{ opacity: visible ? 0.55 : 0, transition: "opacity 400ms" }}
      aria-hidden="true"
    >
      <div className="h-10 w-px bg-gradient-to-b from-transparent via-paper-400 to-transparent" />
    </div>
  );
}

/**
 * The same story without motion.
 *
 * Not a fallback in the apologetic sense — the exploded view is legible as a
 * single still diagram, which is how an exploded view is normally printed. A
 * viewer who has asked for less motion gets the whole argument at once instead
 * of over four screens of scrolling.
 */
export function HeroStatic() {
  return (
    <section className="reduced-only px-6 py-24" aria-labelledby="hero-heading-static">
      <div className="mx-auto max-w-5xl">
        <h1
          id="hero-heading-static"
          className="font-display text-display-sm text-paper-000 sm:text-display-md"
        >
          Your film is finished.
          <br />
          <span className="text-paper-200">Make sure it’s ready to leave.</span>
        </h1>
        <p className="mt-6 max-w-measure text-lg leading-relaxed text-paper-200">
          A finished film is picture, sound, subtitles and metadata that have to
          satisfy someone else’s published requirements. Preflight takes it
          apart, measures every piece, and checks each one against what the
          destination asks for today.
        </p>

        <div className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {LAYERS.map((layer) => (
            <figure key={layer.key} className="space-y-2">
              <div className="aspect-[2.39/1] w-full">
                <LayerFrame label={layer.label} value={layer.value}>
                  {layer.render()}
                </LayerFrame>
              </div>
            </figure>
          ))}
          <figure className="space-y-2">
            <div className="aspect-[2.39/1] w-full">
              <LayerFrame label="Verified package">
                <PackageLayer />
              </LayerFrame>
            </div>
          </figure>
        </div>

        <div className="mt-12 flex flex-wrap gap-3">
          <Link
            href="/projects"
            className="rounded-[3px] bg-paper-000 px-6 py-3 text-sm font-medium text-ink-000"
          >
            Prepare your film
          </Link>
          <Link
            href="/signin"
            className="rounded-[3px] px-5 py-3 text-sm text-paper-200 ring-1 ring-inset ring-line-strong"
          >
            Sign in
          </Link>
        </div>
      </div>
    </section>
  );
}
