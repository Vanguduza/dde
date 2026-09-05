import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DdeStudioApp } from "../src/app/DdeStudioApp";
import type { DdeCommand, DdeReadQuery } from "../src/bridge/DdeHostBridge";
import { TestHostBridge } from "../src/bridge/TestHostBridge";
import type {
  FrontendChatActivity,
  FrontendChatAttachment,
  FrontendChatChanges,
  FrontendChatCheckpoint,
  FrontendChatContextBudget,
  FrontendChatConversation,
  FrontendChatModelOption,
  FrontendChatPlan,
  FrontendChatThread,
  FrontendChatTurn,
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
let previousSpacing = spacing;
let chatConversation: FrontendChatConversation | null = null;
let chatTurns: FrontendChatTurn[] = [];
let chatSequence = 0;
let chatTurnNumber = 0;
const historicConversationId = "00000000-0000-0000-0000-000000000051";
const chatPlanId = "00000000-0000-0000-0000-000000000060";
const chatPlanStepId = "00000000-0000-0000-0000-000000000061";
const attachmentId = "00000000-0000-0000-0000-000000000070";
const activityId = "00000000-0000-0000-0000-000000000090";
let chatAttachments: FrontendChatAttachment[] = [];
let chatPlans: FrontendChatPlan[] = [];
let chatActivities: FrontendChatActivity[] = [
  {
    activityId, conversationId: "conversation-1", sequence: 1, kind: "MODEL_INVOCATION",
    state: "RUNNING", label: "Awaiting approved provider invocation", detail: "approval required",
    refs: {}, cancellable: true, cancelReason: null, commandId: null, createdAt: new Date().toISOString(),
  },
];
let chatCheckpoints: FrontendChatCheckpoint[] = [];
let chatChanges: FrontendChatChanges = {
  workspaceId: candidateWorkspaceId ?? "00000000-0000-0000-0000-000000000030",
  baseRevision: "base-revision", workspaceRevision: "workspace-revision", diffHash: "diff-current",
  changes: [{
    path: "src/Checkout.tsx",
    diffText: "--- a/src/Checkout.tsx\n+++ b/src/Checkout.tsx\n@@ -1 +1 @@\n-space2\n+space4\n",
    diffHash: "diff-checkout", reviewDecision: "PENDING",
  }],
};
const chatModels: FrontendChatModelOption[] = [
  { optionId: "AUTO", label: "Auto", provider: "dde", profileId: null, modelId: null, status: "AVAILABLE", reason: "deterministic routing", requiresApproval: false, capabilities: ["deterministic"] },
  { optionId: "profile.claude_code_cli", label: "Claude Code subscription seat", provider: "anthropic-cli", profileId: "profile.claude_code_cli", modelId: null, status: "APPROVAL_REQUIRED", reason: "fresh human approval required", requiresApproval: true, capabilities: ["reasoning", "implementation"] },
];
const chatBudget = (): FrontendChatContextBudget => ({
  estimatedTokens: chatConversation?.pinnedContextRefs.length ? 512 : 128, budgetTokens: 24000,
  includedRefs: [...(chatConversation?.pinnedContextRefs ?? [])], omittedRefs: [], omissionReasons: {}, items: [],
});

function historicalConversation(): FrontendChatConversation {
  const now = new Date().toISOString();
  return {
    conversationId: historicConversationId, projectId, missionId, activeCandidateId: candidateId,
    designSessionId: null, screenKey: "screens/checkout", selectedNodeKeys: [], viewport: "1440",
    title: "Earlier checkout exploration", status: "OPEN", mode: "ASK", modelProfileId: null,
    activeWorkspaceId: candidateWorkspaceId, activePlanId: null, parentConversationId: null,
    branchedFromTurnId: null, pinnedContextRefs: [], createdBy: null, archivedAt: null, lockVersion: 1,
    createdAt: now, updatedAt: now,
  };
}

function conversationList(query = ""): FrontendChatConversation[] {
  const rows = [chatConversation, historicalConversation()].filter((item): item is FrontendChatConversation => item !== null);
  const needle = query.trim().toLowerCase();
  return needle ? rows.filter((item) => (item.title ?? "").toLowerCase().includes(needle)) : rows;
}

function chatThread(): FrontendChatThread {
  return { conversation: chatConversation, turns: [...chatTurns] };
}

function appendChatPair(
  text: string,
  options: {
    intent: string;
    outcome: "ROUTED" | "REFUSED" | "ANSWERED";
    message: string;
    refusalCode?: string | null;
    refusalDetail?: string | null;
    producedRefs?: string[];
  },
): { user: FrontendChatTurn; studio: FrontendChatTurn } {
  if (!chatConversation) throw new Error("chat conversation is not open");
  chatTurnNumber += 1;
  const createdAt = new Date().toISOString();
  const boundAttachmentIds = chatAttachments
    .filter((item) => item.turnId === `bound-turn-${chatTurnNumber}`)
    .map((item) => item.attachmentId);
  const resolvedContext = {
    target_keys: [...chatConversation.selectedNodeKeys],
    references: chatConversation.selectedNodeKeys.length ? { deictic: "selection" } : {},
  };
  const base = {
    conversationId: chatConversation.conversationId,
    intent: options.intent,
    outcome: options.outcome,
    refusalCode: options.refusalCode ?? null,
    refusalDetail: options.refusalDetail ?? null,
    resolvedContext,
    producedRefs: options.producedRefs ?? [],
    attachmentIds: boundAttachmentIds,
    planId: null,
    modelProfileId: chatConversation.modelProfileId,
    createdAt,
  } as const;
  const user: FrontendChatTurn = {
    ...base,
    turnId: `chat-user-${chatTurnNumber}`,
    sequence: ++chatSequence,
    role: "user",
    text,
  };
  const studio: FrontendChatTurn = {
    ...base,
    turnId: `chat-studio-${chatTurnNumber}`,
    sequence: ++chatSequence,
    role: "studio",
    text: options.message,
  };
  chatTurns = [...chatTurns, user, studio];
  chatConversation = { ...chatConversation, updatedAt: createdAt };
  return { user, studio };
}

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
  if (command.commandType === "frontend.chat.open") {
    if (!chatConversation) {
      const now = new Date().toISOString();
      chatConversation = {
        conversationId: "conversation-1",
        projectId,
        missionId,
        activeCandidateId: null,
        designSessionId: null,
        screenKey:
          typeof command.parameters.screen_key === "string"
            ? command.parameters.screen_key
            : null,
        selectedNodeKeys: [],
        viewport:
          typeof command.parameters.viewport === "string"
            ? command.parameters.viewport
            : "1440",
        title: typeof command.parameters.title === "string" ? command.parameters.title : null,
        status: "OPEN",
        mode: command.parameters.mode === "PLAN" || command.parameters.mode === "EXECUTE" ? command.parameters.mode : "ASK",
        modelProfileId: typeof command.parameters.model_profile_id === "string" ? command.parameters.model_profile_id : null,
        activeWorkspaceId: typeof command.parameters.active_workspace_id === "string" ? command.parameters.active_workspace_id : null,
        activePlanId: null,
        parentConversationId: null,
        branchedFromTurnId: null,
        pinnedContextRefs: [],
        createdBy: null,
        archivedAt: null,
        lockVersion: 1,
        createdAt: now,
        updatedAt: now,
      };
    }
    return {
      conversationId: chatConversation.conversationId,
      screenKey: chatConversation.screenKey,
      viewport: chatConversation.viewport,
    };
  }
  if (command.commandType === "frontend.chat.set_context") {
    if (!chatConversation) throw new Error("chat context set before open");
    const rawKeys = command.parameters.selected_node_keys;
    chatConversation = {
      ...chatConversation,
      selectedNodeKeys: Array.isArray(rawKeys)
        ? rawKeys.filter((item): item is string => typeof item === "string")
        : chatConversation.selectedNodeKeys,
      activeCandidateId: Object.prototype.hasOwnProperty.call(
        command.parameters,
        "active_candidate_id",
      )
        ? typeof command.parameters.active_candidate_id === "string"
          ? command.parameters.active_candidate_id
          : null
        : chatConversation.activeCandidateId,
      screenKey: Object.prototype.hasOwnProperty.call(command.parameters, "screen_key")
        ? typeof command.parameters.screen_key === "string"
          ? command.parameters.screen_key
          : null
        : chatConversation.screenKey,
      viewport:
        typeof command.parameters.viewport === "string"
          ? command.parameters.viewport
          : chatConversation.viewport,
      updatedAt: new Date().toISOString(),
    };
    return {
      conversationId: chatConversation.conversationId,
      selectedNodeKeys: [...chatConversation.selectedNodeKeys],
      activeCandidateId: chatConversation.activeCandidateId,
      screenKey: chatConversation.screenKey,
      viewport: chatConversation.viewport,
    };
  }
  if (command.commandType === "frontend.chat.set_mode") {
    if (!chatConversation) throw new Error("chat mode set before open");
    const mode = command.parameters.mode;
    if (mode !== "ASK" && mode !== "PLAN" && mode !== "EXECUTE") throw new Error("invalid mode");
    chatConversation = { ...chatConversation, mode, updatedAt: new Date().toISOString() };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.set_model") {
    if (!chatConversation) throw new Error("chat model set before open");
    chatConversation = {
      ...chatConversation,
      modelProfileId: typeof command.parameters.model_profile_id === "string" ? command.parameters.model_profile_id : null,
      updatedAt: new Date().toISOString(),
    };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.rename") {
    if (!chatConversation) throw new Error("chat rename before open");
    chatConversation = { ...chatConversation, title: String(command.parameters.title ?? ""), updatedAt: new Date().toISOString() };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.set_mode") {
    if (!chatConversation) throw new Error("mode set before open");
    const mode = String(command.parameters.mode ?? "ASK") as FrontendChatConversation["mode"];
    chatConversation = { ...chatConversation, mode, lockVersion: chatConversation.lockVersion + 1, updatedAt: new Date().toISOString() };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.set_model") {
    if (!chatConversation) throw new Error("model set before open");
    const raw = command.parameters.model_profile_id;
    chatConversation = { ...chatConversation, modelProfileId: typeof raw === "string" ? raw : null, lockVersion: chatConversation.lockVersion + 1, updatedAt: new Date().toISOString() };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.rename") {
    if (!chatConversation) throw new Error("rename before open");
    chatConversation = { ...chatConversation, title: String(command.parameters.title ?? "Untitled"), lockVersion: chatConversation.lockVersion + 1, updatedAt: new Date().toISOString() };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.archive") {
    if (!chatConversation) throw new Error("archive before open");
    chatConversation = { ...chatConversation, status: command.parameters.archived === false ? "OPEN" : "ARCHIVED", archivedAt: command.parameters.archived === false ? null : new Date().toISOString(), lockVersion: chatConversation.lockVersion + 1, updatedAt: new Date().toISOString() };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.branch") {
    if (!chatConversation) throw new Error("branch before open");
    const now = new Date().toISOString();
    chatConversation = { ...chatConversation, conversationId: `conversation-branch-${chatTurnNumber + 1}`, title: `${chatConversation.title ?? "Chat"} — branch`, parentConversationId: chatConversation.conversationId, branchedFromTurnId: typeof command.parameters.from_turn_id === "string" ? command.parameters.from_turn_id : null, activePlanId: null, lockVersion: 1, createdAt: now, updatedAt: now };
    chatTurns = []; chatSequence = 0;
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.pin_context") {
    if (!chatConversation) throw new Error("pin before open");
    const ref = String(command.parameters.context_ref ?? "");
    const pinned = command.parameters.pinned !== false;
    const next = pinned ? [...new Set([...chatConversation.pinnedContextRefs, ref])] : chatConversation.pinnedContextRefs.filter((item) => item !== ref);
    chatConversation = { ...chatConversation, pinnedContextRefs: next, lockVersion: chatConversation.lockVersion + 1, updatedAt: new Date().toISOString() };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.attachment.reserve") {
    if (!chatConversation) throw new Error("attachment before open");
    const attachment: FrontendChatAttachment = { attachmentId, conversationId: chatConversation.conversationId, turnId: null, sourceKind: "UPLOAD", filename: String(command.parameters.filename ?? "upload.txt"), mediaType: String(command.parameters.media_type ?? "text/plain"), sizeBytes: Number(command.parameters.size_bytes ?? 12), contentHash: null, workspacePath: null, extractionState: "PENDING", status: "RESERVED", createdAt: new Date().toISOString() };
    chatAttachments = [attachment];
    return { attachment };
  }
  if (command.commandType === "frontend.chat.attachment.remove") {
    chatAttachments = chatAttachments.map((item) => item.attachmentId === command.parameters.attachment_id ? { ...item, status: "REMOVED" } : item);
    return { attachment: chatAttachments[0] };
  }
  if (command.commandType === "frontend.chat.checkpoint.create") {
    if (!chatConversation) throw new Error("checkpoint before open");
    const item: FrontendChatCheckpoint = { checkpointId: `checkpoint-${chatCheckpoints.length + 1}`, conversationId: chatConversation.conversationId, turnSequence: chatSequence, mode: chatConversation.mode, modelProfileId: chatConversation.modelProfileId, planId: chatConversation.activePlanId, workspaceId: chatConversation.activeWorkspaceId, pinnedContextRefs: [...chatConversation.pinnedContextRefs], attachmentRefs: chatAttachments.filter((a) => a.status === "ACTIVE").map((a) => a.attachmentId), workspaceRevision: chatChanges.workspaceRevision, diffHash: chatChanges.diffHash, contextHash: `context-${chatCheckpoints.length + 1}`, note: typeof command.parameters.note === "string" ? command.parameters.note : null, createdAt: new Date().toISOString() };
    chatCheckpoints = [item, ...chatCheckpoints];
    return { checkpoint: item };
  }
  if (command.commandType === "frontend.chat.checkpoint.restore") {
    const item = chatCheckpoints.find((cp) => cp.checkpointId === command.parameters.checkpoint_id);
    if (item && chatConversation) chatConversation = { ...chatConversation, mode: item.mode, modelProfileId: item.modelProfileId, pinnedContextRefs: [...item.pinnedContextRefs], activePlanId: item.planId, activeWorkspaceId: item.workspaceId, lockVersion: chatConversation.lockVersion + 1 };
    return { conversation: chatConversation };
  }
  if (command.commandType === "frontend.chat.plan.approve") {
    chatPlans = chatPlans.map((plan) => plan.planId === command.parameters.plan_id ? { ...plan, state: "APPROVED", approvedBy: "test-principal", approvedAt: new Date().toISOString(), lockVersion: plan.lockVersion + 1 } : plan);
    return { plan: chatPlans[0] };
  }
  if (command.commandType === "frontend.chat.plan.prepare_step") {
    const plan = chatPlans[0]; if (!plan) throw new Error("no plan");
    const step = plan.steps[0]!;
    chatPlans = [{ ...plan, state: "EXECUTING", activeStepId: step.stepId, lockVersion: plan.lockVersion + 1, steps: [{ ...step, state: "READY", attempt: step.attempt + 1, idempotencyKey: "plan-attempt-1", expectedRequestHash: "request-hash-1" }] }];
    return { planId: plan.planId, stepId: step.stepId, commandType: step.commandType, targetType: "mission", targetId: missionId, parameters: step.parameters, idempotencyKey: "plan-attempt-1", expectedRequestHash: "request-hash-1" };
  }
  if (command.commandType === "frontend.chat.plan.record_step") {
    const plan = chatPlans[0]; if (!plan) throw new Error("no plan");
    const step = plan.steps[0]!;
    chatPlans = [{ ...plan, state: "COMPLETED", activeStepId: null, lockVersion: plan.lockVersion + 1, steps: [{ ...step, state: "COMPLETED", commandId: String(command.parameters.command_id), resultSummary: "completed" }] }];
    return { plan: chatPlans[0] };
  }
  if (command.commandType === "frontend.chat.plan.retry_step") {
    const plan = chatPlans[0]; if (!plan) throw new Error("no plan"); const step = plan.steps[0]!;
    chatPlans = [{ ...plan, state: "APPROVED", activeStepId: null, steps: [{ ...step, state: "PENDING", commandId: null, errorCode: null, errorDetail: null }] }]; return { plan: chatPlans[0] };
  }
  if (command.commandType === "frontend.chat.plan.cancel") { const plan=chatPlans[0]; if(plan) chatPlans=[{...plan,state:"CANCELLED",lockVersion:plan.lockVersion+1}]; return {plan:chatPlans[0]}; }
  if (command.commandType === "frontend.chat.activity.cancel") { chatActivities=chatActivities.map((item)=>item.activityId===command.parameters.activity_id?{...item,state:"CANCELLED",cancellable:false,cancelReason:String(command.parameters.reason??"cancelled")}:item); return {activity:chatActivities[0]}; }
  if (command.commandType === "frontend.chat.workspace.accept_file") { chatChanges={...chatChanges,changes:chatChanges.changes.map((item)=>item.path===command.parameters.path?{...item,reviewDecision:"ACCEPTED"}:item)}; return {reviewDecision:"ACCEPTED"}; }
  if (command.commandType === "frontend.chat.workspace.revert_file") { chatChanges={...chatChanges,diffHash:"diff-empty",changes:[]}; return { ...chatChanges }; }
  if (command.commandType === "frontend.chat.workspace.revert_all") { chatChanges={...chatChanges,diffHash:"diff-empty",changes:[]}; return { ...chatChanges }; }
  if (command.commandType === "frontend.chat.workspace.apply_patch") { chatChanges={...chatChanges,diffHash:"diff-patched",changes:[...chatChanges.changes,{path:"src/Patched.tsx",diffText:String(command.parameters.patch_text??""),diffHash:"diff-patched-file",reviewDecision:"PENDING"}]}; return { ...chatChanges }; }

  if (command.commandType === "frontend.chat.send") {
    if (!chatConversation) throw new Error("chat send before open");
    const text = String(command.parameters.text ?? "").trim();
    const rawAttachmentIds = command.parameters.attachment_ids;
    if (Array.isArray(rawAttachmentIds)) {
      const ids = new Set(rawAttachmentIds.filter((item): item is string => typeof item === "string"));
      chatAttachments = chatAttachments.map((item) => ids.has(item.attachmentId) ? { ...item, turnId: `bound-turn-${chatTurnNumber + 1}` } : item);
    }
    const lower = text.toLowerCase();
    if (lower.startsWith("/design")) {
      if (chatConversation.mode !== "EXECUTE") {
        const refusalDetail = chatConversation.mode === "ASK" ? "Ask mode is read-only. Switch to Execute for /design." : "Plan mode cannot invoke /design; it can only prepare governed plans.";
        const pair = appendChatPair(text, { intent: "DESIGN_DIVERGENT", outcome: "REFUSED", message: refusalDetail, refusalCode: "MODE_READ_ONLY", refusalDetail });
        return { turnId: pair.user.turnId, replyTurnId: pair.studio.turnId, sequence: pair.user.sequence, intent: "DESIGN_DIVERGENT", outcome: "REFUSED", refusalCode: "MODE_READ_ONLY", refusalDetail, resolvedContext: pair.user.resolvedContext, producedRefs: [], message: refusalDetail };
      }
      const refusalDetail = "no certified design provider transport";
      const pair = appendChatPair(text, {
        intent: "DESIGN_DIVERGENT",
        outcome: "REFUSED",
        message: refusalDetail,
        refusalCode: "CAPABILITY_UNAVAILABLE",
        refusalDetail,
      });
      return {
        turnId: pair.user.turnId,
        replyTurnId: pair.studio.turnId,
        sequence: pair.user.sequence,
        intent: "DESIGN_DIVERGENT",
        outcome: "REFUSED",
        refusalCode: "CAPABILITY_UNAVAILABLE",
        refusalDetail,
        resolvedContext: pair.user.resolvedContext,
        producedRefs: [],
        message: refusalDetail,
      };
    }
    if (lower === "undo" || lower.includes("revert")) {
      if (chatConversation.mode !== "EXECUTE") {
        const detail = chatConversation.mode === "ASK" ? "Ask mode is read-only. Switch to Execute to undo." : "Plan mode prepares changes and does not execute undo.";
        const pair = appendChatPair(text, { intent: "UNDO_REVERT", outcome: "REFUSED", message: detail, refusalCode: "MODE_READ_ONLY", refusalDetail: detail });
        return { turnId: pair.user.turnId, replyTurnId: pair.studio.turnId, sequence: pair.user.sequence, intent: "UNDO_REVERT", outcome: "REFUSED", refusalCode: "MODE_READ_ONLY", refusalDetail: detail, resolvedContext: pair.user.resolvedContext, producedRefs: [], message: detail };
      }
      if (!chatConversation.activeCandidateId) {
        const detail = "undo applies to a candidate; none is active";
        const pair = appendChatPair(text, {
          intent: "UNDO_REVERT",
          outcome: "REFUSED",
          message: detail,
          refusalCode: "NO_ACTIVE_CANDIDATE",
          refusalDetail: detail,
        });
        return {
          turnId: pair.user.turnId,
          replyTurnId: pair.studio.turnId,
          sequence: pair.user.sequence,
          intent: "UNDO_REVERT",
          outcome: "REFUSED",
          refusalCode: "NO_ACTIVE_CANDIDATE",
          refusalDetail: detail,
          resolvedContext: pair.user.resolvedContext,
          producedRefs: [],
          message: detail,
        };
      }
      const next = previousSpacing;
      previousSpacing = spacing;
      spacing = next;
      candidateState = "DIRTY";
      previewState = "STALE";
      verificationRequestState = "SUPERSEDED";
      verificationRunId = null;
      verificationRunStatus = null;
      const pair = appendChatPair(text, {
        intent: "UNDO_REVERT",
        outcome: "ROUTED",
        message: "reverted mutation 1",
        producedRefs: ["chat-revert-mutation"],
      });
      return {
        turnId: pair.user.turnId,
        replyTurnId: pair.studio.turnId,
        sequence: pair.user.sequence,
        intent: "UNDO_REVERT",
        outcome: "ROUTED",
        refusalCode: null,
        refusalDetail: null,
        resolvedContext: pair.user.resolvedContext,
        producedRefs: ["chat-revert-mutation"],
        message: "reverted mutation 1",
      };
    }
    const match = lower.match(/set\s+(?:the\s+)?spacing\s+to\s+(space[0-9]+)/);
    if (match) {
      if (!chatConversation.selectedNodeKeys.length) {
        const detail =
          "nothing is selected and the message names no element, so there is no unambiguous target for this instruction";
        const pair = appendChatPair(text, {
          intent: "MUTATE_DETERMINISTIC",
          outcome: "REFUSED",
          message: detail,
          refusalCode: "AMBIGUOUS_REFERENCE",
          refusalDetail: detail,
        });
        return {
          turnId: pair.user.turnId,
          replyTurnId: pair.studio.turnId,
          sequence: pair.user.sequence,
          intent: "MUTATE_DETERMINISTIC",
          outcome: "REFUSED",
          refusalCode: "AMBIGUOUS_REFERENCE",
          refusalDetail: detail,
          resolvedContext: pair.user.resolvedContext,
          producedRefs: [],
          message: detail,
        };
      }
      if (chatConversation.mode === "ASK") {
        const detail = "Ask mode is read-only. Switch to Plan to prepare this change or Execute to run it.";
        const pair = appendChatPair(text, { intent: "MUTATE_DETERMINISTIC", outcome: "REFUSED", message: detail, refusalCode: "MODE_READ_ONLY", refusalDetail: detail });
        return { turnId: pair.user.turnId, replyTurnId: pair.studio.turnId, sequence: pair.user.sequence, intent: "MUTATE_DETERMINISTIC", outcome: "REFUSED", refusalCode: "MODE_READ_ONLY", refusalDetail: detail, resolvedContext: pair.user.resolvedContext, producedRefs: [], message: detail };
      }
      if (chatConversation.mode === "PLAN") {
        const now = new Date().toISOString();
        const plan: FrontendChatPlan = {
          planId: chatPlanId, conversationId: chatConversation.conversationId, title: "Change spacing", objective: text, state: "READY", approvalRequired: true, approvedBy: null, approvedAt: null,
          steps: [{ stepId: chatPlanStepId, sequence: 1, title: "Set selected spacing", description: `Set spacing to ${match[1]!}`, state: "PENDING", attempt: 0, commandType: "frontend.mutation.apply", targetType: "mission", targetId: missionId, parameters: { candidate_id: candidateId, mutations: [{ operation: "SET_PROPERTY", target_key: chatConversation.selectedNodeKeys[0], origin: "CHAT", payload: { property: "spacing", value: match[1]! } }] }, dependsOn: [], evidenceRefs: [], commandId: null, resultSummary: null, errorCode: null, errorDetail: null, idempotencyKey: null, expectedRequestHash: null }],
          activeStepId: null, workspaceId: chatConversation.activeWorkspaceId, taskGraphId: null, lockVersion: 1, createdAt: now, updatedAt: now,
        };
        chatPlans = [plan];
        chatConversation = { ...chatConversation, activePlanId: plan.planId, lockVersion: chatConversation.lockVersion + 1, updatedAt: now };
        const pair = appendChatPair(text, { intent: "MUTATE_DETERMINISTIC", outcome: "ROUTED", message: "created governed plan with 1 step", producedRefs: [`plan:${plan.planId}`] });
        return { turnId: pair.user.turnId, replyTurnId: pair.studio.turnId, sequence: pair.user.sequence, intent: "MUTATE_DETERMINISTIC", outcome: "ROUTED", refusalCode: null, refusalDetail: null, resolvedContext: pair.user.resolvedContext, producedRefs: [`plan:${plan.planId}`], message: "created governed plan with 1 step" };
      }
      previousSpacing = spacing;
      spacing = match[1]!;
      candidateState = "DIRTY";
      previewState = "STALE";
      verificationRequestState = "SUPERSEDED";
      verificationRunId = null;
      verificationRunStatus = null;
      const pair = appendChatPair(text, {
        intent: "MUTATE_DETERMINISTIC",
        outcome: "ROUTED",
        message: "applied 1 change(s)",
        producedRefs: ["chat-mutation-1"],
      });
      return {
        turnId: pair.user.turnId,
        replyTurnId: pair.studio.turnId,
        sequence: pair.user.sequence,
        intent: "MUTATE_DETERMINISTIC",
        outcome: "ROUTED",
        refusalCode: null,
        refusalDetail: null,
        resolvedContext: pair.user.resolvedContext,
        producedRefs: ["chat-mutation-1"],
        message: "applied 1 change(s)",
      };
    }
    if (lower.includes("coverage") || lower.includes("uncovered")) {
      const message =
        "Coverage PARTIAL: percentage unavailable; blocking findings=0; dimensions: screen=ASSESSED";
      const pair = appendChatPair(text, {
        intent: "COVERAGE_QUERY",
        outcome: "ANSWERED",
        message,
      });
      return {
        turnId: pair.user.turnId,
        replyTurnId: pair.studio.turnId,
        sequence: pair.user.sequence,
        intent: "COVERAGE_QUERY",
        outcome: "ANSWERED",
        refusalCode: null,
        refusalDetail: null,
        resolvedContext: pair.user.resolvedContext,
        producedRefs: [],
        message,
      };
    }
    if (lower.includes("qa") || lower.includes("finding") || lower.includes("issue")) {
      const message = `Candidate QA: request=${verificationRequestState ?? "NOT_REQUESTED"}; run=${verificationRunStatus ?? "NOT_EVALUATED"}; evidence=${verificationRunStatus === "PASSED" ? 2 : 0}`;
      const pair = appendChatPair(text, {
        intent: "QA_QUERY",
        outcome: "ANSWERED",
        message,
      });
      return {
        turnId: pair.user.turnId,
        replyTurnId: pair.studio.turnId,
        sequence: pair.user.sequence,
        intent: "QA_QUERY",
        outcome: "ANSWERED",
        refusalCode: null,
        refusalDetail: null,
        resolvedContext: pair.user.resolvedContext,
        producedRefs: [],
        message,
      };
    }
    const detail = "the studio could not tell what this instruction should do";
    const pair = appendChatPair(text, {
      intent: "UNKNOWN",
      outcome: "REFUSED",
      message: detail,
      refusalCode: "INTENT_AMBIGUOUS",
      refusalDetail: detail,
    });
    return {
      turnId: pair.user.turnId,
      replyTurnId: pair.studio.turnId,
      sequence: pair.user.sequence,
      intent: "UNKNOWN",
      outcome: "REFUSED",
      refusalCode: "INTENT_AMBIGUOUS",
      refusalDetail: detail,
      resolvedContext: pair.user.resolvedContext,
      producedRefs: [],
      message: detail,
    };
  }
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
  capabilities: { canPickLocalFile: true },
  pickLocalFile: () => ({ token: "pick-token-1", filename: "requirements.md", mediaType: "text/markdown", sizeBytes: 24 }),
  uploadPickedFile: (request) => {
    chatAttachments = chatAttachments.map((item) => item.attachmentId === request.attachmentId ? { ...item, status: "ACTIVE", extractionState: "EXTRACTED", contentHash: "attachment-hash" } : item);
    return { attachment: chatAttachments.find((item) => item.attachmentId === request.attachmentId) };
  },
  reads: {
    "frontend.host.context": { missionId, projectId, projectName: "LogiFlow Marketplace" },
    "frontend.studio.snapshot": () => snapshot(),
    "frontend.chat.thread": () => chatThread(),
    "frontend.chat.thread.by_id": (query: DdeReadQuery) => {
      const id = String(query.parameters?.conversationId ?? "");
      return id === historicConversationId ? { conversation: historicalConversation(), turns: [] } : chatThread();
    },
    "frontend.chat.conversations": (query: DdeReadQuery) => ({ conversations: conversationList(String(query.parameters?.query ?? "")) }),
    "frontend.chat.attachments": () => ({ attachments: [...chatAttachments] }),
    "frontend.chat.plans": () => ({ plans: [...chatPlans] }),
    "frontend.chat.activities": () => ({ activities: [...chatActivities] }),
    "frontend.chat.checkpoints": () => ({ checkpoints: [...chatCheckpoints] }),
    "frontend.chat.models": { models: chatModels },
    "frontend.chat.context": () => chatBudget(),
    "frontend.chat.changes": () => ({ ...chatChanges }),
    "frontend.preview.document": () => previewDocument(),
    "frontend.inspector.describe": () => inspector(),
  },
  commands: {
    "frontend.chat.open": commandPayload,
    "frontend.chat.set_context": commandPayload,
    "frontend.chat.set_mode": commandPayload,
    "frontend.chat.set_model": commandPayload,
    "frontend.chat.rename": commandPayload,
    "frontend.chat.archive": commandPayload,
    "frontend.chat.branch": commandPayload,
    "frontend.chat.pin_context": commandPayload,
    "frontend.chat.attachment.reserve": commandPayload,
    "frontend.chat.attachment.remove": commandPayload,
    "frontend.chat.plan.approve": commandPayload,
    "frontend.chat.plan.prepare_step": commandPayload,
    "frontend.chat.plan.record_step": commandPayload,
    "frontend.chat.plan.retry_step": commandPayload,
    "frontend.chat.plan.cancel": commandPayload,
    "frontend.chat.activity.cancel": commandPayload,
    "frontend.chat.checkpoint.create": commandPayload,
    "frontend.chat.checkpoint.restore": commandPayload,
    "frontend.chat.workspace.accept_file": commandPayload,
    "frontend.chat.workspace.revert_file": commandPayload,
    "frontend.chat.workspace.revert_all": commandPayload,
    "frontend.chat.workspace.apply_patch": commandPayload,
    "frontend.chat.send": commandPayload,
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
