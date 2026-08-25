/**
 * Shapes returned by the Preflight API.
 *
 * These mirror the API's response models rather than being convenient for the
 * UI. Where the API distinguishes measured from inferred from unresolved, the
 * UI must too — collapsing those distinctions is how an interface ends up
 * claiming something the system never established.
 */

export type AssertionResult =
  | "PASS"
  | "REPAIRABLE"
  | "REVIEW_REQUIRED"
  | "UNSUPPORTED"
  | "AMBIGUOUS"
  | "NOT_MEASURED"
  | "NOT_APPLICABLE";

export type Severity = "required" | "recommended" | "context";

export interface Assertion {
  ruleId: string;
  assetType: string;
  field: string;
  published: string;
  measured: string | number | boolean | null;
  result: AssertionResult;
  severity: Severity;
  sourceUrl?: string;
  sourceExcerpt?: string;
  retrievedAt?: string;
  repairOperation?: string | null;
  explanation?: string;
}

export interface DestinationMatrix {
  destinationId: string;
  destinationName: string;
  rulePackVersion: number;
  rulePackDigest: string;
  ready: boolean;
  assertions: Assertion[];
}

export interface Conflict {
  assetType: string;
  field: string;
  strength: "hard" | "soft";
  destinations: [string, string];
  requirements: [string, string];
  severities: [string, string];
  evidenceUrls?: [string, string];
  excerpts?: [string, string];
  resolution: string;
}

export interface PreflightRun {
  runId: string;
  comparisonDigest: string;
  destinations: DestinationMatrix[];
  conflicts: Conflict[];
}

/** Human-facing copy for each result. Never the enum name. */
export const RESULT_COPY: Record<AssertionResult, { label: string; tone: Tone }> = {
  PASS: { label: "Meets requirement", tone: "pass" },
  REPAIRABLE: { label: "Preflight can fix this", tone: "fixable" },
  REVIEW_REQUIRED: { label: "Needs your decision", tone: "review" },
  UNSUPPORTED: { label: "Preflight cannot fix this", tone: "blocked" },
  AMBIGUOUS: { label: "Sources disagree", tone: "ambiguous" },
  NOT_MEASURED: { label: "Not measured", tone: "unknown" },
  NOT_APPLICABLE: { label: "Does not apply", tone: "muted" },
};

export type Tone =
  | "pass"
  | "fixable"
  | "review"
  | "blocked"
  | "ambiguous"
  | "unknown"
  | "muted";
