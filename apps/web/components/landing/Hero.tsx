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
import { ease, range, useScrollProgress } from "./useScrollProgress";

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

  // Five movements overlap so the scene behaves like one slow camera move,
  // not a row of triggered interface animations.
  const arrive = ease(range(progress, 0.0, 0.11));
  const open = ease(range(progress, 0.10, 0.43));
  const inspect = ease(range(progress, 0.40, 0.67));
  const resolve = ease(range(progress, 0.68, 0.89));
  const closing = ease(range(progress, 0.86, 1.0));
  const apart = open * (1 - resolve);

  const stage =
    progress < 0.1
      ? "Finished"
      : progress < 0.42
        ? "Opened"
        : progress < 0.69
          ? "Inspected"
          : "Prepared";

  return (
    <section
      ref={ref}
      className="relative h-[500vh] motion-only"
      aria-labelledby="hero-heading"
    >
      <div className="sticky top-0 flex h-[100svh] items-center justify-center overflow-hidden">
        <header className="absolute inset-x-0 top-0 z-50 flex items-center justify-between px-5 py-5 sm:px-8 sm:py-7">
          <Link
            href="/"
            className="text-[11px] font-medium uppercase tracking-[0.28em] text-paper-100"
          >
            Pre<span className="text-accent">—</span>flight
          </Link>
          <div className="flex items-center gap-4">
            <span className="hidden font-mono text-[9px] uppercase tracking-[0.16em] text-paper-400 sm:block">
              Delivery readiness / 01
            </span>
            <Link
              href="/signin"
              className="text-xs text-paper-300 transition hover:text-paper-000"
            >
              Sign in
            </Link>
          </div>
        </header>

        <div
          className="hero-projector pointer-events-none absolute inset-0"
          style={{ opacity: 0.38 + arrive * 0.62 - closing * 0.35 }}
          aria-hidden="true"
        />

        <div
          className="pointer-events-none absolute inset-x-0 top-[15vh] overflow-hidden text-center"
          aria-hidden="true"
        >
          <p
            className="font-display text-[clamp(5rem,17vw,15rem)] leading-none tracking-[-0.055em] text-white/[0.09]"
            style={{
              opacity: 0.62 + arrive * 0.38 - closing,
              transform: `translateY(${(1 - arrive) * 28}px) scale(${0.96 + arrive * 0.04})`,
            }}
          >
            {stage}
          </p>
        </div>

        <div
          className="relative mt-[-2vh] w-[min(92vw,1180px)] sm:mt-0"
          style={{ perspective: "2100px", perspectiveOrigin: "50% 38%" }}
        >
          <div
            className="relative aspect-[2.39/1] w-full"
            style={{
              transformStyle: "preserve-3d",
              transform: `translate3d(0, ${(1 - arrive) * 36 - closing * 110}px, 0) scale(${0.9 + arrive * 0.1 - apart * 0.08 - closing * 0.16}) rotateX(${apart * 2.5}deg)`,
              opacity: 0.68 + arrive * 0.32 - closing * 0.58,
            }}
          >
            {LAYERS.map((layer) => {
              const rank = layer.depth;
              const z = -rank * 150 * apart;
              const y = rank * 43 * apart;
              const x = layer.x * 760 * apart;
              const rotateX = apart * (-5 - rank * 3.1);
              const rotateZ = apart * (rank % 2 === 0 ? -0.45 : 0.45);
              const isSpec = layer.key === "spec";
              const opacity = isSpec
                ? Math.min(1, apart * 1.7) * (1 - resolve)
                : rank === 0
                  ? 1
                  : (0.08 + apart * 0.92) * (1 - resolve * 0.92);

              return (
                <div
                  key={layer.key}
                  className="absolute inset-0"
                  style={{
                    transform: `translate3d(${x}px, ${y}px, ${z}px) rotateX(${rotateX}deg) rotateZ(${rotateZ}deg)`,
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

            <div
              className="hero-scan pointer-events-none absolute -inset-y-8 left-[-12%] z-40 w-[18%]"
              style={{
                opacity: inspect * (1 - resolve),
                transform: `translateX(${inspect * 690}%)`,
              }}
              aria-hidden="true"
            />

            <Findings amount={inspect * (1 - resolve)} />

            <div
              className="absolute inset-0"
              style={{
                opacity: resolve * (1 - closing * 0.72),
                transform: `scale(${0.94 + resolve * 0.06})`,
                zIndex: 20,
                pointerEvents: "none",
              }}
              aria-hidden="true"
            >
              <PackageLayer />
            </div>
          </div>
        </div>

        <div
          className="pointer-events-none absolute bottom-[9vh] left-6 sm:bottom-10 sm:left-8"
          style={{ opacity: (1 - range(progress, 0.02, 0.16)) * (0.72 + arrive * 0.28) }}
        >
          <p className="slate text-paper-300">One finished master</p>
          <p className="mt-1 max-w-[18rem] text-sm leading-relaxed text-paper-400">
            Opened, measured and prepared for every place it has to go.
          </p>
        </div>

        <StageRail progress={progress} stage={stage} />

        <div
          className="absolute inset-0 z-40 flex flex-col items-center justify-center px-6 text-center"
          style={{
            opacity: closing,
            pointerEvents: closing > 0.6 ? "auto" : "none",
            transform: `translateY(${(1 - closing) * 34}px)`,
          }}
        >
          <p className="slate mb-6 text-accent">Verified package / ready</p>
          <h1
            id="hero-heading"
            className="max-w-5xl font-display text-[clamp(3.1rem,7.5vw,7rem)] leading-[0.92] tracking-[-0.04em] text-paper-000"
          >
            Your film is finished.
            <br />
            <span className="text-paper-200">Make sure it’s ready to leave.</span>
          </h1>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/projects"
              className="rounded-[3px] bg-paper-000 px-6 py-3 text-sm font-medium text-ink-000 transition hover:bg-white"
            >
              Prepare your film
            </Link>
            <Link
              href="/signin"
              className="rounded-[3px] px-5 py-3 text-sm text-paper-200 ring-1 ring-inset ring-line-strong transition hover:text-paper-000"
            >
              Sign in
            </Link>
          </div>
        </div>

        <ScrollHint visible={progress < 0.04} />
      </div>
    </section>
  );
}

function StageRail({ progress, stage }: { progress: number; stage: string }) {
  return (
    <div
      className="pointer-events-none absolute bottom-8 right-6 top-24 hidden w-20 flex-col items-end justify-between sm:flex sm:right-8"
      aria-hidden="true"
    >
      <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-paper-400">
        {stage}
      </p>
      <div className="relative h-36 w-px overflow-hidden bg-white/10">
        <div
          className="absolute inset-x-0 top-0 bg-accent"
          style={{ height: `${Math.max(2, progress * 100)}%` }}
        />
      </div>
      <p className="font-mono text-[9px] text-paper-400 tnum">
        {String(Math.round(progress * 100)).padStart(2, "0")} / 100
      </p>
    </div>
  );
}

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
    <section
      className="reduced-only relative min-h-[100svh] overflow-hidden px-6 py-24"
      aria-labelledby="hero-heading-static"
    >
      <div className="hero-projector pointer-events-none absolute inset-0 opacity-70" />
      <div className="relative mx-auto grid min-h-[calc(100svh-12rem)] max-w-6xl items-center gap-16 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <p className="slate mb-5 text-accent">Finished / inspected / prepared</p>
          <h1
            id="hero-heading-static"
            className="font-display text-display-sm text-paper-000 sm:text-display-md lg:text-display-lg"
          >
            Your film is finished.
            <br />
            <span className="text-paper-200">Make sure it’s ready to leave.</span>
          </h1>
          <p className="mt-6 max-w-measure text-base leading-relaxed text-paper-200">
            Picture, sound, subtitles, metadata and the destination specification —
            opened as one composition, measured, then resolved into a verified package.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
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

        <div className="relative h-[min(68vw,500px)]" aria-label="Exploded technical view of a finished film">
          <div className="absolute inset-x-0 top-[12%] aspect-[2.39/1] [perspective:1600px]">
            {LAYERS.map((layer, index) => (
              <div
                key={layer.key}
                className="absolute inset-0"
                style={{
                  transform: `translate3d(${layer.x * 180}px, ${index * 34}px, ${-index * 70}px) rotateX(${-index * 2.4}deg)`,
                  zIndex: 10 - index,
                }}
              >
                <LayerFrame label={layer.label} value={layer.value} tone={layer.tone}>
                  {layer.render()}
                </LayerFrame>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
