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
import { InspectorPanel } from "../frontend-studio/InspectorPanel";
import { AppRail, type RailModule } from "../shell/AppRail";
import { ContextSidebar } from "../shell/ContextSidebar";
import { DdeShell } from "../shell/DdeShell";
import { GlobalTopBar } from "../shell/GlobalTopBar";
import { StatusBar } from "../shell/StatusBar";
import type {
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

  const refreshSnapshot = useCallback(async () => {
    const value = await bridge.requestRead<FrontendStudioSnapshot>({
      resource: "frontend.studio.snapshot",
    });
    setSnapshot(value);
    return value;
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
    ): Promise<CommandAcceptance> => {
      if (!hostContext) {
        throw new Error("Frontend Studio mission context is unavailable.");
      }
      const command: DdeCommand = {
        commandType,
        targetType: "mission",
        targetId: hostContext.missionId,
        parameters,
        idempotencyKey: `${commandType}:${actionId()}`,
      };
      return bridge.sendCommand(command);
    },
    [bridge, hostContext],
  );

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
