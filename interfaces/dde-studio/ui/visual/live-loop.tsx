import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DdeStudioApp } from "../src/app/DdeStudioApp";
import type { DdeCommand } from "../src/bridge/DdeHostBridge";
import { TestHostBridge } from "../src/bridge/TestHostBridge";
import type {
  FrontendStudioSnapshot,
  InspectorDescriptor,
  PreviewDocument,
} from "../src/state/projections";
import "../src/styles/tokens.css";
import "../src/styles/global.css";
import "../src/styles/panels.css";

const missionId = "00000000-0000-0000-0000-000000000010";
const projectId = "00000000-0000-0000-0000-000000000001";
const candidateId = "00000000-0000-0000-0000-000000000020";
const pxgKey = "screens/checkout#hero";
let previewNumber = 1;
let previewSessionId = `preview-${previewNumber}`;
let previewState: "LOADING" | "LIVE" | "STALE" = "LOADING";
let candidateState = "READY";
let spacing = "space2";

function snapshot(): FrontendStudioSnapshot {
  return {
    projectId,
    observedAt: new Date().toISOString(),
    pxgRevision: 4,
    contractVersion: 2,
    explorer: {
      projectId,
      pxgRevision: 4,
      groups: [
        { key: "screens", title: "Screens", count: { value: 1, availability: "AVAILABLE" } },
        { key: "journeys", title: "Journeys", count: { value: 0, availability: "EMPTY" } },
        { key: "components", title: "Components", count: { value: 1, availability: "AVAILABLE" } },
        {
          key: "sources",
          title: "Sources",
          count: { value: null, availability: "NOT_IMPLEMENTED", reason: "M8 not implemented" },
        },
        {
          key: "templates",
          title: "Templates",
          count: { value: null, availability: "NOT_IMPLEMENTED", reason: "M8 not implemented" },
        },
        { key: "locks", title: "Locks", count: { value: 0, availability: "EMPTY" } },
      ],
    },
    coverage: {
      summaryState: "PARTIAL",
      weightedPercent: null,
      contractVersion: 2,
      pxgRevision: 4,
      currentPxgRevision: 4,
      stale: false,
      dimensionStates: [["screen", "ASSESSED"]],
      blockingFindingCount: 0,
      availability: "AVAILABLE",
    },
    orchestrator: {
      runtimeState: "UNKNOWN",
      roles: [],
      designDirector: null,
      activityEventCount: { value: null, availability: "NOT_IMPLEMENTED", reason: "not wired" },
      availability: "NOT_IMPLEMENTED",
      reason: "serving identity unattested",
    },
    sync: {
      state: candidateState === "DIRTY" ? "PENDING" : "SYNCED",
      durablePxgRevision: 4,
      pendingMutationCount: candidateState === "DIRTY" ? 1 : 0,
      durableRevisionAt: new Date().toISOString(),
      buildVersion: "dde-studio test",
    },
    attention: {
      items: [],
      count: { value: 0, availability: "EMPTY" },
      availability: "AVAILABLE",
    },
    screens: [
      { pxgKey: "screens/checkout", title: "Checkout", route: "/checkout", childKeys: [pxgKey] },
    ],
    candidates: {
      count: { value: 1, availability: "AVAILABLE" },
      cards: [
        {
          candidateId,
          title: "Checkout spacing refinement",
          state: candidateState,
          origin: "DIRECT_EDIT",
          workspaceId: "00000000-0000-0000-0000-000000000030",
          basePxgRevision: 4,
          currentPxgRevision: 4,
          stale: false,
          scopeKeys: ["screens/checkout"],
          previewSessionId,
          previewState,
          previewStateDetail: `fixture ${previewState.toLowerCase()}`,
        },
      ],
    },
    degradedReasons: [],
  };
}

