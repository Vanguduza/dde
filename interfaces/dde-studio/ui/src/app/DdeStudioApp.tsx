import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CommandAcceptance,
  DdeHostBridge,
  DdeCommand,
} from "../bridge/DdeHostBridge";
import {
  FrontendStudioWorkspace,
  type PreviewRuntimeSignal,
  type PreviewSelection,
} from "../frontend-studio/FrontendStudioWorkspace";
import { DdeChatComposer } from "../chat/DdeChatComposer";
import { InspectorPanel } from "../frontend-studio/InspectorPanel";
import { AppRail, type RailModule } from "../shell/AppRail";
import { ContextSidebar } from "../shell/ContextSidebar";
import { DdeShell } from "../shell/DdeShell";
import { GlobalTopBar } from "../shell/GlobalTopBar";
import { StatusBar } from "../shell/StatusBar";
import type {
  FrontendChatActivity,
  FrontendChatAttachment,
  FrontendChatChange,
  FrontendChatChanges,
  FrontendChatCheckpoint,
  FrontendChatContextBudget,
  FrontendChatConversation,
  FrontendChatMode,
  FrontendChatModelOption,
  FrontendChatPlan,
  FrontendChatPlanStep,
  FrontendChatThread,
  FrontendHostContext,
  FrontendStudioSnapshot,
  InspectorDescriptor,
  PreviewDocument,
  StudioMode,
} from "../state/projections";

const MODULES: readonly RailModule[] = [
  { id: "frontend", label: "Frontend Studio", glyph: "◧", available: true },
  { id: "projects", label: "Projects", glyph: "▤", available: false },
  { id: "models", label: "Models", glyph: "◈", available: false },
  { id: "orchestration", label: "Orchestration", glyph: "⌘", available: false },
  { id: "knowledge", label: "Knowledge", glyph: "◎", available: false },
];

export interface DdeStudioAppProps {
  readonly bridge: DdeHostBridge;
  readonly projectName?: string | null;
  readonly buildVersion?: string | null;
}

