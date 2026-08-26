import type { AssertionResult } from "@/lib/types";

/**
 * One status language for the whole product.
 *
 * Every status carries three signals: a glyph, a label, and a colour — in that
 * order of importance. Colour is the last of the three because a producer
 * checking a delivery at 2am on a colour-managed monitor, or reading a
 * screenshot a post house sent them, should get the same answer either way.
 *
 * The vocabulary is deliberately small. A dozen shades of "not quite ready"
 * would be a way of avoiding the sentence the user actually needs.
 */

export type Tone =
  | "ok"
  | "review"
  | "act"
  | "stop"
  | "think"
  | "idle";

const TONE: Record<Tone, { fg: string; bg: string; ring: string }> = {
  ok: { fg: "text-ok", bg: "bg-ok-bg", ring: "ring-ok/25" },
  review: { fg: "text-review", bg: "bg-review-bg", ring: "ring-review/25" },
  act: { fg: "text-act", bg: "bg-act-bg", ring: "ring-act/25" },
  stop: { fg: "text-stop", bg: "bg-stop-bg", ring: "ring-stop/25" },
  think: { fg: "text-think", bg: "bg-think-bg", ring: "ring-think/25" },
  idle: { fg: "text-paper-300", bg: "bg-idle-bg", ring: "ring-white/10" },
};

const GLYPH: Record<Tone, string> = {
  ok: "✓",
  review: "?",
  act: "!",
  stop: "✕",
  think: "◍",
  idle: "·",
};

/**
 * How each assertion result reads to a filmmaker.
 *
 * "REPAIRABLE" is a word about the system. "Preflight can fix this" is a
 * sentence about their film, and it is the one that belongs on screen.
 */
export const RESULT: Record<AssertionResult, { label: string; tone: Tone }> = {
  PASS: { label: "Meets requirement", tone: "ok" },
  REPAIRABLE: { label: "Preflight can fix this", tone: "think" },
  REVIEW_REQUIRED: { label: "Needs your decision", tone: "review" },
  UNSUPPORTED: { label: "Preflight will not do this", tone: "stop" },
  AMBIGUOUS: { label: "Sources disagree", tone: "review" },
  NOT_MEASURED: { label: "Not measured", tone: "idle" },
  NOT_APPLICABLE: { label: "Does not apply", tone: "idle" },
};

export function StatusChip({
  tone,
  children,
  className = "",
}: {
  tone: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  const t = TONE[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-[3px] px-2 py-[3px]
                  text-[11px] font-medium leading-none ring-1 ring-inset
                  ${t.fg} ${t.bg} ${t.ring} ${className}`}
    >
      <span aria-hidden="true" className="text-[10px] leading-none">
        {GLYPH[tone]}
      </span>
      {children}
    </span>
  );
}

export function ResultChip({ result }: { result: AssertionResult }) {
  const { label, tone } = RESULT[result] ?? RESULT.NOT_MEASURED;
  return <StatusChip tone={tone}>{label}</StatusChip>;
}

/**
 * A project's position in the workflow, in the user's terms.
 *
 * These map onto real backend state. Nothing here is a percentage: the
 * backend does not report one for media work, and inventing it would be a
 * number the user could catch us making up.
 */
export type ProjectStage =
  | "DRAFT"
  | "ASSETS_UPLOADED"
  | "DESTINATIONS_CONFIRMED"
  | "PREFLIGHT_COMPLETE"
  | "REPAIR_APPROVED"
  | "PROCESSING"
  | "PACKAGES_READY"
  | "DELIVERED"
  | "DELETION_PENDING"
  | "DELETED";

export const STAGE: Record<
  ProjectStage,
  { label: string; tone: Tone; next: string }
> = {
  DRAFT: { label: "No master yet", tone: "idle", next: "Upload your master" },
  ASSETS_UPLOADED: {
    label: "Master measured",
    tone: "think",
    next: "Choose destinations",
  },
  DESTINATIONS_CONFIRMED: {
    label: "Requirements retrieved",
    tone: "think",
    next: "Run preflight",
  },
  PREFLIGHT_COMPLETE: {
    label: "Action required",
    tone: "act",
    next: "Review the repair plan",
  },
  REPAIR_APPROVED: {
    label: "Approved",
    tone: "think",
    next: "Run the repairs",
  },
  PROCESSING: { label: "Processing", tone: "think", next: "Working" },
  PACKAGES_READY: { label: "Verified", tone: "ok", next: "Create a delivery room" },
  DELIVERED: { label: "Delivered", tone: "ok", next: "View the passport" },
  DELETION_PENDING: { label: "Deleting", tone: "idle", next: "Removing files" },
  DELETED: { label: "Deleted", tone: "idle", next: "" },
};

export function StageChip({ state }: { state: string }) {
  const stage = STAGE[state as ProjectStage] ?? STAGE.DRAFT;
  return <StatusChip tone={stage.tone}>{stage.label}</StatusChip>;
}

/** The safety classification of a repair, in plain language. */
export const SAFETY: Record<string, { label: string; tone: Tone; note: string }> = {
  green: {
    label: "Safe to run",
    tone: "ok",
    note: "Deterministic, and reversible in the sense that your original is untouched.",
  },
  yellow: {
    label: "Your decision",
    tone: "review",
    note: "This can change the picture, the timing, or the meaning of the work.",
  },
  red: {
    label: "Preflight will not do this",
    tone: "stop",
    note: "This needs judgement or authority Preflight does not have.",
  },
};

const UNKNOWN_SAFETY = {
  label: "Preflight will not do this",
  tone: "stop" as Tone,
  note: "This operation is not one Preflight is willing to perform.",
};

export function SafetyChip({ safety }: { safety: string }) {
  const level = SAFETY[safety] ?? UNKNOWN_SAFETY;
  return <StatusChip tone={level.tone}>{level.label}</StatusChip>;
}

/**
 * Indeterminate progress, for work whose duration is genuinely unknown.
 *
 * Deliberately not a percentage. The backend reports job state, not fraction
 * complete, and a bar that crawls to 90% and waits is a bar that lies.
 */
export function Working({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3" role="status" aria-live="polite">
      <div className="relative h-[2px] w-24 overflow-hidden rounded-full bg-ink-200">
        <div className="indeterminate absolute inset-0" aria-hidden="true" />
      </div>
      <span className="text-sm text-paper-300">{label}</span>
    </div>
  );
}