function previewDocument(): PreviewDocument {
  const contentHash = `hash-${previewSessionId}-${spacing}`;
  const content = `<!doctype html><html><body>
<div data-dde-pxg-key="${pxgKey}" data-spacing="${spacing}" style="padding:16px">Hero ${spacing}</div>
<script>(()=>{const meta={previewSessionId:${JSON.stringify(previewSessionId)},contentHash:${JSON.stringify(contentHash)}};const send=(kind,payload={})=>parent.postMessage({type:'dde.preview',kind,...meta,...payload},'*');document.addEventListener('pointerdown',(event)=>{const target=event.target.closest('[data-dde-pxg-key]');if(!target)return;const r=target.getBoundingClientRect();send('selection',{pxgKey:target.getAttribute('data-dde-pxg-key'),geometry:{x:r.x,y:r.y,width:r.width,height:r.height}})},true);addEventListener('DOMContentLoaded',()=>send('ready'),{once:true});})();</script>
</body></html>`;
  return {
    previewSessionId,
    candidateId,
    workspaceId: "00000000-0000-0000-0000-000000000030",
    screenKey: "screens/checkout",
    state: previewState,
    viewport: "1440",
    route: "/checkout",
    candidatePxgRevision: candidateState === "DIRTY" ? 5 : 4,
    sourceRevision: "fixture-source",
    documentPath: `.dde/preview/${previewSessionId}.html`,
    contentHash,
    stateDetail: `fixture ${previewState.toLowerCase()}`,
    content,
  };
}

function inspector(): InspectorDescriptor {
  return {
    candidateId,
    pxgKey,
    title: "Checkout hero",
    nodeKind: "region",
    candidateState,
    graphRevision: candidateState === "DIRTY" ? 5 : 4,
    stale: false,
    sourceMapping: "VERIFIED",
    sourcePath: "prototypes/screens/checkout.html",
    sourceSymbol: null,
    elementId: "hero-1",
    requiredVerification: ["silhouette", "visual_critique"],
    properties: [
      {
        propertyName: "spacing",
        value: spacing,
        valueType: "TOKEN",
        units: "px",
        semanticTokenClass: "spacing",
        legalValues: ["space2", "space4"],
        computedValue: spacing === "space2" ? "8px" : "16px",
        responsiveSemantics: "GLOBAL",
        sourcePath: "prototypes/screens/checkout.html",
        mutationOperation: "SET_PROPERTY",
        lockBehavior: "OPERATION_SENSITIVE",
        writable: true,
        lockReason: null,
        accessibilityEffect: "LAYOUT_REFLOW_RECHECK",
        validation: "TOKEN_REQUIRED",
        previewInvalidation: ["PREVIEW", "VISUAL_VERIFICATION"],
        requiredVerification: ["silhouette", "visual_critique"],
      },
    ],
  };
}

function commandPayload(command: DdeCommand): Record<string, unknown> {
  if (command.commandType === "frontend.preview.set_state") {
    if (command.parameters.state === "LIVE") previewState = "LIVE";
    return {
      previewSessionId,
      state: previewState,
      stateDetail: "browser loaded exact code-backed candidate source",
      contentHash: previewDocument().contentHash,
    };
  }
  if (command.commandType === "frontend.mutation.apply") {
    const rows = command.parameters.mutations as Array<Record<string, unknown>>;
    const payload = rows[0]?.payload as Record<string, unknown>;
    spacing = String(payload.value);
    candidateState = "DIRTY";
    previewState = "STALE";
    return {
      candidateState,
      fullyApplied: true,
      applied: [{ mutationId: "mutation-1", sequence: 1, operation: "SET_PROPERTY", targetKey: pxgKey }],
      refused: [],
      invalidatedPreviewSessionIds: [previewSessionId],
    };
  }
  if (command.commandType === "frontend.preview.start") {
    previewNumber += 1;
    previewSessionId = `preview-${previewNumber}`;
    previewState = "LOADING";
    candidateState = "READY";
    return {
      previewSessionId,
      state: "LOADING",
      stateDetail: "awaiting browser ready handshake",
      contentHash: previewDocument().contentHash,
    };
  }
  throw new Error(`unexpected command ${command.commandType}`);
}

const bridge = new TestHostBridge({
  reads: {
    "frontend.host.context": { missionId, projectId, projectName: "LogiFlow Marketplace" },
    "frontend.studio.snapshot": () => snapshot(),
    "frontend.preview.document": () => previewDocument(),
    "frontend.inspector.describe": () => inspector(),
  },
  commands: {
    "frontend.preview.set_state": commandPayload,
    "frontend.mutation.apply": commandPayload,
    "frontend.preview.start": commandPayload,
  },
});

Object.assign(window, { __ddeTestBridge: bridge });
const container = document.getElementById("dde-root");
if (container) {
  createRoot(container).render(
    <StrictMode>
      <DdeStudioApp bridge={bridge} buildVersion="dde-studio test" />
    </StrictMode>,
  );
}