export function DdeStudioApp({
  bridge,
  projectName = null,
  buildVersion = null,
}: DdeStudioAppProps) {
  const [hostContext, setHostContext] = useState<FrontendHostContext | null>(null);
  const [snapshot, setSnapshot] = useState<FrontendStudioSnapshot | null>(null);
  const [mode, setMode] = useState<StudioMode>("design");
  const [group, setGroup] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [viewport, setViewport] = useState("1440");
  const [screenKey, setScreenKey] = useState<string | null>(null);
  const [activeCandidateId, setActiveCandidateId] = useState<string | null>(null);
  const [sourceWorkspaceId, setSourceWorkspaceId] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewDocument | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewBrowserReady, setPreviewBrowserReady] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selection, setSelection] = useState<PreviewSelection | null>(null);
  const [descriptor, setDescriptor] = useState<InspectorDescriptor | null>(null);
  const [inspectorLoading, setInspectorLoading] = useState(false);
  const [inspectorError, setInspectorError] = useState<string | null>(null);
  const [applyingProperty, setApplyingProperty] = useState<string | null>(null);
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const verificationStarted = useRef<Set<string>>(new Set());
  const [chatThread, setChatThread] = useState<FrontendChatThread | null>(null);
  const [chatLoading, setChatLoading] = useState(true);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatIncludeSelection, setChatIncludeSelection] = useState(true);
  const [chatConversations, setChatConversations] = useState<readonly FrontendChatConversation[]>([]);
  const [chatAttachments, setChatAttachments] = useState<readonly FrontendChatAttachment[]>([]);
  const [pendingAttachmentIds, setPendingAttachmentIds] = useState<readonly string[]>([]);
  const [chatPlans, setChatPlans] = useState<readonly FrontendChatPlan[]>([]);
  const [chatActivities, setChatActivities] = useState<readonly FrontendChatActivity[]>([]);
  const [chatCheckpoints, setChatCheckpoints] = useState<readonly FrontendChatCheckpoint[]>([]);
  const [chatChanges, setChatChanges] = useState<FrontendChatChanges | null>(null);
  const [chatModels, setChatModels] = useState<readonly FrontendChatModelOption[]>([]);
  const [chatContextBudget, setChatContextBudget] = useState<FrontendChatContextBudget | null>(null);
  const [canPickLocalFile, setCanPickLocalFile] = useState(false);

  const refreshSnapshot = useCallback(async () => {
    const value = await bridge.requestRead<FrontendStudioSnapshot>({
      resource: "frontend.studio.snapshot",
    });
    setSnapshot(value);
    return value;
  }, [bridge]);

  const refreshChat = useCallback(async () => {
    const value = await bridge.requestRead<FrontendChatThread>({
      resource: "frontend.chat.thread",
    });
    setChatThread(value);
    setChatError(null);
    return value;
  }, [bridge]);

  const refreshChatResources = useCallback(
    async (conversationId?: string | null) => {
      const target = conversationId ?? chatThread?.conversation?.conversationId ?? null;
      const conversationRead = await bridge.requestRead<{
        conversations: readonly FrontendChatConversation[];
      }>({ resource: "frontend.chat.conversations" });
      setChatConversations(conversationRead.conversations ?? []);
      const modelRead = await bridge.requestRead<{ models: readonly FrontendChatModelOption[] }>({
        resource: "frontend.chat.models",
      });
      setChatModels(modelRead.models ?? []);
      if (!target) {
        setChatAttachments([]);
        setChatPlans([]);
        setChatActivities([]);
        setChatCheckpoints([]);
        setChatChanges(null);
        setChatContextBudget(null);
        return;
      }
      const [attachments, plans, activities, checkpoints, context] = await Promise.all([
        bridge.requestRead<{ attachments: readonly FrontendChatAttachment[] }>({
          resource: "frontend.chat.attachments", parameters: { conversationId: target },
        }),
        bridge.requestRead<{ plans: readonly FrontendChatPlan[] }>({
          resource: "frontend.chat.plans", parameters: { conversationId: target },
        }),
        bridge.requestRead<{ activities: readonly FrontendChatActivity[] }>({
          resource: "frontend.chat.activities", parameters: { conversationId: target },
        }),
        bridge.requestRead<{ checkpoints: readonly FrontendChatCheckpoint[] }>({
          resource: "frontend.chat.checkpoints", parameters: { conversationId: target },
        }),
        bridge.requestRead<FrontendChatContextBudget>({
          resource: "frontend.chat.context",
          parameters: {
            conversationId: target,
            refs: chatThread?.conversation?.pinnedContextRefs ?? [],
            budgetTokens: 24_000,
          },
        }),
      ]);
      setChatAttachments(attachments.attachments ?? []);
      setChatPlans(plans.plans ?? []);
      setChatActivities(activities.activities ?? []);
      setChatCheckpoints(checkpoints.checkpoints ?? []);
      setChatContextBudget(context);
      try {
        const changes = await bridge.requestRead<FrontendChatChanges>({
          resource: "frontend.chat.changes", parameters: { conversationId: target },
        });
        setChatChanges(changes);
      } catch {
        setChatChanges(null);
      }
    },
    [bridge, chatThread?.conversation?.conversationId, chatThread?.conversation?.pinnedContextRefs],
  );

  useEffect(() => {
    let cancelled = false;
    bridge.getCapabilities().then((value) => {
      if (!cancelled) setCanPickLocalFile(value.canPickLocalFile);
    }).catch(() => {
      if (!cancelled) setCanPickLocalFile(false);
    });
    return () => { cancelled = true; };
  }, [bridge]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      bridge.requestRead<FrontendHostContext>({ resource: "frontend.host.context" }),
      bridge.requestRead<FrontendStudioSnapshot>({ resource: "frontend.studio.snapshot" }),
    ])
      .then(([context, value]) => {
        if (cancelled) return;
        setHostContext(context);
        setSnapshot(value);
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : String(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [bridge]);

  useEffect(() => {
    let cancelled = false;
    setChatLoading(true);
    refreshChat()
      .catch((error: unknown) => {
        if (!cancelled) {
          setChatError(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) setChatLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshChat]);

  useEffect(() => {
    const conversationId = chatThread?.conversation?.conversationId;
    void refreshChatResources(conversationId).catch((error: unknown) => {
      setChatError(error instanceof Error ? error.message : String(error));
    });
  }, [chatThread?.conversation?.conversationId, refreshChatResources]);

  useEffect(() => {
    if (!snapshot) return;
    setScreenKey((current) =>
      current && snapshot.screens.some((screen) => screen.pxgKey === current)
        ? current
        : (snapshot.screens[0]?.pxgKey ?? null),
    );
    setActiveCandidateId((current) =>
      current && snapshot.candidates.cards.some((card) => card.candidateId === current)
        ? current
        : (snapshot.candidates.cards[0]?.candidateId ?? null),
    );
  }, [snapshot]);

  useEffect(() => {
    if (!snapshot || !activeCandidateId) {
      setSourceWorkspaceId(null);
      return;
    }
    const candidate = snapshot.candidates.cards.find(
      (item) => item.candidateId === activeCandidateId,
    );
    if (candidate?.workspaceId) {
      setSourceWorkspaceId(null);
      return;
    }
    const inventory = snapshot.sourceWorkspaces;
    setSourceWorkspaceId((current) => {
      if (inventory.selectionState === "UNIQUE") {
        return inventory.autoSelectedWorkspaceId;
      }
      if (
        current &&
        inventory.options.some((option) => option.workspaceId === current)
      ) {
        return current;
      }
      return null;
    });
  }, [activeCandidateId, snapshot]);

  const activeCandidate = useMemo(
    () =>
      snapshot?.candidates.cards.find(
        (candidate) => candidate.candidateId === activeCandidateId,
      ) ?? null,
    [activeCandidateId, snapshot],
  );

  const loadPreviewDocument = useCallback(
    async (previewSessionId: string) => {
      setPreviewError(null);
      setPreviewBrowserReady(false);
      try {
        const document = await bridge.requestRead<PreviewDocument>({
          resource: "frontend.preview.document",
          parameters: { previewSessionId },
        });
        setPreview(document);
        return document;
      } catch (error) {
        setPreview(null);
        setPreviewError(error instanceof Error ? error.message : String(error));
        return null;
      }
    },
    [bridge],
  );

  useEffect(() => {
    setSelectedKey(null);
    setSelection(null);
    setDescriptor(null);
    setInspectorError(null);
    setPreview(null);
    setPreviewError(null);
    setPreviewBrowserReady(false);
    if (activeCandidate?.previewSessionId) {
      void loadPreviewDocument(activeCandidate.previewSessionId);
    }
  }, [activeCandidate?.candidateId, activeCandidate?.previewSessionId, loadPreviewDocument]);

  useEffect(() => {
    setChatIncludeSelection(true);
  }, [selectedKey]);

  useEffect(() => {
    if (!selectedKey || !activeCandidateId) {
      setDescriptor(null);
      setInspectorLoading(false);
      return;
    }
    let cancelled = false;
    setInspectorLoading(true);
    setInspectorError(null);
    bridge
      .requestRead<InspectorDescriptor>({
        resource: "frontend.inspector.describe",
        parameters: { candidateId: activeCandidateId, pxgKey: selectedKey },
      })
      .then((value) => {
        if (!cancelled) setDescriptor(value);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setDescriptor(null);
          setInspectorError(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) setInspectorLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeCandidateId, bridge, preview?.previewSessionId, selectedKey]);

  const sendFrontendCommand = useCallback(
    async (
      commandType: string,
      parameters: Readonly<Record<string, unknown>>,
      options?: { idempotencyKey?: string; commandId?: string },
    ): Promise<CommandAcceptance> => {
      if (!hostContext) {
        throw new Error("Frontend Studio mission context is unavailable.");
      }
      const command: DdeCommand = {
        commandId: options?.commandId,
        commandType,
        targetType: "mission",
        targetId: hostContext.missionId,
        parameters,
        idempotencyKey: options?.idempotencyKey ?? `${commandType}:${actionId()}`,
      };
      return bridge.sendCommand(command);
    },
    [bridge, hostContext],
  );

  useEffect(() => {
    const conversationId = chatThread?.conversation?.conversationId;
    if (!conversationId) return;
    const parameters: Record<string, unknown> = {
      conversation_id: conversationId,
      selected_node_keys:
        chatIncludeSelection && selectedKey ? [selectedKey] : [],
      viewport,
    };
    parameters.active_candidate_id = activeCandidateId;
    parameters.screen_key = screenKey;
    parameters.active_workspace_id = activeCandidate?.workspaceId ?? sourceWorkspaceId;
    sendFrontendCommand("frontend.chat.set_context", parameters).catch(
      (error: unknown) => {
        setChatError(error instanceof Error ? error.message : String(error));
      },
    );
  }, [
    activeCandidate?.workspaceId,
    activeCandidateId,
    chatIncludeSelection,
    chatThread?.conversation?.conversationId,
    screenKey,
    selectedKey,
    sendFrontendCommand,
    sourceWorkspaceId,
    viewport,
  ]);

  useEffect(() => {
    const requestId = activeCandidate?.verificationRequestId;
    if (
      !requestId ||
      activeCandidate?.verificationRequestState !== "PENDING" ||
      activeCandidate.previewState !== "LIVE" ||
      verificationStarted.current.has(requestId)
    ) {
      return;
    }
    verificationStarted.current.add(requestId);
    let cancelled = false;
    setVerificationBusy(true);
    setVerificationError(null);
    sendFrontendCommand("frontend.verification.run", {
      verification_request_id: requestId,
    })
      .then(async () => {
        if (!cancelled) await refreshSnapshot();
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setVerificationError(error instanceof Error ? error.message : String(error));
        }
      })
      .finally(() => {
        if (!cancelled) setVerificationBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeCandidate, refreshSnapshot, sendFrontendCommand]);

  const startPreview = useCallback(async () => {
    if (!activeCandidateId || !screenKey) {
      setPreviewError("Select both a real candidate and a PXG screen before previewing.");
      return;
    }
    const needsSourceWorkspace = !activeCandidate?.workspaceId;
    if (needsSourceWorkspace && !sourceWorkspaceId) {
      const inventory = snapshot?.sourceWorkspaces;
      setPreviewError(
        inventory?.reason ??
          "Select a READY source workspace before materializing this candidate.",
      );
      return;
    }
    setPreviewBusy(true);
    setPreviewError(null);
    setSelection(null);
    setPreviewBrowserReady(false);
    try {
      const parameters: Record<string, unknown> = {
        candidate_id: activeCandidateId,
        screen_key: screenKey,
        viewport,
      };
      if (needsSourceWorkspace && sourceWorkspaceId) {
        parameters.source_workspace_id = sourceWorkspaceId;
      }
      const acceptance = await sendFrontendCommand(
        "frontend.preview.start",
        parameters,
      );
      const sessionId = payloadString(acceptance, "previewSessionId");
      const state = payloadString(acceptance, "state") ?? "UNAVAILABLE";
      const detail = payloadString(acceptance, "stateDetail");
      if (!sessionId || state === "UNAVAILABLE" || state === "RENDER_ERROR") {
        setPreview(null);
        setPreviewError(`${state}${detail ? ` — ${detail}` : ""}`);
        await refreshSnapshot();
        return;
      }
      await refreshSnapshot();
      await loadPreviewDocument(sessionId);
    } catch (error) {
      setPreview(null);
      setPreviewError(error instanceof Error ? error.message : String(error));
    } finally {
      setPreviewBusy(false);
    }
  }, [
    activeCandidate,
    activeCandidateId,
    loadPreviewDocument,
    refreshSnapshot,
    screenKey,
    sendFrontendCommand,
    snapshot,
    sourceWorkspaceId,
    viewport,
  ]);

  const handleChatSend = useCallback(
    async (text: string): Promise<boolean> => {
      if (chatLoading || chatError) {
        setChatError(chatError ?? "Frontend Chat thread is still loading.");
        return false;
      }
      setChatBusy(true);
      setChatError(null);
      try {
        let conversationId = chatThread?.conversation?.conversationId ?? null;
        if (!conversationId) {
          const openParameters: Record<string, unknown> = { viewport };
          if (screenKey) openParameters.screen_key = screenKey;
          const opened = await sendFrontendCommand("frontend.chat.open", openParameters);
          conversationId = payloadString(opened, "conversationId");
          if (!conversationId) {
            throw new Error("Frontend Chat did not return a conversation identity.");
          }
        }

        const contextParameters: Record<string, unknown> = {
          conversation_id: conversationId,
          selected_node_keys:
            chatIncludeSelection && selectedKey ? [selectedKey] : [],
          viewport,
        };
        contextParameters.active_candidate_id = activeCandidateId;
        contextParameters.screen_key = screenKey;
        contextParameters.active_workspace_id = activeCandidate?.workspaceId ?? sourceWorkspaceId;
        await sendFrontendCommand("frontend.chat.set_context", contextParameters);

        const accepted = await sendFrontendCommand("frontend.chat.send", {
          conversation_id: conversationId,
          text,
          attachment_ids: pendingAttachmentIds,
        });
        setPendingAttachmentIds([]);
        const intent = payloadString(accepted, "intent");
        const outcome = payloadString(accepted, "outcome");
        await refreshChat();
        await refreshChatResources(conversationId);

        if (
          chatThread?.conversation?.mode !== "PLAN" &&
          outcome === "ROUTED" &&
          (intent === "MUTATE_DETERMINISTIC" || intent === "UNDO_REVERT")
        ) {
          setSelection(null);
          setSelectedKey(null);
          setPreview(null);
          setPreviewBrowserReady(false);
          await refreshSnapshot();
          await startPreview();
        }
        return true;
      } catch (error) {
        setChatError(error instanceof Error ? error.message : String(error));
        return false;
      } finally {
        setChatBusy(false);
      }
    },
    [
      activeCandidate?.workspaceId,
      activeCandidateId,
      chatError,
      chatIncludeSelection,
      chatLoading,
      chatThread?.conversation?.conversationId,
      pendingAttachmentIds,
      refreshChat,
      refreshChatResources,
      refreshSnapshot,
      screenKey,
      selectedKey,
      sendFrontendCommand,
      sourceWorkspaceId,
      startPreview,
      viewport,
    ],
  );

  const handlePreviewSignal = useCallback(
    async (signal: PreviewRuntimeSignal) => {
      if (!preview || signal.previewSessionId !== preview.previewSessionId) return;
      if (signal.kind === "selection") {
        setSelectedKey(signal.pxgKey);
        setSelection({ pxgKey: signal.pxgKey, geometry: signal.geometry });
        return;
      }
      try {
        if (signal.kind === "ready") {
          const acceptance = await sendFrontendCommand("frontend.preview.set_state", {
            preview_session_id: signal.previewSessionId,
            state: "LIVE",
            content_hash: signal.contentHash,
          });
          const state = payloadString(acceptance, "state");
          setPreview((current) =>
            current && state
              ? {
                  ...current,
                  state: state as PreviewDocument["state"],
                  stateDetail:
                    payloadString(acceptance, "stateDetail") ?? current.stateDetail,
                }
              : current,
          );
          setPreviewBrowserReady(state === "LIVE");
          await refreshSnapshot();
        } else {
          const acceptance = await sendFrontendCommand("frontend.preview.set_state", {
            preview_session_id: signal.previewSessionId,
            state: "RUNTIME_ERROR",
            detail: signal.detail,
          });
          const state = payloadString(acceptance, "state");
          setPreview((current) =>
            current && state
              ? { ...current, state: state as PreviewDocument["state"], stateDetail: signal.detail }
              : current,
          );
          setPreviewBrowserReady(false);
          await refreshSnapshot();
        }
      } catch (error) {
        setPreviewError(error instanceof Error ? error.message : String(error));
        setPreviewBrowserReady(false);
      }
    },
    [preview, refreshSnapshot, sendFrontendCommand],
  );

  const applyInspectorProperty = useCallback(
    async (propertyName: string, value: string) => {
      if (!activeCandidateId || !selectedKey) return;
      setApplyingProperty(propertyName);
      setInspectorError(null);
      try {
        const acceptance = await sendFrontendCommand("frontend.mutation.apply", {
          candidate_id: activeCandidateId,
          mutations: [
            {
              operation: "SET_PROPERTY",
              target_key: selectedKey,
              origin: "INSPECTOR",
              payload: { property: propertyName, value },
            },
          ],
        });
        const refused = acceptance.payload.refused;
        if (Array.isArray(refused) && refused.length) {
          const first = refused[0] as Record<string, unknown>;
          setInspectorError(
            String(first.refusalDetail ?? first.refusalCode ?? "Mutation refused."),
          );
          return;
        }
        setSelection(null);
        setPreview(null);
        setPreviewBrowserReady(false);
        await refreshSnapshot();
        await startPreview();
      } catch (error) {
        setInspectorError(error instanceof Error ? error.message : String(error));
      } finally {
        setApplyingProperty(null);
      }
    },
    [
      activeCandidateId,
      refreshSnapshot,
      selectedKey,
      sendFrontendCommand,
      startPreview,
    ],
  );

  const selectChatConversation = useCallback(async (conversationId: string) => {
    setChatLoading(true);
    try {
      const value = await bridge.requestRead<FrontendChatThread>({
        resource: "frontend.chat.thread.by_id",
        parameters: { conversationId },
      });
      setChatThread(value);
      setPendingAttachmentIds([]);
      await refreshChatResources(conversationId);
    } finally {
      setChatLoading(false);
    }
  }, [bridge, refreshChatResources]);

  const newChatConversation = useCallback(async () => {
    const opened = await sendFrontendCommand("frontend.chat.open", {
      viewport,
      screen_key: screenKey,
      active_workspace_id: activeCandidate?.workspaceId ?? sourceWorkspaceId,
      mode: "ASK",
      title: "New AI Chat",
    });
    const id = payloadString(opened, "conversationId");
    if (!id) throw new Error("DDE did not return a conversation id.");
    await selectChatConversation(id);
  }, [activeCandidate?.workspaceId, screenKey, selectChatConversation, sendFrontendCommand, sourceWorkspaceId, viewport]);

  const mutateConversation = useCallback(async (
    commandType: string,
    parameters: Record<string, unknown>,
  ) => {
    const conversationId = chatThread?.conversation?.conversationId;
    if (!conversationId) throw new Error("Open a Chat conversation first.");
    await sendFrontendCommand(commandType, { conversation_id: conversationId, ...parameters });
    await selectChatConversation(conversationId);
  }, [chatThread?.conversation?.conversationId, selectChatConversation, sendFrontendCommand]);

  const attachLocalFile = useCallback(async () => {
    const conversationId = chatThread?.conversation?.conversationId;
    if (!conversationId) throw new Error("Open a Chat conversation before attaching files.");
    if (!bridge.pickLocalFile || !bridge.uploadPickedFile) {
      throw new Error("This host does not provide native Chat file upload.");
    }
    const picked = await bridge.pickLocalFile();
    if (!picked) return;
    const reserved = await sendFrontendCommand("frontend.chat.attachment.reserve", {
      conversation_id: conversationId,
      filename: picked.filename,
      media_type: picked.mediaType,
      size_bytes: picked.sizeBytes,
    });
    const rawAttachment = reserved.payload.attachment;
    if (!rawAttachment || typeof rawAttachment !== "object") {
      throw new Error("DDE did not return an attachment reservation.");
    }
    const attachmentId = (rawAttachment as Record<string, unknown>).attachmentId;
    if (typeof attachmentId !== "string") throw new Error("Attachment reservation has no identity.");
    await bridge.uploadPickedFile({
      token: picked.token,
      conversationId,
      attachmentId,
      idempotencyKey: `frontend.chat.attachment.upload:${attachmentId}`,
    });
    setPendingAttachmentIds((current) => [...new Set([...current, attachmentId])]);
    await refreshChatResources(conversationId);
  }, [bridge, chatThread?.conversation?.conversationId, refreshChatResources, sendFrontendCommand]);

  const approvePlan = useCallback(async (plan: FrontendChatPlan) => {
    await sendFrontendCommand("frontend.chat.plan.approve", {
      plan_id: plan.planId,
      lock_version: plan.lockVersion,
    });
    await refreshChatResources(plan.conversationId);
    await refreshChat();
  }, [refreshChat, refreshChatResources, sendFrontendCommand]);

  const runPlanStep = useCallback(async (plan: FrontendChatPlan, step: FrontendChatPlanStep) => {
    const prepared = await sendFrontendCommand("frontend.chat.plan.prepare_step", {
      plan_id: plan.planId,
      step_id: step.stepId,
    });
    const commandType = payloadString(prepared, "commandType");
    const idempotencyKey = payloadString(prepared, "idempotencyKey");
    const targetId = payloadString(prepared, "targetId");
    const parameters = prepared.payload.parameters;
    if (!commandType || !idempotencyKey || !targetId || !parameters || typeof parameters !== "object") {
      throw new Error("Prepared Chat plan step is incomplete.");
    }
    const commandId = actionId();
    try {
      await bridge.sendCommand({
        commandId,
        commandType,
        targetType: "mission",
        targetId,
        parameters: parameters as Readonly<Record<string, unknown>>,
        idempotencyKey,
      });
    } finally {
      await sendFrontendCommand("frontend.chat.plan.record_step", {
        plan_id: plan.planId,
        step_id: step.stepId,
        command_id: commandId,
      });
      await refreshChatResources(plan.conversationId);
      await refreshChat();
      await refreshSnapshot();
      if (commandType === "frontend.mutation.apply" || commandType === "frontend.mutation.revert") {
        setSelection(null);
        setSelectedKey(null);
        setPreview(null);
        setPreviewBrowserReady(false);
        await startPreview();
      }
    }
  }, [bridge, refreshChat, refreshChatResources, refreshSnapshot, sendFrontendCommand, startPreview]);

  const chatCursor = useMemo(() => ({
    canPickLocalFile,
    conversations: chatConversations,
    attachments: chatAttachments,
    pendingAttachmentIds,
    plans: chatPlans,
    activities: chatActivities,
    checkpoints: chatCheckpoints,
    changes: chatChanges,
    models: chatModels,
    contextBudget: chatContextBudget,
    onNewConversation: newChatConversation,
    onSelectConversation: selectChatConversation,
    onSearchConversations: async (query: string) => {
      const value = await bridge.requestRead<{ conversations: readonly FrontendChatConversation[] }>({
        resource: "frontend.chat.conversations", parameters: { query },
      });
      setChatConversations(value.conversations ?? []);
    },
    onRenameConversation: async (title: string) => mutateConversation("frontend.chat.rename", { title }),
    onArchiveConversation: async () => {
      await mutateConversation("frontend.chat.archive", { archived: true });
      await refreshChat();
      await refreshChatResources(null);
    },
    onBranchConversation: async (turnId?: string) => {
      const conversationId = chatThread?.conversation?.conversationId;
      if (!conversationId) return;
      const accepted = await sendFrontendCommand("frontend.chat.branch", {
        conversation_id: conversationId,
        from_turn_id: turnId ?? null,
      });
      const raw = accepted.payload.conversation;
      const id = raw && typeof raw === "object" ? (raw as Record<string, unknown>).conversationId : null;
      if (typeof id === "string") await selectChatConversation(id);
    },
    onModeChange: async (next: FrontendChatMode) => mutateConversation("frontend.chat.set_mode", { mode: next }),
    onModelChange: async (model: string | null) => mutateConversation("frontend.chat.set_model", { model_profile_id: model }),
    onAttachLocalFile: attachLocalFile,
    onRemoveAttachment: async (attachmentId: string) => {
      await mutateConversation("frontend.chat.attachment.remove", { attachment_id: attachmentId });
      setPendingAttachmentIds((current) => current.filter((item) => item !== attachmentId));
    },
    onCreateCheckpoint: async (note?: string) => mutateConversation("frontend.chat.checkpoint.create", { note: note ?? null }),
    onRestoreCheckpoint: async (checkpointId: string) => mutateConversation("frontend.chat.checkpoint.restore", { checkpoint_id: checkpointId }),
    onApprovePlan: approvePlan,
    onRunPlanStep: runPlanStep,
    onRetryPlanStep: async (plan: FrontendChatPlan, step: FrontendChatPlanStep) => {
      await sendFrontendCommand("frontend.chat.plan.retry_step", { plan_id: plan.planId, step_id: step.stepId });
      await refreshChatResources(plan.conversationId);
    },
    onCancelPlan: async (plan: FrontendChatPlan) => {
      await sendFrontendCommand("frontend.chat.plan.cancel", { plan_id: plan.planId, lock_version: plan.lockVersion });
      await refreshChatResources(plan.conversationId);
    },
    onCancelActivity: async (activity: FrontendChatActivity) => mutateConversation("frontend.chat.activity.cancel", { activity_id: activity.activityId, reason: "Stopped by user" }),
    onAcceptChange: async (change: FrontendChatChange) => mutateConversation("frontend.chat.workspace.accept_file", { path: change.path, expected_diff_hash: change.diffHash }),
    onRevertChange: async (change: FrontendChatChange) => mutateConversation("frontend.chat.workspace.revert_file", { path: change.path, expected_diff_hash: change.diffHash }),
    onRevertAll: async () => {
      const exact = chatCheckpoints.find((item) => item.diffHash && item.diffHash === chatChanges?.diffHash);
      if (!exact) throw new Error("Create a checkpoint of the exact current diff before revert-all.");
      await mutateConversation("frontend.chat.workspace.revert_all", { checkpoint_id: exact.checkpointId });
    },
    onApplyPatch: async (patch: string) => mutateConversation("frontend.chat.workspace.apply_patch", {
      patch_text: patch,
      expected_diff_hash: chatChanges?.diffHash ?? null,
    }),
    onPinContext: async (ref: string, pinned: boolean) => mutateConversation("frontend.chat.pin_context", { context_ref: ref, pinned }),
  }), [
    approvePlan, attachLocalFile, bridge, canPickLocalFile, chatActivities, chatAttachments,
    chatChanges, chatCheckpoints, chatContextBudget, chatConversations, chatModels, chatPlans,
    chatThread?.conversation?.conversationId, mutateConversation, newChatConversation,
    pendingAttachmentIds, refreshChat, refreshChatResources, runPlanStep,
    selectChatConversation, sendFrontendCommand,
  ]);

  const breadcrumb = selectedKey
    ? ["Project", screenKey ?? "Screen", selectedKey]
    : group
      ? ["Project", group]
      : [];

  const displayedPreview =
    preview && preview.state === "LIVE" && !previewBrowserReady
      ? { ...preview, state: "LOADING" as const, stateDetail: "awaiting this browser handshake" }
      : preview;

  return (
    <DdeShell
      topBar={
        <GlobalTopBar
          snapshot={snapshot}
          projectName={projectName ?? hostContext?.projectName ?? null}
          mode={mode}
          onModeChange={setMode}
        />
      }
      rail={<AppRail modules={MODULES} activeId="frontend" onSelect={() => {}} />}
      explorer={
        <ContextSidebar
          explorer={snapshot?.explorer ?? null}
          orchestrator={snapshot?.orchestrator ?? null}
          selectedGroup={group}
          onSelectGroup={setGroup}
        />
      }
      workspace={
        loadError ? (
          <div className="dde-workspace-inner">
            <div className="dde-canvas">
              <div className="dde-unavailable" role="alert">
                <span className="dde-unavailable-label">Unavailable</span>
                <span className="dde-unavailable-reason">
                  Could not read Frontend Studio context: {loadError}
                </span>
              </div>
            </div>
          </div>
        ) : (
          <FrontendStudioWorkspace
            mode={mode}
            snapshot={snapshot}
            viewport={viewport}
            onViewportChange={setViewport}
            screenKey={screenKey}
            onScreenChange={(value) => {
              setScreenKey(value || null);
              setPreview(null);
              setSelection(null);
              setSelectedKey(null);
            }}
            activeCandidateId={activeCandidateId}
            onActiveCandidateChange={setActiveCandidateId}
            requiresSourceWorkspace={Boolean(activeCandidate && !activeCandidate.workspaceId)}
            sourceWorkspaces={snapshot?.sourceWorkspaces ?? null}
            sourceWorkspaceId={sourceWorkspaceId}
            onSourceWorkspaceChange={setSourceWorkspaceId}
            preview={displayedPreview}
            previewError={previewError}
            previewBusy={previewBusy}
            verificationBusy={verificationBusy}
            verificationError={verificationError}
            selection={selection}
            onStartPreview={() => void startPreview()}
            onPreviewSignal={(signal) => void handlePreviewSignal(signal)}
          />
        )
      }
      chat={
        <DdeChatComposer
          thread={chatThread}
          loading={chatLoading}
          error={chatError}
          busy={chatBusy}
          screenKey={screenKey}
          candidateId={activeCandidateId}
          candidateLabel={activeCandidate?.title ?? null}
          selectedKey={selection?.pxgKey ?? null}
          viewport={viewport}
          includeSelection={chatIncludeSelection}
          onIncludeSelectionChange={setChatIncludeSelection}
          onSend={handleChatSend}
          cursor={chatCursor}
        />
      }
      inspector={
        <InspectorPanel
          bridge={bridge}
          selectedKey={selectedKey}
          descriptor={descriptor}
          loading={inspectorLoading}
          error={inspectorError}
          applyingProperty={applyingProperty}
          candidate={activeCandidate}
          onApply={(propertyName, value) =>
            void applyInspectorProperty(propertyName, value)
          }
        />
      }
      statusBar={
        <StatusBar
          snapshot={snapshot}
          breadcrumb={breadcrumb}
          buildVersion={buildVersion ?? snapshot?.sync.buildVersion ?? null}
        />
      }
    />
  );
}

function payloadString(acceptance: CommandAcceptance, key: string): string | null {
  const value = acceptance.payload[key];
  return typeof value === "string" && value ? value : null;
}

function actionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
