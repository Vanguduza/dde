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
const freshCandidate = new URLSearchParams(window.location.search).get("fresh") === "1";
const sourceA = "00000000-0000-0000-0000-000000000041";
const sourceB = "00000000-0000-0000-0000-000000000042";
let candidateWorkspaceId: string | null = freshCandidate
  ? null
  : "00000000-0000-0000-0000-000000000030";
let previewNumber = 1;
let previewSessionId = `preview-${previewNumber}`;
let previewState: "LOADING" | "LIVE" | "STALE" = "LOADING";
let candidateState = freshCandidate ? "GENERATED" : "READY";
let spacing = "space2";
let verificationRequestState: "PENDING" | "PASSED" | "FAILED" | "BLOCKED" | "SUPERSEDED" | null =
  freshCandidate ? null : "PENDING";
let verificationRequestNumber = 1;
let verificationRunId: string | null = null;
let verificationRunStatus: string | null = null;

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
    sourceWorkspaces: freshCandidate
      ? {
          options: [
            {
              workspaceId: sourceA,
              currentRevision: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
              missionId,
              purpose: "worker_source",
              createdAt: new Date().toISOString(),
            },
            {
              workspaceId: sourceB,
              currentRevision: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
              missionId,
              purpose: "worker_source",
              createdAt: new Date().toISOString(),
            },
          ],
          selectionState: "AMBIGUOUS",
          autoSelectedWorkspaceId: null,
          availability: "AVAILABLE",
          reason: "Multiple READY source workspaces exist; explicit selection is required.",
        }
      : {
          options: [],
          selectionState: "EMPTY",
          autoSelectedWorkspaceId: null,
          availability: "EMPTY",
          reason: "No source selection is needed after candidate materialization.",
        },
    candidates: {
      count: { value: 1, availability: "AVAILABLE" },
      cards: [
        {
          candidateId,
          title: "Checkout spacing refinement",
          state: candidateState,
          origin: "DIRECT_EDIT",
          workspaceId: candidateWorkspaceId,
          basePxgRevision: 4,
          currentPxgRevision: 4,
          stale: false,
          scopeKeys: ["screens/checkout"],
          previewSessionId: freshCandidate && !candidateWorkspaceId ? null : previewSessionId,
          previewState: freshCandidate && !candidateWorkspaceId ? null : previewState,
          previewStateDetail:
            freshCandidate && !candidateWorkspaceId
              ? null
              : `fixture ${previewState.toLowerCase()}`,
          verificationRequestId:
            verificationRequestState === null
              ? null
              : `verification-request-${verificationRequestNumber}`,
          verificationRequestState,
          verificationRequestReason:
            verificationRequestState === "SUPERSEDED"
              ? "candidate changed; DDE-068 rerun required"
              : null,
          verificationRequiredKinds:
            verificationRequestState === null
              ? []
              : ["silhouette", "visual_critique"],
          verificationRunId,
          verificationRunStatus,
          verificationConfidence: verificationRunStatus === "PASSED" ? 1 : null,
          verificationChecks:
            verificationRunStatus === "PASSED"
              ? [
                  {
                    checkRef: "screens/checkout:silhouette",
                    kind: "silhouette",
                    status: "PASSED",
                    detail: null,
                  },
                  {
                    checkRef: "screens/checkout:visual_critique",
                    kind: "visual_critique",
                    status: "PASSED",
                    detail: null,
                  },
                ]
              : [],
          verificationEvidenceRefs:
            verificationRunStatus === "PASSED" ? ["evidence-1", "evidence-2"] : [],
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
    workspaceId: candidateWorkspaceId ?? "00000000-0000-0000-0000-000000000030",
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
    if (command.parameters.state === "LIVE") {
      previewState = "LIVE";
      verificationRequestNumber += 1;
      verificationRequestState = "PENDING";
    }
    return {
      previewSessionId,
      state: previewState,
      stateDetail: "browser loaded exact code-backed candidate source",
      contentHash: previewDocument().contentHash,
      verificationRequestId: `verification-request-${verificationRequestNumber}`,
      verificationRequestState,
      verificationRequiredKinds: ["silhouette", "visual_critique"],
    };
  }
  if (command.commandType === "frontend.verification.run") {
    const expected = `verification-request-${verificationRequestNumber}`;
    if (command.parameters.verification_request_id !== expected) {
      throw new Error("verification command targeted a stale request");
    }
    verificationRequestState = "PASSED";
    candidateState = "VERIFIED";
    verificationRunId = `verification-run-${verificationRequestNumber}`;
    verificationRunStatus = "PASSED";
    return {
      verificationRequestId: expected,
      requestState: "PASSED",
      requestReason: "DDE-068 verification passed",
      verificationRunId,
      verificationRunStatus: "PASSED",
      candidateId,
      candidateState,
    };
  }
  if (command.commandType === "frontend.mutation.apply") {
    const rows = command.parameters.mutations as Array<Record<string, unknown>>;
    const payload = rows[0]?.payload as Record<string, unknown>;
    spacing = String(payload.value);
    candidateState = "DIRTY";
    previewState = "STALE";
    verificationRequestState = "SUPERSEDED";
    verificationRunId = null;
    verificationRunStatus = null;
    return {
      candidateState,
      fullyApplied: true,
      applied: [{ mutationId: "mutation-1", sequence: 1, operation: "SET_PROPERTY", targetKey: pxgKey }],
      refused: [],
      invalidatedPreviewSessionIds: [previewSessionId],
      supersededVerificationRequestIds: [
        `verification-request-${verificationRequestNumber}`,
      ],
    };
  }
  if (command.commandType === "frontend.preview.start") {
    if (freshCandidate && !candidateWorkspaceId) {
      const sourceWorkspaceId = command.parameters.source_workspace_id;
      if (sourceWorkspaceId !== sourceA && sourceWorkspaceId !== sourceB) {
        throw new Error(
          "fresh candidate requires an explicitly selected source workspace",
        );
      }
      candidateWorkspaceId = "00000000-0000-0000-0000-000000000030";
    }
    previewNumber += 1;
    previewSessionId = `preview-${previewNumber}`;
    previewState = "LOADING";
    candidateState = "READY";
    verificationRequestState = null;
    verificationRunId = null;
    verificationRunStatus = null;
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
    "frontend.verification.run": commandPayload,
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
