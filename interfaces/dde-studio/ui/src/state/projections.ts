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

export interface SourceWorkspaceOption {
  readonly workspaceId: string;
  readonly currentRevision: string;
  readonly missionId: string | null;
  readonly purpose: string | null;
  readonly createdAt: string;
}

export interface SourceWorkspaceInventory {
  readonly options: readonly SourceWorkspaceOption[];
  readonly selectionState: "EMPTY" | "UNIQUE" | "AMBIGUOUS";
  readonly autoSelectedWorkspaceId: string | null;
  readonly availability: Availability;
  readonly reason?: string | null;
}

export interface VerificationCheckSnapshot {
  readonly checkRef: string;
  readonly kind: string;
  readonly status: string;
  readonly detail: string | null;
}

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
  readonly verificationRequestId: string | null;
  readonly verificationRequestState: string | null;
  readonly verificationRequestReason: string | null;
  readonly verificationRequiredKinds: readonly string[];
  readonly verificationRunId: string | null;
  readonly verificationRunStatus: string | null;
  readonly verificationConfidence: number | null;
  readonly verificationChecks: readonly VerificationCheckSnapshot[];
  readonly verificationEvidenceRefs: readonly string[];
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

export type FrontendChatMode = "ASK" | "PLAN" | "EXECUTE";

export interface FrontendChatConversation {
  readonly conversationId: string;
  readonly projectId: string;
  readonly missionId: string | null;
  readonly activeCandidateId: string | null;
  readonly designSessionId: string | null;
  readonly screenKey: string | null;
  readonly selectedNodeKeys: readonly string[];
  readonly viewport: string;
  readonly title: string | null;
  readonly status: "OPEN" | "ARCHIVED";
  readonly mode: FrontendChatMode;
  readonly modelProfileId: string | null;
  readonly activeWorkspaceId: string | null;
  readonly activePlanId: string | null;
  readonly policyId: string | null;
  readonly activeWorkerSessionId: string | null;
  readonly contextDomain:
    | "DDE" | "MISSION" | "TASK" | "FRONTEND_STUDIO" | "QUALITY"
    | "RESEARCH" | "DECISIONS" | "FLEET" | "EVIDENCE" | null;
  readonly activeTaskId: string | null;
  readonly activeWorkerRunId: string | null;
  readonly activeVerificationRunId: string | null;
  readonly activeArtifactRef: string | null;
  readonly parentConversationId: string | null;
  readonly branchedFromTurnId: string | null;
  readonly pinnedContextRefs: readonly string[];
  readonly createdBy: string | null;
  readonly archivedAt: string | null;
  readonly lockVersion: number;
  readonly createdAt: string;
  readonly updatedAt: string;
}

/** Canonical name; FrontendChatConversation remains a wire compatibility alias. */
export type DdeChatConversation = FrontendChatConversation;
export type DdeChatMode = FrontendChatMode;

export interface FrontendChatTurn {
  readonly turnId: string;
  readonly conversationId: string;
  readonly sequence: number;
  readonly role: "user" | "studio";
  readonly text: string;
  readonly intent: string;
  readonly outcome: "ROUTED" | "REFUSED" | "ANSWERED";
  readonly refusalCode: string | null;
  readonly refusalDetail: string | null;
  readonly resolvedContext: Readonly<Record<string, unknown>>;
  readonly producedRefs: readonly string[];
  readonly attachmentIds: readonly string[];
  readonly planId: string | null;
  readonly modelProfileId: string | null;
  readonly createdAt: string;
}

export interface FrontendChatThread {
  readonly conversation: FrontendChatConversation | null;
  readonly turns: readonly FrontendChatTurn[];
}

export interface FrontendChatAttachment {
  readonly attachmentId: string;
  readonly conversationId: string;
  readonly turnId: string | null;
  readonly sourceKind: "UPLOAD" | "WORKSPACE_FILE";
  readonly filename: string;
  readonly mediaType: string;
  readonly sizeBytes: number;
  readonly contentHash: string | null;
  readonly workspacePath: string | null;
  readonly extractionState: string;
  readonly status: "RESERVED" | "ACTIVE" | "REMOVED";
  readonly createdAt: string;
}

export interface FrontendChatPlanStep {
  readonly stepId: string;
  readonly sequence: number;
  readonly title: string;
  readonly description: string;
  readonly state: string;
  readonly attempt: number;
  readonly commandType: string | null;
  readonly targetType: string | null;
  readonly targetId: string | null;
  readonly parameters: Readonly<Record<string, unknown>>;
  readonly dependsOn: readonly string[];
  readonly evidenceRefs: readonly string[];
  readonly commandId: string | null;
  readonly resultSummary: string | null;
  readonly errorCode: string | null;
  readonly errorDetail: string | null;
  readonly idempotencyKey: string | null;
  readonly expectedRequestHash: string | null;
}

