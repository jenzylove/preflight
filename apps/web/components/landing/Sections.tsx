import Link from "next/link";

/**
 * After the hero, the page calms down.
 *
 * The hero makes the argument emotionally; these sections make it concretely,
 * in the order the product actually works. Nothing here animates on scroll —
 * spectacle all the way down is exhausting, and the reader is now here to
 * find out whether this is real.
 *
 * Everything shown is illustrative and says so where it could be mistaken for
 * a measurement. The authenticated product never shows invented values.
 */

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className="slate text-paper-400">{children}</p>;
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-4 max-w-[22ch] font-display text-display-sm leading-[1.05] text-paper-000">
      {children}
    </h2>
  );
}

function Lede({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-5 max-w-measure text-[17px] leading-relaxed text-paper-200">
      {children}
    </p>
  );
}

function Section({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`border-t border-line px-6 py-24 sm:py-32 ${className}`}>
      <div className="mx-auto max-w-5xl">{children}</div>
    </section>
  );
}

/** One master, several destinations, each wanting something different. */
export function OneMasterManyDestinations() {
  const destinations = [
    { name: "Berlinale", asks: ["ProRes or DCP", "Burned-in subtitles", "1920 × 1080"] },
    { name: "Artdocfest", asks: ["MP4 or MOV", "SubRip sidecar", "−18…−21 LUFS"] },
  ];

  return (
    <Section>
      <Eyebrow>01 — The problem</Eyebrow>
      <SectionHeading>
        One finished master. Every destination has different rules.
      </SectionHeading>
      <Lede>
        Two real festivals, two published specifications. One mandates subtitles
        burned into the picture. The other forbids exactly that and asks for a
        SubRip file alongside. No single deliverable satisfies both, and nothing
        about your master tells you so.
      </Lede>

      <div className="mt-14 grid gap-px overflow-hidden rounded-[2px] bg-line sm:grid-cols-2">
        {destinations.map((destination) => (
          <div key={destination.name} className="bg-ink-050 p-6 sm:p-8">
            <p className="font-display text-2xl text-paper-000">{destination.name}</p>
            <ul className="mt-5 space-y-2.5">
              {destination.asks.map((ask) => (
                <li
                  key={ask}
                  className="flex items-baseline gap-3 border-t border-line pt-2.5 text-sm text-paper-200"
                >
                  <span aria-hidden="true" className="text-paper-400">
                    ·
                  </span>
                  {ask}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-start gap-3 rounded-[2px] border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 pr-5">
        <span aria-hidden="true" className="mt-px text-stop">
          ✕
        </span>
        <p className="text-sm text-paper-100">
          These destinations require different subtitle deliveries.
          <span className="text-paper-300">
            {" "}
            Preflight builds a separate package for each, and quotes the sentence
            from each specification that says why.
          </span>
        </p>
      </div>
    </Section>
  );
}

/** Requirements change; Preflight reads the current ones and cites them. */
export function CurrentRequirements() {
  return (
    <Section>
      <Eyebrow>02 — Retrieval</Eyebrow>
      <SectionHeading>
        Requirements change. Preflight checks the current ones.
      </SectionHeading>
      <Lede>
        Specifications are retrieved from the destination’s own documentation
        each time, hashed, and dated. A rule that cannot be traced to an
        official page does not become a requirement your film is measured
        against — it stays visible as context, and nothing else.
      </Lede>

      <div className="mt-14 space-y-px overflow-hidden rounded-[2px] bg-line">
        {[
          {
            host: "artdocfest.com",
            tier: "Official",
            tone: "ok" as const,
            note: "Technical requirements · retrieved today",
          },
          {
            host: "berlinale.de",
            tier: "Official",
            tone: "ok" as const,
            note: "Technical specifications · retrieved today",
          },
          {
            host: "a film blog",
            tier: "Unverified",
            tone: "idle" as const,
            note: "Kept as context. Cannot create a requirement.",
          },
        ].map((source) => (
          <div
            key={source.host}
            className="flex flex-wrap items-center justify-between gap-3 bg-ink-050 px-5 py-4"
          >
            <div className="min-w-0">
              <p
                className={`font-mono text-sm ${
                  source.tone === "ok" ? "text-paper-100" : "text-paper-400 line-through"
                }`}
              >
                {source.host}
              </p>
              <p className="mt-0.5 text-xs text-paper-300">{source.note}</p>
            </div>
            <span
              className={`slate rounded-[3px] px-2 py-1 ring-1 ring-inset ${
                source.tone === "ok"
                  ? "bg-ok-bg text-ok ring-ok/25"
                  : "bg-idle-bg text-paper-300 ring-white/10"
              }`}
            >
              {source.tier}
            </span>
          </div>
        ))}
      </div>

      <p className="mt-6 text-sm text-paper-300">
        Illustrative. In the product, every requirement links to the page it came
        from and the date it was read.
      </p>
    </Section>
  );
}

/** Measurement, not inference. */
export function MeasureNeverGuess() {
  const groups = [
    {
      title: "Picture",
      rows: [
        ["container", "mov"],
        ["codec", "h264"],
        ["resolution", "1920 × 1080"],
        ["frame rate", "25"],
      ],
    },
    {
      title: "Sound",
      rows: [
        ["codec", "ac3"],
        ["sample rate", "48 000 Hz"],
        ["loudness", "−26.61 LUFS"],
        ["true peak", "−21.94 dBTP"],
      ],
    },
    {
      title: "Subtitles",
      rows: [
        ["format", "vtt"],
        ["cues", "3"],
        ["burned in", "no"],
        ["language", "en"],
      ],
    },
  ];

  return (
    <Section>
      <Eyebrow>03 — Measurement</Eyebrow>
      <SectionHeading>Measure. Never guess.</SectionHeading>
      <Lede>
        A language model may read a requirement. Only a tool may state a fact
        about your file. Every number Preflight reports comes from ffprobe,
        ffmpeg’s EBU R128 implementation or Pillow, with the version of the tool
        that produced it recorded alongside.
      </Lede>

      <div className="mt-14 grid gap-px overflow-hidden rounded-[2px] bg-line md:grid-cols-3">
        {groups.map((group) => (
          <div key={group.title} className="bg-ink-050 p-6">
            <p className="slate text-paper-400">{group.title}</p>
            <dl className="mt-4 space-y-2">
              {group.rows.map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-baseline justify-between gap-4 border-t border-line pt-2"
                >
                  <dt className="text-xs text-paper-300">{key}</dt>
                  <dd className="font-mono text-xs text-paper-100 tnum">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>

      <p className="mt-6 text-sm text-paper-300">
        Measured from the demonstration master on this page. Your own figures
        come from your own file, and from nothing else.
      </p>
    </Section>
  );
}

/** The safety model. */
export function SafeRepairsStaySafe() {
  const levels = [
    {
      name: "Safe to run",
      tone: "ok" as const,
      glyph: "✓",
      body:
        "Deterministic and non-creative. Loudness moved by a single gain offset; "
        + "subtitles converted without retiming; the container rewritten without "
        + "touching the picture. Runs only after you approve the exact plan.",
    },
    {
      name: "Your decision",
      tone: "review" as const,
      glyph: "?",
      body:
        "Re-encoding the picture, cropping key art, translating subtitles. These "
        + "change the work. Preflight shows what would be required and why, and "
        + "will not do it on your behalf.",
    },
    {
      name: "Preflight will not do this",
      tone: "stop" as const,
      glyph: "✕",
      body:
        "Producing a mix that does not exist, resolving contradictory instructions, "
        + "or deciding something that needs authority Preflight does not have.",
    },
  ];

  return (
    <Section>
      <Eyebrow>04 — Repair</Eyebrow>
      <SectionHeading>Safe repairs stay safe.</SectionHeading>
      <Lede>
        The most valuable thing an automated tool can do with a finished film is
        refuse. Preflight repairs only what it can do deterministically, proves
        the picture came through untouched, and leaves everything else to you.
      </Lede>

      <div className="mt-14 space-y-px overflow-hidden rounded-[2px] bg-line">
        {levels.map((level) => (
          <div key={level.name} className="bg-ink-050 p-6 sm:flex sm:gap-8 sm:p-8">
            <div className="flex items-baseline gap-3 sm:w-64 sm:shrink-0">
              <span
                aria-hidden="true"
                className={
                  level.tone === "ok"
                    ? "text-ok"
                    : level.tone === "review"
                      ? "text-review"
                      : "text-stop"
                }
              >
                {level.glyph}
              </span>
              <p className="text-[15px] font-medium text-paper-000">{level.name}</p>
            </div>
            <p className="mt-3 max-w-measure text-sm leading-relaxed text-paper-200 sm:mt-0">
              {level.body}
            </p>
          </div>
        ))}
      </div>
    </Section>
  );
}

/** Evidence. */
export function EveryDeliveryKeepsItsEvidence() {
  return (
    <Section>
      <Eyebrow>05 — Evidence</Eyebrow>
      <SectionHeading>Every delivery keeps its evidence.</SectionHeading>
      <Lede>
        When the repairs finish, Preflight does not take the worker’s word for
        it. The package is re-measured from disk, against the same published
        requirements, and only then can it be called ready. What comes out is a
        passport: the original hashes, every transformation, the rules and the
        pages they came from, and whatever remains unresolved.
      </Lede>

      <div className="mt-14 overflow-hidden rounded-[2px] bg-ink-050 ring-1 ring-inset ring-line">
        <div className="border-b border-line px-6 py-4">
          <p className="slate text-paper-400">Release passport · extract</p>
        </div>
        <div className="space-y-3 px-6 py-6 font-mono text-xs leading-relaxed text-paper-200">
          <p>
            <span className="text-paper-400">original master </span>
            <span className="tnum">sha256 4b1e…c7a9 · unchanged</span>
          </p>
          <p>
            <span className="text-paper-400">transformation </span>
            normalise_loudness · −26.61 → −19.42 LUFS
          </p>
          <p>
            <span className="text-paper-400">transformation </span>
            convert_subtitles · vtt → srt
          </p>
          <p>
            <span className="text-paper-400">rule pack </span>
            artdocfest v1 · retrieved 2026-08-26
          </p>
          <p className="text-review">
            <span className="text-paper-400">limitation </span>
            One published requirement was set aside by the owner and not measured.
          </p>
          <p className="text-paper-300">
            Preflight verifies against the requirements published at the dates
            recorded above. It is not a guarantee that the destination will
            accept this delivery.
          </p>
        </div>
      </div>
    </Section>
  );
}

/** Close. */
export function FinalCall() {
  return (
    <section className="relative border-t border-line px-6 py-32 sm:py-44">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(90% 60% at 50% 100%, rgba(217,164,65,0.08), transparent 65%)",
        }}
        aria-hidden="true"
      />
      <div className="relative mx-auto max-w-3xl text-center">
        <h2 className="font-display text-display-sm text-paper-000 sm:text-display-md">
          Your film is finished.
          <br />
          <span className="text-paper-200">Make sure it’s ready to leave.</span>
        </h2>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/projects"
            className="rounded-[3px] bg-paper-000 px-7 py-3.5 text-sm font-medium text-ink-000
                       transition hover:bg-white"
          >
            Prepare your film
          </Link>
          <Link
            href="/signin"
            className="rounded-[3px] px-6 py-3.5 text-sm text-paper-200 ring-1 ring-inset
                       ring-line-strong transition hover:text-paper-000"
          >
            Sign in
          </Link>
        </div>
      </div>
    </section>
  );
}

export function LandingFooter() {
  return (
    <footer className="border-t border-line px-6 py-10">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4">
        <p className="slate text-paper-400">Preflight</p>
        <p className="max-w-measure text-xs leading-relaxed text-paper-400">
          Preflight checks a delivery against the requirements a destination has
          published. It does not speak for any festival, platform or
          distributor, and cannot promise that a delivery will be accepted.
        </p>
      </div>
    </footer>
  );
}
