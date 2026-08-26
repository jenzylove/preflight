/**
 * Shapes returned by the Preflight API.
 *
 * These mirror the API's response models exactly, snake_case included, rather
 * than being reshaped into something more comfortable for the UI. A rename
 * layer is a place for a field to quietly change meaning, and the distinctions
 * this API draws — measured against inferred, published against satisfied,
 * verified against accepted — are the whole product.
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
export type Safety = "green" | "yellow" | "red";

export interface Project {
  id: string;
  title: string;
  project_type: string;
  primary_language: string | null;
  runtime_seconds: number | null;
  country_of_origin: string | null;
  synopsis_chars: number | null;
  state: string;
  created_at: string;
}

/**
 * `measured_properties` is deliberately loose. It is whatever the inspector
 * recorded for that asset type, and the UI renders what is there rather than
 * assuming a fixed set — a video carries different facts from a subtitle file.
 */
export interface Asset {
  id: string;
  role: string;
  original_filename: string;
  content_type: string;
  byte_size: number;
  sha256: string | null;
  custody_state: string;
  immutable: boolean;
  measured_properties: Record<string, unknown> | null;
  inspector: string | null;
  inspector_version: string | null;
}

export interface Source {
  url: string | null;
  retrieved_at: string | null;
  trust_tier: string;
  excerpt: string | null;
}

export interface Destination {
  id: string;
  slug: string;
  name: string;
  official_domain: string | null;
  requires_private_spec: boolean;
  available: boolean;
  rule_pack_id: string | null;
  rule_pack_version: number | null;
  rule_pack_digest: string | null;
  mandatory_rules: number;
  total_rules: number;
  sources: Source[];
  /** Why this destination cannot be selected, when it cannot. */
  unavailable_reason: string | null;
}

export interface Assertion {
  rule_id: string;
  destination_id: string;
  asset_type: string;
  field: string;
  published: string;
  measured: string | number | boolean | null;
  result: AssertionResult;
  severity: Severity;
  source_url: string | null;
  source_excerpt: string | null;
  repair_operation: string | null;
  explanation: string | null;
}

export interface DestinationMatrix {
  destination_id: string;
  rule_pack_digest: string;
  satisfied: number;
  total: number;
  ready: boolean;
  blocking: string[];
  assertions: Assertion[];
}

/**
 * A cross-destination disagreement, after deduplication.
 *
 * `occurrences` is how many extracted rule pairs expressed the same
 * disagreement. It is shown because a requirement stated four different ways
 * by four sources is more firmly established than one stated once.
 */
export interface Conflict {
  assetType: string;
  field: string;
  strength: "hard" | "soft";
  destinations: [string, string];
  requirements: [string, string];
  severities?: [string, string];
  evidence?: [string, string];
  resolution: string;
  occurrences?: number;
  alsoStated?: [string[], string[]];
}

export interface PlanStep {
  step_id: string;
  operation: string;
  safety: Safety;
  what_it_does: string;
  input_asset: string | null;
  output: string;
  parameters: Record<string, unknown>;
  resolves: string[];
  depends_on: string[];
  /** False for anything Preflight will not run on its own. */
  executable: boolean;
}

export interface Plan {
  plan_id: string | null;
  digest: string;
  steps: PlanStep[];
  needs_your_decision: PlanStep[];
  blocked: Array<Record<string, unknown>>;
  unresolved: Array<Record<string, unknown>>;
  preserved_assets: string[];
  estimated_seconds: number | null;
  shared_across_destinations: Record<string, string[]>;
}

export interface PreflightRun {
  run_id: string;
  comparison_digest: string;
  destinations: DestinationMatrix[];
  conflicts: Conflict[];
  plan: Plan;
  limitations: string[];
}

export interface Rule {
  rule_id: string;
  destination: string;
  asset_type: string;
  field: string;
  operator: string;
  expected: string | null;
  severity: Severity;
  confidence: string;
  source_url: string | null;
  source_excerpt: string | null;
  disposition: "accept" | "set_aside" | null;
  disposition_reason: string | null;
}

export interface JobStatus {
  job_id: string;
  type: string;
  state: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  attempt: number;
  error: string | null;
  message: string;
}

export interface Transformation {
  operation: string;
  parameters: Record<string, unknown>;
  input_sha256: string | null;
  output_sha256: string | null;
  /** True when the decoded picture came through a repair bit-identical. */
  picture_preserved: boolean | null;
}

export interface PackageFile {
  path: string;
  sha256: string;
}

export interface PackageSummary {
  id: string;
  destination_id: string;
  destination_name: string;
  state: string;
  verified: boolean;
  package_sha256: string | null;
  rule_pack_version: number | null;
  rule_pack_digest: string | null;
  requirements_satisfied: string;
  files: PackageFile[];
  transformations: Transformation[];
  limitations: string[];
  validator_version: string | null;
  created_at: string;
}

export interface DeliveryRoom {
  room_id: string;
  /** Returned once, at creation, and never recoverable afterwards. */
  url_token: string | null;
  recipient_label: string | null;
  expires_at: string;
  revoked_at: string | null;
  state: string;
  note: string;
}

export interface PublicRoom {
  project_title: string;
  destination: string;
  verified: boolean;
  package_sha256: string | null;
  file_count: number;
  expires_at: string;
  limitations: string[];
}

export interface Passport {
  version: number;
  digest: string;
  issued_at: string;
  passport: Record<string, unknown>;
  report: string;
}

export interface UploadIntent {
  asset_id: string;
  upload_url: string;
  expires_in_seconds: number;
}
