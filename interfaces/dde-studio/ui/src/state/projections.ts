/**
 * The read-projection shapes the workbench consumes, mirroring
 * `engine/studio/reads.py`.
 *
 * The important type here is `CountValue`. A count is either a real number
 * from a real inventory, or it is explicitly unknown — there is no
 * zero-as-default, because a group whose backing service does not exist
 * rendering `0` is a lie that looks exactly like a fact.
 */

export type Availability =
  | "AVAILABLE"
  | "EMPTY"
  | "NOT_CONFIGURED"
  | "NOT_IMPLEMENTED"
  | "UNAVAILABLE"
  | "DEGRADED";

export interface CountValue {
  readonly value: number | null;
  readonly availability: Availability;
  readonly reason?: string | null;
}

export interface ExplorerGroup {
  readonly key: string;
  readonly title: string;
  readonly count: CountValue;
  readonly children?: readonly ExplorerGroup[];
}

export interface ProjectExplorerSnapshot {
  readonly projectId: string;
  readonly pxgRevision: number;
  readonly groups: readonly ExplorerGroup[];
}

export type CoverageState = "UNASSESSED" | "PARTIAL" | "ASSESSED" | "BLOCKED";

export interface CoverageSummary {
  readonly summaryState: CoverageState;
  /** Null whenever anything is unknown. The ring renders an em-dash. */
  readonly weightedPercent: number | null;
  readonly contractVersion: number | null;
  readonly pxgRevision: number | null;
  readonly currentPxgRevision: number;
  readonly stale: boolean;
  readonly dimensionStates: readonly (readonly [string, CoverageState])[];
  readonly blockingFindingCount: number;
  readonly availability: Availability;
  readonly reason?: string | null;
}

export interface ModelRoleView {
  readonly role: string;
  readonly desired: string | null;
  readonly configured: string | null;
  readonly serving: string | null;
  /** "UNATTESTED" until a ModelServingEvidence source exists. */
  readonly servingConfidence: string;
}

export interface OrchestratorFrontendStatus {
  readonly runtimeState: string;
  readonly roles: readonly ModelRoleView[];
  readonly designDirector: string | null;
  readonly activityEventCount: CountValue;
  readonly availability: Availability;
  readonly reason?: string | null;
}

export interface StudioSyncSnapshot {
  readonly state: string;
  readonly durablePxgRevision: number;
  readonly pendingMutationCount: number;
  readonly durableRevisionAt: string | null;
  readonly buildVersion: string | null;
}

export interface AttentionItemView {
  readonly category: string;
  readonly detail: string;
  readonly pxgKey: string | null;
}

export interface AttentionCenterSnapshot {
  readonly items: readonly AttentionItemView[];
  readonly count: CountValue;
  readonly availability: Availability;
  readonly reason?: string | null;
}


export interface ScreenNode {
  readonly pxgKey: string;
  readonly title: string;
  readonly route: string | null;
  readonly childKeys: readonly string[];
}

export type PreviewState =
  | "BUILDING"
  | "LOADING"
  | "LIVE"
  | "STALE"
  | "RUNTIME_ERROR"
  | "RENDER_ERROR"
  | "UNAVAILABLE"
  | "STOPPED";

export interface CandidateCardSnapshot {
  readonly candidateId: string;
  readonly title: string;
  readonly state: string;
  readonly origin: string;
  readonly workspaceId: string | null;
  readonly basePxgRevision: number;
  readonly currentPxgRevision: number;
  readonly stale: boolean;
  readonly scopeKeys: readonly string[];
  readonly previewSessionId: string | null;
  readonly previewState: PreviewState | null;
  readonly previewStateDetail: string | null;
}

export interface CandidateBoardSnapshot {
  readonly cards: readonly CandidateCardSnapshot[];
  readonly count: CountValue;
}

export interface PreviewDocument {
  readonly previewSessionId: string;
  readonly candidateId: string;
  readonly workspaceId: string;
  readonly screenKey: string;
  readonly state: PreviewState;
  readonly viewport: string;
  readonly route: string | null;
  readonly candidatePxgRevision: number;
  readonly sourceRevision: string;
  readonly documentPath: string | null;
  readonly contentHash: string | null;
  readonly stateDetail: string | null;
  readonly content: string;
}

export interface InspectorPropertyDescriptor {
  readonly propertyName: string;
  readonly value: string | null;
  readonly valueType: string;
  readonly units: string | null;
  readonly semanticTokenClass: string;
  readonly legalValues: readonly string[];
  readonly computedValue: string | null;
  readonly responsiveSemantics: string;
  readonly sourcePath: string | null;
  readonly mutationOperation: string;
  readonly lockBehavior: string;
  readonly writable: boolean;
  readonly lockReason: string | null;
  readonly accessibilityEffect: string;
  readonly validation: string;
  readonly previewInvalidation: readonly string[];
  readonly requiredVerification: readonly string[];
}

export interface InspectorDescriptor {
  readonly candidateId: string;
  readonly pxgKey: string;
  readonly title: string;
  readonly nodeKind: string;
  readonly candidateState: string;
  readonly graphRevision: number;
  readonly stale: boolean;
  readonly sourceMapping: string;
  readonly sourcePath: string | null;
  readonly sourceSymbol: string | null;
  readonly elementId: string | null;
  readonly properties: readonly InspectorPropertyDescriptor[];
  readonly requiredVerification: readonly string[];
}

export interface FrontendHostContext {
  readonly missionId: string;
  readonly projectId: string;
  readonly projectName: string;
}

export interface FrontendStudioSnapshot {
  readonly projectId: string;
  readonly observedAt: string;
  readonly pxgRevision: number;
  readonly contractVersion: number | null;
  readonly explorer: ProjectExplorerSnapshot;
  readonly coverage: CoverageSummary;
  readonly orchestrator: OrchestratorFrontendStatus;
  readonly sync: StudioSyncSnapshot;
  readonly attention: AttentionCenterSnapshot;
  readonly screens: readonly ScreenNode[];
  readonly candidates: CandidateBoardSnapshot;
  readonly degradedReasons: readonly string[];
}

export type StudioMode =
  | "design"
  | "coverage"
  | "architecture"
  | "qa"
  | "source";

export const STUDIO_MODES: readonly StudioMode[] = [
  "design",
  "coverage",
  "architecture",
  "qa",
  "source",
];

/** The em-dash a count renders when it is genuinely unknown. */
export const UNKNOWN_MARK = "—";

export function formatCount(count: CountValue): string {
  return count.value === null ? UNKNOWN_MARK : String(count.value);
}

/**
 * The coverage ring's label. Deliberately refuses to render a number for a
 * stale or partially assessed project: a percentage reads as certainty, and
 * "we have not checked" is not a percentage.
 */
export function formatCoverage(summary: CoverageSummary): string {
  if (summary.weightedPercent === null) return UNKNOWN_MARK;
  return `${Math.round(summary.weightedPercent)}%`;
}

export function countTitle(count: CountValue): string | undefined {
  return count.value === null ? (count.reason ?? "unavailable") : undefined;
}
