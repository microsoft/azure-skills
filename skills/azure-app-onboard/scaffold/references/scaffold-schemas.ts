/**
 * Scaffold artifact schema — scaffold-manifest.json.
 * Read by scaffold refs (validation-and-manifest.md, scaffold-healing-rules.md, iac-generation-rules.md).
 */

// ─── Scaffold healing types ──────────────────────────────────────────────────

export type ScaffoldErrorClassification = "FIXABLE" | "BLOCKING";
export type ScaffoldHealingResult = "fixed" | "still-failing" | "blocked";

export interface ScaffoldHealingError {
  check: string;
  detail: string;
  classification: ScaffoldErrorClassification;
}

export interface ScaffoldHealingFix {
  file: string;
  change: string;
  reason: string;
}

export interface ScaffoldHealingAttempt {
  attempt: number;
  errors: ScaffoldHealingError[];
  fixes: ScaffoldHealingFix[];
  result: ScaffoldHealingResult;
  /** True when this healing attempt changed the service type or region — requires re-approval */
  planLevelChange?: boolean;
  /** Original service before the pivot (e.g., "App Service B1") */
  originalService?: string;
  /** New service after the pivot (e.g., "Container Apps Consumption") */
  newService?: string;
}

// ─── scaffold-manifest.json ──────────────────────────────────────────────────

export type SelfReviewRating = "VERIFIED" | "PLAUSIBLE" | "FLAGGED";

export interface ScaffoldFile {
  path: string;
  type: string;
}

export interface SelfReviewFinding {
  layer: string; // "L1" | "L2" | "L3" | "L4"
  claim: string;
  rating: SelfReviewRating;
  detail: string;
}

export type IacFormat = "bicep" | "terraform";

export interface ValidationCheck {
  name: string;
  passed: boolean;
  detail?: string;
}

export interface ValidationResult {
  status: "Validated" | "Partial" | "Failed";
  checks: ValidationCheck[];
  proof?: string;
}

/** One BLOCK failure emitted by scaffold-conformance.{ps1,sh} (Step 3c plan-conformance gate). */
export interface ConformanceFailure {
  id: string; // e.g. "TAGS-NO-CAMEL", "NO-PLAINTEXT-SECRET", "DB-TLS-ON"
  detail: string;
  file: string;
}

/** Result of the deterministic plan-conformance gate (subagent-validate.md Step 3c). */
export interface ConformanceResult {
  passed: boolean;
  failures: ConformanceFailure[];
  /** "script" when scaffold-conformance.{ps1,sh} ran; "manual" when the fallback assertion table was used. */
  source: "script" | "manual";
}

export interface ScaffoldManifest {
  /** Session id this manifest belongs to. */
  sessionId: string;
  /** UTC timestamp when scaffold completed. */
  scaffoldCompletedUtc: string;
  iacFormat: IacFormat;
  /** Deployment scope for the generated IaC (deploy preflight branches on this). */
  targetScope: "subscription" | "resourceGroup";
  files: ScaffoldFile[];
  /** Entry-point IaC file, e.g. "infra/main.bicep". */
  entryPoint?: string;
  /** Parameters file, e.g. "infra/main.parameters.json". */
  parametersFile?: string;
  /** Exact command the deploy phase runs to provision (read by deploy preflight). */
  deployCommand: string;
  /** Container Apps two-phase (infra, then image) wiring, when applicable. */
  twoPhaseWiring?: boolean;
  /** Ordered phase-2 steps (e.g. image build/push) for two-phase deploys. */
  phase2Steps?: readonly string[];
  selfReview: {
    findings: SelfReviewFinding[];
    healingAttempts?: readonly ScaffoldHealingAttempt[];
  };
  validationResult?: ValidationResult;
  conformance?: ConformanceResult;
}
