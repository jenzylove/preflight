/**
 * The five things Preflight inspects, drawn as the planes of an exploded view.
 *
 * Each one is a thin sheet the same shape as the frame, so when they separate
 * they read as layers of a single object rather than as five panels. That is
 * the whole metaphor: a finished film is one thing made of parts, and delivery
 * is the moment those parts get checked separately.
 *
 * They are drawn, not screenshotted, so nothing here claims to be a
 * measurement of anyone's real film.
 */

export function LayerFrame({
  children,
  label,
  value,
  tone = "neutral",
}: {
  children: React.ReactNode;
  label: string;
  value?: string;
  tone?: "neutral" | "ok" | "warn";
}) {
  const edge =
    tone === "ok"
      ? "ring-ok/30"
      : tone === "warn"
        ? "ring-review/35"
        : "ring-white/[0.08]";

  return (
    <div className="relative h-full w-full">
      <div
        className={`relative h-full w-full overflow-hidden rounded-[2px] bg-ink-050
                    ring-1 ring-inset ${edge}`}
      >
        {children}
      </div>
      <div className="pointer-events-none absolute -top-5 left-0 flex items-baseline gap-2">
        <span className="slate text-paper-300">{label}</span>
        {value && (
          <span className="slate font-mono text-accent/80 tnum">{value}</span>
        )}
      </div>
    </div>
  );
}

/** The picture: the film still itself. */
export function PictureLayer() {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/film/still.jpg"
      alt="A field at dusk, the last of the light behind a treeline."
      className="still h-full w-full object-cover"
      loading="eager"
      decoding="async"
    />
  );
}

/** Audio, as a waveform with a loudness line across it. */
export function AudioLayer() {
  // A fixed pseudo-random shape: stable between renders, and obviously drawn
  // rather than sampled from anything.
  const bars = Array.from({ length: 132 }, (_, i) => {
    const swell = Math.sin(i / 9) * 0.34 + Math.sin(i / 3.1) * 0.16;
    const body = Math.abs(Math.sin(i * 1.7) * 0.3);
    return Math.min(0.98, Math.max(0.06, 0.42 + swell + body * 0.4));
  });

  return (
    <div className="relative h-full w-full bg-ink-050">
      <svg
        viewBox="0 0 132 40"
        preserveAspectRatio="none"
        className="h-full w-full"
        aria-hidden="true"
      >
        {bars.map((height, i) => (
          <rect
            key={i}
            x={i + 0.22}
            y={20 - (height * 40) / 2}
            width={0.56}
            height={height * 40}
            fill="rgba(217,164,65,0.55)"
          />
        ))}
        <line
          x1="0"
          y1="13.5"
          x2="132"
          y2="13.5"
          stroke="rgba(111,170,127,0.5)"
          strokeWidth="0.3"
          strokeDasharray="2 1.4"
        />
      </svg>
    </div>
  );
}

/** Subtitles, as timed cues. */
export function SubtitleLayer() {
  const cues = [
    ["00:00:00,000", "A field, before anyone arrives."],
    ["00:00:06,000", "The sound builds, then falls away."],
    ["00:00:13,000", "Nothing here is louder than it should be."],
  ];
  return (
    <div className="flex h-full w-full flex-col justify-center gap-2 bg-ink-050 px-5 py-3">
      {cues.map(([time, text], i) => (
        <div key={i} className="flex items-baseline gap-3">
          <span className="font-mono text-[9px] text-paper-400 tnum sm:text-[10px]">
            {time}
          </span>
          <span className="truncate text-[11px] text-paper-200 sm:text-xs">
            {text}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Metadata, as the fields a destination actually asks for. */
export function MetadataLayer() {
  const rows = [
    ["title", "A Quiet Field"],
    ["runtime", "00:24"],
    ["language", "en"],
    ["origin", "GB"],
  ];
  return (
    <div className="grid h-full w-full grid-cols-2 content-center gap-x-6 gap-y-1.5 bg-ink-050 px-5">
      {rows.map(([key, value]) => (
        <div key={key} className="flex items-baseline justify-between gap-3">
          <span className="slate text-paper-400">{key}</span>
          <span className="truncate font-mono text-[11px] text-paper-200">
            {value}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * The destination's published specification.
 *
 * This is the layer that does not come from the film. It arrives from
 * somewhere else and is the reason any of the others need checking, so it is
 * drawn differently — ruled, colder, more like a document than a track.
 */
export function SpecLayer() {
  const rules = [
    ["container", "mp4 · mov"],
    ["resolution", "1920 × 1080"],
    ["loudness", "−18 … −21 LUFS"],
    ["subtitles", "srt"],
  ];
  return (
    <div className="h-full w-full bg-[#0a0c10] px-5 py-3">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="slate text-think">artdocfest.com</span>
        <span className="slate text-paper-400">retrieved today</span>
      </div>
      <div className="space-y-1">
        {rules.map(([field, value]) => (
          <div
            key={field}
            className="flex items-baseline justify-between gap-3 border-t border-white/[0.06] pt-1"
          >
            <span className="text-[10px] text-paper-300 sm:text-[11px]">{field}</span>
            <span className="font-mono text-[10px] text-paper-100 tnum sm:text-[11px]">
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * The resolved package: the layers back together, with its evidence.
 *
 * The point of ending here is that delivery is not the film plus paperwork —
 * it is the film, checked, with the checking attached.
 */
export function PackageLayer() {
  return (
    <div className="relative h-full w-full overflow-hidden rounded-[2px]">
      <PictureLayer />
      <div className="absolute inset-0 still-scrim" />
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-4 p-4 sm:p-6">
        <div>
          <p className="font-display text-xl leading-none text-paper-000 sm:text-2xl">
            A Quiet Field
          </p>
          <p className="slate mt-1.5 text-paper-300">
            artdocfest · package verified
          </p>
        </div>
        <div className="hidden text-right sm:block">
          <p className="slate text-paper-400">sha256</p>
          <p className="font-mono text-[10px] text-paper-200 tnum">
            9f2c…a41d
          </p>
        </div>
      </div>
    </div>
  );
}
