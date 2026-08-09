import Link from "next/link";

/**
 * Marketing page. One primary action, per the product's single-journey rule:
 * Master -> Destinations -> Preflight -> Packages -> Delivery.
 *
 * Deliberately absent: any sample project, any fabricated status, any number
 * that is not traceable to something the product actually measured.
 */
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-24">
      <p className="text-sm uppercase tracking-widest text-neutral-500">
        Preflight
      </p>

      <h1 className="mt-6 text-4xl font-semibold leading-tight sm:text-5xl">
        Never get rejected for something a machine could have measured.
      </h1>

      <p className="mt-6 text-lg leading-relaxed text-neutral-400">
        Upload one finished master. Preflight finds out what each destination
        requires right now, proves what your file actually is, fixes the gaps it
        can fix safely, and hands you a verified package with a receipt.
      </p>

      <Link
        href="/projects/new"
        className="mt-10 inline-flex w-fit items-center rounded-lg bg-neutral-100 px-6 py-3
                   font-medium text-neutral-950 transition hover:bg-white
                   focus:outline-none focus-visible:ring-2 focus-visible:ring-neutral-400
                   focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
      >
        Prepare a release package
      </Link>

      <p className="mt-10 max-w-xl text-sm leading-relaxed text-neutral-500">
        Preflight verifies against published requirements. It does not guarantee
        that a festival, broadcaster or platform will accept your delivery — and
        it will always tell you which of its findings it could not resolve.
      </p>
    </main>
  );
}