export interface FrontendChatPlan {
  readonly planId: string;
  readonly conversationId: string;
  readonly title: string;
  readonly objective: string;
  readonly state: string;
  readonly approvalRequired: boolean;
  readonly approvedBy: string | null;
  readonly approvedAt: string | null;
  readonly steps: readonly FrontendChatPlanStep[];
  readonly activeStepId: string | null;
  readonly workspaceId: string | null;
  readonly taskGraphId: string | null;
  readonly lockVersion: number;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface FrontendChatActivity {
  readonly activityId: string;
  readonly conversationId: string;
  readonly sequence: number;
  readonly kind: string;
  readonly state: string;
  readonly label: string;
  readonly detail: string | null;
  readonly refs: Readonly<Record<string, unknown>>;
  readonly cancellable: boolean;
  readonly cancelReason: string | null;
  readonly commandId: string | null;
  readonly createdAt: string;
}

export interface FrontendChatCheckpoint {
  readonly checkpointId: string;
  readonly conversationId: string;
  readonly turnSequence: number;
  readonly mode: FrontendChatMode;
  readonly modelProfileId: string | null;
  readonly planId: string | null;
  readonly workspaceId: string | null;
  readonly pinnedContextRefs: readonly string[];
  readonly attachmentRefs: readonly string[];
  readonly workspaceRevision: string | null;
  readonly diffHash: string | null;
  readonly contextHash: string;
  readonly note: string | null;
  readonly createdAt: string;
}

export interface FrontendChatChange {
  readonly path: string;
  readonly diffText: string;
  readonly diffHash: string;
  readonly reviewDecision: "PENDING" | "ACCEPTED" | "REVERTED";
}

export interface FrontendChatChanges {
  readonly workspaceId: string;
  readonly baseRevision: string;
  readonly workspaceRevision: string | null;
  readonly diffHash: string;
  readonly changes: readonly FrontendChatChange[];
}

export interface FrontendChatModelOption {
  readonly optionId: string;
  readonly label: string;
  readonly provider: string;
  readonly profileId: string | null;
  readonly modelId: string | null;
  readonly status: string;
  readonly reason: string;
  readonly requiresApproval: boolean;
  readonly capabilities: readonly string[];
}

export interface FrontendChatTokenAllocation {
  readonly budgetTokens: number;
  readonly usedTokens: number;
  readonly utilization: number;
  readonly promptTokens: number;
  readonly liveContextTokens: number;
  readonly systemReserveTokens: number;
}

export interface FrontendChatMemoryContextItem {
  readonly memoryId: string;
  readonly scopeKind: string;
  readonly scopeRef: string;
  readonly trustClass: string;
  readonly sourceType: string;
  readonly text: string;
  readonly estimatedTokens: number;
  readonly score: number;
  readonly truncated: boolean;
  readonly storageBackend: string;
  readonly sourceRefs: readonly string[];
}

export interface FrontendChatContextSnapshotProjection {
  readonly contextSnapshotId: string;
  readonly reason: string;
  readonly estimatedTokens: number;
  readonly budgetTokens: number;
  readonly archiveStorageBackend: string | null;
  readonly archiveStorageKey: string | null;
  readonly archiveHash: string | null;
  readonly archiveSizeBytes: number | null;
}

export interface FrontendChatContextBudget {
  readonly estimatedTokens: number;
  readonly budgetTokens: number;
  readonly includedRefs: readonly string[];
  readonly omittedRefs: readonly string[];
  readonly omissionReasons: Readonly<Record<string, string>>;
  readonly items: readonly Readonly<Record<string, unknown>>[];
  readonly allocation?: FrontendChatTokenAllocation | null;
  readonly memoryContext?: readonly FrontendChatMemoryContextItem[];
  readonly historyContext?: readonly Readonly<Record<string, unknown>>[];
  readonly historySummary?: string | null;
  readonly managedOmittedRefs?: readonly string[];
  readonly managedOmissionReasons?: Readonly<Record<string, string>>;
  readonly contextSnapshot?: FrontendChatContextSnapshotProjection | null;
}

export interface FrontendHostContext {
  readonly missionId: string;
  readonly projectId: string;
  readonly projectName: string;
}

export interface ScreenAuditSummary {
  readonly availability: string; readonly currentness: string; readonly auditRunId: string | null;
  readonly runStatus: string | null; readonly trigger: string | null; readonly summaryState: string;
  readonly pxgRevision: number | null; readonly contractVersion: number | null; readonly sourceRevision: string | null;
  readonly screenCount: number; readonly unresolvedFindings: number; readonly blockingFindings: number; readonly staleFindings: number;
  readonly findingCountsByDimension: Readonly<Record<string, number>>; readonly assessmentCounts: Readonly<Record<string, number>>;
}
export interface ScreenAuditScreen {
  readonly recordId: string; readonly auditRunId: string; readonly pxgKey: string; readonly screenKind: string; readonly platform: string;
  readonly routeIdentity: string | null; readonly sourceRefs: readonly Readonly<Record<string, unknown>>[]; readonly journeyRefs: readonly string[];
  readonly roleRefs: readonly string[]; readonly featureRequirementRefs: readonly string[]; readonly implementationState: string; readonly assessmentState: string;
  readonly dimensionStates: Readonly<Record<string, string>>; readonly stale: boolean;
}
export interface ScreenAuditFinding {
  readonly findingId: string; readonly pxgKey: string | null; readonly nodeKey: string | null; readonly findingType: string; readonly dimension: string;
  readonly severity: string; readonly status: string; readonly assessmentState: string; readonly message: string; readonly evidenceRefs: readonly string[];
  readonly requirementRefs: readonly string[]; readonly journeyRefs: readonly string[]; readonly roleRefs: readonly string[]; readonly ruleId: string; readonly stale: boolean;
}
export interface ScreenAuditMatrix { readonly summary: ScreenAuditSummary; readonly screens: readonly ScreenAuditScreen[]; readonly findings: readonly ScreenAuditFinding[]; }

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
  readonly sourceWorkspaces: SourceWorkspaceInventory;
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
