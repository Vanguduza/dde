/**
 * The structural conformance fixture.
 *
 * It renders the real workbench against a `TestHostBridge` carrying a
 * controlled projection, so the geometry assertions measure the actual
 * shell rather than a stand-in. The projection deliberately includes
 * unknown counts and an unassessed coverage summary: the fixture must
 * exercise the honest states, not a best case that hides them.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DdeStudioApp } from "../src/app/DdeStudioApp";
import { TestHostBridge } from "../src/bridge/TestHostBridge";
import type { FrontendStudioSnapshot } from "../src/state/projections";
import "../src/styles/tokens.css";
import "../src/styles/global.css";
import "../src/styles/panels.css";

const SNAPSHOT: FrontendStudioSnapshot = {
  projectId: "00000000-0000-0000-0000-000000000001",
  observedAt: "2026-09-04T12:00:00Z",
  pxgRevision: 4,
  contractVersion: 2,
  explorer: {
    projectId: "00000000-0000-0000-0000-000000000001",
    pxgRevision: 4,
    groups: [
      { key: "screens", title: "Screens", count: { value: 12, availability: "AVAILABLE" } },
      { key: "journeys", title: "Journeys", count: { value: 4, availability: "AVAILABLE" } },
      { key: "components", title: "Components", count: { value: 37, availability: "AVAILABLE" } },
      {
        key: "sources",
        title: "Sources",
        count: {
          value: null,
          availability: "NOT_IMPLEMENTED",
          reason: "DesignSourceRegistry is DDE-069 M8; no source adapter is wired yet",
        },
      },
      {
        key: "templates",
        title: "Templates",
        count: {
          value: null,
          availability: "NOT_IMPLEMENTED",
          reason: "TemplateRecommendationService is DDE-069 M8; not wired yet",
        },
      },
      { key: "locks", title: "Locks", count: { value: 3, availability: "AVAILABLE" } },
    ],
  },
  coverage: {
    summaryState: "PARTIAL",
    weightedPercent: null,
    contractVersion: 2,
    pxgRevision: 4,
    currentPxgRevision: 4,
    stale: false,
    dimensionStates: [
      ["screen", "ASSESSED"],
      ["journey", "ASSESSED"],
      ["accessibility", "PARTIAL"],
      ["responsive", "UNASSESSED"],
    ],
    blockingFindingCount: 2,
    availability: "AVAILABLE",
    reason: null,
  },
  orchestrator: {
    runtimeState: "UNKNOWN",
    roles: [
      {
        role: "manager_chair",
        desired: null,
        configured: null,
        serving: null,
        servingConfidence: "UNATTESTED",
      },
    ],
    designDirector: null,
    activityEventCount: {
      value: 2,
      availability: "AVAILABLE",
      reason: null,
    },
    activityWindow: [
      { eventType: "frontend.design.requested", occurredAt: "2026-09-04T11:57:00Z", missionId: "00000000-0000-0000-0000-000000000010", aggregateType: "mission" },
      { eventType: "frontend.preview.live", occurredAt: "2026-09-04T11:58:00Z", missionId: "00000000-0000-0000-0000-000000000010", aggregateType: "mission" },
    ],
    availability: "NOT_IMPLEMENTED",
    reason:
      "no ModelServingEvidence source is implemented (Blueprint Rev 3 section 5.4); serving identity stays unattested",
  },
  sync: {
    state: "SYNCED",
    durablePxgRevision: 4,
    pendingMutationCount: 0,
    durableRevisionAt: "2026-09-04T11:58:00Z",
    buildVersion: "dde-studio 0.1.0",
  },
  screens: [],
  sourceWorkspaces: {
    options: [],
    selectionState: "EMPTY",
    autoSelectedWorkspaceId: null,
    availability: "EMPTY",
    reason: "No READY source workspace is available in the structural fixture.",
  },
  sources: {
    providers: [
      { providerKey: "project-native", displayName: "Internal Components", sourceClass: "PROJECT_NATIVE", status: "NOT_CONFIGURED", healthDetail: "source registry has not been initialized", capabilities: [], itemCount: { value: null, availability: "NOT_CONFIGURED", reason: "provider has not been initialized" } },
      { providerKey: "dde-library", displayName: "DDE Library", sourceClass: "DDE_LIBRARY", status: "NOT_CONFIGURED", healthDetail: "source registry has not been initialized", capabilities: [], itemCount: { value: null, availability: "NOT_CONFIGURED", reason: "provider has not been initialized" } },
      { providerKey: "21st", displayName: "21st MCP", sourceClass: "EXTERNAL_REGISTRY", status: "NOT_CONFIGURED", healthDetail: "source registry has not been initialized", capabilities: [], itemCount: { value: null, availability: "NOT_CONFIGURED", reason: "provider has not been initialized" } },
      { providerKey: "donors", displayName: "Donor Sources", sourceClass: "DONOR", status: "NOT_CONFIGURED", healthDetail: "source registry has not been initialized", capabilities: [], itemCount: { value: null, availability: "NOT_CONFIGURED", reason: "provider has not been initialized" } },
    ],
    providerCount: { value: null, availability: "NOT_CONFIGURED", reason: "source registry has not been initialized" },
    artifactCount: { value: null, availability: "NOT_CONFIGURED", reason: "no indexed source inventory exists yet" },
    templateCount: { value: null, availability: "NOT_CONFIGURED", reason: "template recommendation has not run" },
    availability: "NOT_CONFIGURED",
    reason: "source registry has not been initialized",
  },
  candidates: { cards: [], count: { value: 0, availability: "EMPTY" } },
  attention: {
    items: [
      {
        attentionKey: "a".repeat(64),
        category: "coverage_missing",
        detail: "no PXG node implements screens/settings",
        pxgKey: "screens/settings",
      },
    ],
    count: { value: 1, availability: "AVAILABLE" },
    availability: "AVAILABLE",
  },
  degradedReasons: [],
};

const bridge = new TestHostBridge({
  reads: {
    "frontend.host.context": {
      missionId: "00000000-0000-0000-0000-000000000010",
      projectId: SNAPSHOT.projectId,
      missionSlug: "frontend-studio",
      missionTitle: "Frontend Studio",
      projectSlug: "logiflow-marketplace",
      principalId: "00000000-0000-0000-0000-000000000020",
      principalSlug: "tapiwa",
      availableProjects: [
        { projectId: SNAPSHOT.projectId, projectSlug: "logiflow-marketplace", missionId: "00000000-0000-0000-0000-000000000010", available: true, reason: null },
      ],
      modules: [
        { id: "frontend", label: "Frontend Studio", glyph: "◧", available: true, reason: null },
        { id: "knowledge", label: "Knowledge", glyph: "◎", available: true, reason: null },
      ],
      helpRef: "docs/truth/FRONTEND_STUDIO_REV3.md",
    },
    "frontend.studio.snapshot": SNAPSHOT,

    "vekl.projection": {
      availability: "AVAILABLE",
      sections: {
        stack_map: [], knowledge: [{ resourceId: "00000000-0000-0000-0000-000000000901", resourceKind: "OFFICIAL_DOC", title: "Pinned framework docs", publisher: "Framework", revision: "1.0.0", contentHash: "a".repeat(64), sourceTrust: "S2_FIRST_PARTY", lifecycleState: "REFERENCE_QUALIFIED", activationModes: ["READ_ONLY_CONTEXT"] }],
        tools_plugins_mcp: [], rules_hooks: [], loops: [], community_evidence: [], security: [], learning: [],
      },
      resources: [{ resourceId: "00000000-0000-0000-0000-000000000901", resourceKind: "OFFICIAL_DOC", title: "Pinned framework docs", publisher: "Framework", revision: "1.0.0", contentHash: "a".repeat(64), sourceTrust: "S2_FIRST_PARTY", lifecycleState: "REFERENCE_QUALIFIED", activationModes: ["READ_ONLY_CONTEXT"] }],
      manifests: [], invalidations: [],
      knowledgeGraph: {
        availability: "AVAILABLE", reason: null,
        unitMaps: [{ unitMapId: "00000000-0000-0000-0000-000000000902", unitLineageId: "lineage-a", unitRevisionHash: "b".repeat(64), taskIds: ["00000000-0000-0000-0000-000000000903"], objective: "Implement checkout", knowledgeReadinessState: "READY", challengeState: "CLEAR", invalidationReasons: [] }],
        knowledgeNodes: [
          { knowledgeNodeId: "00000000-0000-0000-0000-000000000904", nodeKind: "DEVELOPMENT_UNIT_PROJECTION", stableRef: "unit:lineage-a", authorityClass: "DERIVED_PROJECTION", authorityService: "engine.vekl.knowledge_service", contentHash: "c".repeat(64), objectType: "vekl_unit_map", objectId: "00000000-0000-0000-0000-000000000902", metadata: { readiness: "READY" } },
          { knowledgeNodeId: "00000000-0000-0000-0000-000000000905", nodeKind: "TASK", stableRef: "task:checkout", authorityClass: "EXECUTION_AUTHORITY_REF", authorityService: "engine.missions", contentHash: "e".repeat(64), objectType: "task", objectId: "00000000-0000-0000-0000-000000000903", metadata: { title: "Implement checkout" } },
          { knowledgeNodeId: "00000000-0000-0000-0000-000000000906", nodeKind: "CONTRACT", stableRef: "contract:checkout.api", authorityClass: "DECLARED_CONTRACT_REF", authorityService: "engine.planning", contentHash: "f".repeat(64), objectType: "task_graph_contract_ref", objectId: null, metadata: { contractRef: "checkout.api" } },
          { knowledgeNodeId: "00000000-0000-0000-0000-000000000907", nodeKind: "VEKL_RESOURCE", stableRef: "vekl-resource:00000000-0000-0000-0000-000000000901", authorityClass: "QUALIFIED_ENGINEERING_RESOURCE", authorityService: "engine.vekl", contentHash: "a".repeat(64), objectType: "vekl_resource", objectId: "00000000-0000-0000-0000-000000000901", metadata: { sourceTrust: "S2_FIRST_PARTY" } },
        ],
        knowledgeEdges: [
          { knowledgeEdgeId: "00000000-0000-0000-0000-000000000908", fromNodeId: "00000000-0000-0000-0000-000000000904", relationship: "derives_from", toNodeId: "00000000-0000-0000-0000-000000000905", provenanceHash: "1".repeat(64), provenanceRef: "task:checkout", derivationClass: "DETERMINISTIC" },
          { knowledgeEdgeId: "00000000-0000-0000-0000-000000000909", fromNodeId: "00000000-0000-0000-0000-000000000904", relationship: "consumes", toNodeId: "00000000-0000-0000-0000-000000000906", provenanceHash: "2".repeat(64), provenanceRef: "unit-contract", derivationClass: "DETERMINISTIC" },
          { knowledgeEdgeId: "00000000-0000-0000-0000-000000000910", fromNodeId: "00000000-0000-0000-0000-000000000907", relationship: "supports", toNodeId: "00000000-0000-0000-0000-000000000904", provenanceHash: "3".repeat(64), provenanceRef: "route-policy", derivationClass: "DETERMINISTIC" },
        ],
        retrievalRoutes: [], challenges: [], conflictObservations: [], researchFindings: [{ findingId: "00000000-0000-0000-0000-000000000911", concern: "PAYMENTS", claim: "Use idempotent checkout callbacks" }], graphInvalidations: [], resolutionTraces: [{ resolutionTraceId: "00000000-0000-0000-0000-000000000912", traceHash: "4".repeat(64), unitRevisionHash: "b".repeat(64), candidateDecisions: [{ resourceId: "00000000-0000-0000-0000-000000000901", selected: true }] }], graphSnapshotHash: "d".repeat(64),
      },
    },    "frontend.comments": { comments: [] },
    "frontend.editor.assists": { autoLayout: false, aiSuggest: false, availability: "EMPTY", reason: "defaults off" },
    "frontend.chat.thread": { conversation: null, turns: [] },
  },
});

const container = document.getElementById("dde-root");
if (container) {
  createRoot(container).render(
    <StrictMode>
      <DdeStudioApp
        bridge={bridge}
        projectName="LogiFlow Marketplace"
        buildVersion="dde-studio 0.1.0"
      />
    </StrictMode>,
  );
}
