import type { AssertionResult } from "@/lib/types";
import { RESULT_COPY } from "@/lib/types";

/**
 * Colour is never the only indicator: each badge carries a distinct glyph and
 * a text label, so the matrix is readable without colour vision and in a
 * screenshot printed in greyscale.
 */
const TONE_CLASSES: Record<string, string> = {
  pass: "bg-emerald-950 text-emerald-300 ring-emerald-800",
  fixable: "bg-sky-950 text-sky-300 ring-sky-800",
  review: "bg-amber-950 text-amber-300 ring-amber-800",
  blocked: "bg-rose-950 text-rose-300 ring-rose-800",
  ambiguous: "bg-violet-950 text-violet-300 ring-violet-800",
  unknown: "bg-neutral-800 text-neutral-300 ring-neutral-700",
  muted: "bg-neutral-900 text-neutral-500 ring-neutral-800",
};

const GLYPH: Record<AssertionResult, string> = {
  PASS: "✓",
  REPAIRABLE: "↻",
  REVIEW_REQUIRED: "!",
  UNSUPPORTED: "✕",
  AMBIGUOUS: "?",
  NOT_MEASURED: "–",
  NOT_APPLICABLE: "·",
};

export function StatusBadge({ result }: { result: AssertionResult }) {
  const { label, tone } = RESULT_COPY[result];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-2 py-0.5
                  text-xs font-medium ring-1 ring-inset ${TONE_CLASSES[tone]}`}
    >
      <span aria-hidden="true" className="font-bold">{GLYPH[result]}</span>
      {label}
    </span>
  );
}
