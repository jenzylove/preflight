import Link from "next/link";

const eyebrow = "text-[10px] font-semibold uppercase tracking-[0.24em] text-[#786574]";
const heading = "font-display text-[clamp(3.2rem,5.7vw,6.2rem)] leading-[0.9] tracking-[-0.045em] text-[#3b303a]";

export function Workflow() {
  const steps = [
    ["01", "Bring the master", "Upload the finished film and choose every destination it needs to reach."],
    ["02", "Measure against reality", "Preflight reads current, cited requirements and measures the file with media tools."],
    ["03", "Leave with proof", "Approve safe repairs, revalidate the result, and receive a destination-ready package."],
  ];
  return (
    <section id="how-it-works" className="bg-[#c9bec4] px-6 py-28 text-[#40343e] sm:px-10 sm:py-36 lg:px-14">
      <div className="mx-auto max-w-[1160px]">
        <p className={eyebrow}>How it works</p>
        <div className="mt-7 grid gap-12 lg:grid-cols-[0.82fr_1.18fr]">
          <h2 className={heading}>From finished master to confident delivery.</h2>
          <p className="max-w-[38rem] self-end text-lg leading-relaxed text-[#574753]">The film stays yours. Preflight handles the measurable work between final export and the moment a destination receives it.</p>
        </div>
        <ol className="mt-20 grid border-y border-[#665361]/20 md:grid-cols-3">
          {steps.map(([number, title, body], index) => (
            <li key={number} className={`py-9 md:px-8 ${index ? "border-t border-[#665361]/20 md:border-l md:border-t-0" : ""}`}>
              <span className="font-mono text-[10px] text-[#806d7b]">{number}</span>
              <h3 className="mt-8 font-display text-3xl text-[#3b303a]">{title}</h3>
              <p className="mt-4 max-w-[20rem] text-sm leading-relaxed text-[#5c4c58]">{body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Checks() {
  const checks = ["Picture & container", "Sound & loudness", "Subtitles & captions", "Metadata & artwork"];
  return (
    <section className="bg-[#b7a9b5] px-6 py-28 text-[#3b303a] sm:px-10 sm:py-40 lg:px-14">
      <div className="mx-auto grid max-w-[1160px] items-center gap-16 lg:grid-cols-[1.18fr_0.82fr]">
        <div className="relative overflow-hidden rounded-[4px_120px_4px_4px] shadow-[0_30px_70px_rgba(57,42,54,0.24)]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/film/finishing-suite-v3.png" alt="A documentary master being reviewed in a professional finishing suite." className="aspect-[1.25/1] w-full object-cover" />
        </div>
        <div>
          <p className={eyebrow}>What Preflight checks</p>
          <h2 className={`${heading} mt-7`}>Every part of the film that has to arrive intact.</h2>
          <p className="mt-7 max-w-[32rem] text-[16px] leading-[1.7] text-[#554551]">A requirement is cited. A file property is measured. Preflight keeps those two facts beside each other, so readiness never collapses into a vague score.</p>
          <ul className="mt-10 border-t border-[#665361]/25">
            {checks.map((item) => <li key={item} className="flex items-center justify-between border-b border-[#665361]/25 py-4 text-sm font-medium"><span>{item}</span><span className="text-[#7b6877]">Measured</span></li>)}
          </ul>
        </div>
      </div>
    </section>
  );
}

export function DestinationReadiness() {
  return (
    <section className="bg-[#c9bec4] px-6 py-28 text-[#3b303a] sm:px-10 sm:py-40 lg:px-14">
      <div className="mx-auto max-w-[1160px]">
        <div className="grid gap-14 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className={eyebrow}>Destination readiness</p>
            <h2 className={`${heading} mt-7`}>One master. Different ways out.</h2>
          </div>
          <div className="self-end">
            <p className="max-w-[39rem] text-lg leading-relaxed text-[#554551]">Festivals and platforms do not ask for the same thing. Preflight reads the current specification, prepares the right version, and records why each decision was made.</p>
          </div>
        </div>
        {/* The section's whole claim is that these two destinations want
            different things, so they have to read as two. A single panel with
            a hairline seam merged them into one block and said the opposite. */}
        <div className="mt-20 grid gap-10 md:grid-cols-2 md:gap-0">
          {[
            {
              destination: "Berlinale",
              requirement: "Burned-in subtitles.",
              detail:
                "A package built to the festival’s published picture and subtitle specification.",
            },
            {
              destination: "Artdocfest",
              requirement: "SubRip beside the film.",
              detail:
                "The same master leaves differently because the destination requires it.",
            },
          ].map((entry, index) => (
            <article
              key={entry.destination}
              className={`border-t border-[#5f4c5b]/35 pt-7 md:pt-8 ${
                index === 1
                  ? "md:border-l md:border-l-[#5f4c5b]/25 md:pl-12"
                  : "md:pr-12"
              }`}
            >
              <p className={eyebrow}>{entry.destination}</p>
              <h3 className="mt-5 font-display text-[clamp(2rem,3.2vw,2.75rem)] leading-[1.05]">
                {entry.requirement}
              </h3>
              <p className="mt-4 max-w-[26rem] text-sm leading-relaxed text-[#554551]">
                {entry.detail}
              </p>
            </article>
          ))}
        </div>
        <div className="mt-16 grid gap-8 border-t border-[#665361]/20 pt-10 sm:grid-cols-3">
          {[['Current', 'Requirements are retrieved, dated and hashed.'], ['Safe', 'Only deterministic repairs run after approval.'], ['Traceable', 'The package carries its sources and transformations.']].map(([title, body]) => <div key={title}><p className="font-display text-3xl">{title}</p><p className="mt-3 max-w-[18rem] text-sm leading-relaxed text-[#5b4a57]">{body}</p></div>)}
        </div>
      </div>
    </section>
  );
}

export function FinalCall() {
  return (
    <section className="bg-[#4a3948] px-6 py-28 text-center text-[#f0e9e7] sm:px-10 sm:py-40">
      <div className="mx-auto max-w-[900px]">
        <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[#cbbbc4]">Ready when the film is</p>
        <h2 className="mt-8 font-display text-[clamp(4rem,7vw,7.5rem)] leading-[0.86] tracking-[-0.05em]">Know before you deliver.</h2>
        <p className="mx-auto mt-7 max-w-[36rem] text-base leading-relaxed text-[#ded3d8]">Measure the master, prepare every destination, and send a package that carries its own evidence.</p>
        <Link href="/projects" className="mt-9 inline-flex rounded-[4px] bg-[#efe7e4] px-7 py-3.5 text-sm font-medium text-[#40333f] transition hover:bg-white">Prepare your film</Link>
      </div>
    </section>
  );
}

export function LandingFooter() {
  return <footer className="bg-[#4a3948] px-6 pb-10 text-[#cbbbc4] sm:px-10"><div className="mx-auto flex max-w-[1160px] items-center justify-between border-t border-white/10 pt-8 text-[10px] uppercase tracking-[0.2em]"><span>Pre—flight</span><span>Finished media / ready to travel</span></div></footer>;
}
