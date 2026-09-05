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
      value: null,
      availability: "NOT_IMPLEMENTED",
      reason: "no frontend activity projection is wired yet",
    },
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
  candidates: { cards: [], count: { value: 0, availability: "EMPTY" } },
  attention: {
    items: [
      {
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
      projectName: "LogiFlow Marketplace",
    },
    "frontend.studio.snapshot": SNAPSHOT,
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
