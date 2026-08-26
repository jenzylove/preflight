import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Instrument_Serif } from "next/font/google";
import "./globals.css";

/**
 * Three typefaces, each with a job.
 *
 * Instrument Serif carries the cinematic register on the landing page. Inter
 * carries the workspace, where legibility at small sizes matters more than
 * character. IBM Plex Mono is reserved for values that are genuinely technical
 * — hashes, codecs, measurements — because monospacing everything would make
 * the product look like a terminal rather than an instrument.
 */
const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const display = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-display",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Preflight — make sure your film is ready to leave",
  description:
    "Preflight retrieves what each destination currently requires, measures what your "
    + "master actually is, repairs what is safe to repair, and proves the result.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${display.variable} ${mono.variable}`}
    >
      <body className="min-h-screen bg-ink-000 font-sans text-paper-100 antialiased">
        {/* A keyboard user should not have to tab through the whole hero to
            reach the thing they came for. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50
                     focus:rounded focus:bg-paper-000 focus:px-4 focus:py-2 focus:text-ink-000"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
