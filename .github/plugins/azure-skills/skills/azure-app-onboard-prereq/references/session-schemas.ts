/**
 * Context + shared TypeScript interfaces for AppOnboard session artifacts:
 * context.json, active-session.json, and shared types used across all phases.
 *
 * Per-phase schemas (load only when entering that phase):
 * - prereq-schemas.ts (in azure-app-onboard-prereq) — prereq-output.json (PrereqOutput, BuildRequirements, CloudSdkFinding)
 * - session-schemas-prepare.ts — prepare-plan.json (PreparePlan, PlannedService, etc.)
 * - session-schemas-deploy.ts — scaffold-manifest.json, deploy-result.json
 *
 * Source of truth for JSON artifacts in `.copilot-azure/sessions/{session-id}/`.
 */

// ─── shared types (used across all phases) ───────────────────────────────────

export interface AppOnboardComponentStack {
  language: string;
  framework: string;
  version: string;
}

export type ReadinessStatus = "ready" | "fixesApplied" | "needsFixes" | "unknown";

export interface AppOnboardComponentReadiness {
  status: ReadinessStatus;
  fixes: string[];
}

export type VerdictLevel = "PASS" | "WARN" | "FAIL" | "SKIPPED";

export interface AppOnboardComponentVerdicts {
  build: VerdictLevel;
  completeness: Exclude<VerdictLevel, "SKIPPED">;
  deployability: Exclude<VerdictLevel, "SKIPPED">;
}

export interface AppOnboardComponentFinding {
  category: "build" | "completeness" | "deployability";
  verdict: VerdictLevel;
  summary: string;
  fix: string | null;
}

export interface AppOnboardComponent {
  name: string;
  path: string;
  stack: AppOnboardComponentStack;
  readiness: AppOnboardComponentReadiness;
  verdicts?: AppOnboardComponentVerdicts;
  findings?: readonly AppOnboardComponentFinding[];
}

export interface AppOnboardAzureTarget {
  subscriptionId: string;
  /** Display name of the subscription (from `az account show --query name`).
   *  Shown at both approval gates so the user can verify the target. */
  subscriptionName: string;
  resourceGroup: string;
  region: string;
}

export interface AppOnboardRepoInfo {
  remote: string | null;
}

export interface AppOnboardOverride {
  key: string;
  value: string;
  reason: string;
}

export interface AppOnboardAppInfo {
  name: string;
}

export interface PostDeployRecommendation {
  title: string;
  reason: string;
  effort: "low" | "medium" | "high";
  services?: string[];
}

export interface DetectedService {
  type: string;
  version?: string;
  source: "compose" | "config" | "code";
}

// ─── context.json ─────────────────────────────────────────────────────────────

export interface AppOnboardIntent {
  userPrompt: string;
  description: string;
  users?: string;
  auth?: string;
  scale?: string;
  budget?: string;
  /** Set to true after prereq scan refines intent */
  refinedFromScan?: boolean;
  /** Facts discovered by the prereq scan */
  scanDiscoveredFacts?: string[];
}

export type AppOnboardPhase = "info" | "prereq" | "prepare" | "scaffold" | "deploy" | "cicd" | "observe";

export interface AppOnboardContext {
  sessionId: string;
  createdUtc: string;
  lastModifiedUtc: string;
  currentPhase: AppOnboardPhase | null;
  completedPhases: readonly AppOnboardPhase[];
  /** Human-readable 1-line summary of where the session stands, updated at each phase exit.
   *  Displayed in the session picker when the user resumes or switches sessions. */
  statusSummary?: string;
  intent: AppOnboardIntent;
  components: AppOnboardComponent[];
  azure: AppOnboardAzureTarget;
  repo: AppOnboardRepoInfo;
  app?: AppOnboardAppInfo;
  /** Infrastructure file types detected in repo: dockerfile, terraform, bicep, azure-yaml, github-actions */
  detectedInfra: readonly string[];
  /** Cloud provider targeted by detected IaC. Only populated when `.tf` or `.bicep` files found.
   *  Used by scaffold to distinguish "existing Azure IaC" (halt) from "non-Azure IaC" (generate Azure TF alongside). */
  detectedInfraProvider?: {
    terraform?: "azure" | "gcp" | "aws" | "multi" | "unknown";
  };
  /** Service dependencies parsed from docker-compose, config files, or code imports */
  detectedServices: readonly DetectedService[];
  overrides: AppOnboardOverride[];
  /** The skill to invoke next. Set by Step 2 (cloud SDK gate), Step 5 (specialized skill detection),
   *  or Step 8 (normal routing based on health + infra). Examples: "azure-cloud-migrate",
   *  "azure-hosted-copilot-sdk", "microsoft-foundry", "azure-app-onboard", "azure-prepare". */
  routeToSkill?: string;
  /** Why this route was chosen. Examples: "cloud-sdk-migration", "copilot-sdk-detected",
   *  "foundry-agents-detected", "ready-no-infra", "ready-existing-infra". */
  routeReason?: string;
}

// ─── active-session.json ─────────────────────────────────────────────────────

/** Pointer file at `.copilot-azure/sessions/active-session.json`.
 *  Avoids scanning all session folders on startup — read this one file
 *  to find the active session, then read that session's context.json. */
export interface ActiveSessionPointer {
  activeSessionId: string;
}

// PrereqOutput, BuildRequirements → see azure-app-onboard-prereq/references/prereq-schemas.ts