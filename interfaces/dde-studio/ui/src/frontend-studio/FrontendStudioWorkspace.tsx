import { useEffect, useRef } from "react";
import { Unavailable } from "../components/Honest";
import { FrontendChatComposer } from "./FrontendChatComposer";
import type {
  CandidateCardSnapshot,
  FrontendChatThread,
  FrontendStudioSnapshot,
  PreviewDocument,
  SourceWorkspaceInventory,
  StudioMode,
} from "../state/projections";

export interface PreviewSelection {
  readonly pxgKey: string;
  readonly geometry: {
    readonly x: number;
    readonly y: number;
    readonly width: number;
    readonly height: number;
  };
}

export type PreviewRuntimeSignal =
  | {
      readonly kind: "ready";
      readonly previewSessionId: string;
      readonly contentHash: string;
    }
  | {
      readonly kind: "selection";
      readonly previewSessionId: string;
      readonly contentHash: string;
      readonly pxgKey: string;
      readonly geometry: PreviewSelection["geometry"];
    }
  | {
      readonly kind: "runtime_error";
      readonly previewSessionId: string;
      readonly contentHash: string;
      readonly detail: string;
    };

export interface WorkspaceProps {
  readonly mode: StudioMode;
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly viewport: string;
  readonly onViewportChange: (value: string) => void;
  readonly screenKey: string | null;
  readonly onScreenChange: (value: string) => void;
  readonly activeCandidateId: string | null;
  readonly onActiveCandidateChange: (candidateId: string) => void;
  readonly requiresSourceWorkspace: boolean;
  readonly sourceWorkspaces: SourceWorkspaceInventory | null;
  readonly sourceWorkspaceId: string | null;
  readonly onSourceWorkspaceChange: (workspaceId: string) => void;
  readonly preview: PreviewDocument | null;
  readonly previewError: string | null;
  readonly previewBusy: boolean;
  readonly verificationBusy: boolean;
  readonly verificationError: string | null;
  readonly selection: PreviewSelection | null;
  readonly onStartPreview: () => void;
  readonly onPreviewSignal: (signal: PreviewRuntimeSignal) => void;
  readonly chatThread: FrontendChatThread | null;
  readonly chatLoading: boolean;
  readonly chatError: string | null;
  readonly chatBusy: boolean;
  readonly chatIncludeSelection: boolean;
  readonly onChatIncludeSelectionChange: (value: boolean) => void;
  readonly onChatSend: (text: string) => Promise<boolean>;
}

export function FrontendStudioWorkspace({
  mode,
  snapshot,
  viewport,
  onViewportChange,
  screenKey,
  onScreenChange,
  activeCandidateId,
  onActiveCandidateChange,
  requiresSourceWorkspace,
  sourceWorkspaces,
  sourceWorkspaceId,
  onSourceWorkspaceChange,
  preview,
  previewError,
  previewBusy,
  verificationBusy,
  verificationError,
  selection,
  onStartPreview,
  onPreviewSignal,
  chatThread,
  chatLoading,
  chatError,
  chatBusy,
  chatIncludeSelection,
  onChatIncludeSelectionChange,
  onChatSend,
}: WorkspaceProps) {
  const activeCandidate = snapshot?.candidates.cards.find(
    (candidate) => candidate.candidateId === activeCandidateId,
  );
  return (
    <div className="dde-workspace-inner" data-mode={mode}>
      <CanvasToolbar
        mode={mode}
        viewport={viewport}
        onViewportChange={onViewportChange}
        snapshot={snapshot}
        screenKey={screenKey}
        onScreenChange={onScreenChange}
        preview={preview}
      />
      <div className="dde-canvas" data-testid="canvas">
        {mode === "coverage" ? (
          <CoverageMode snapshot={snapshot} />
        ) : mode === "qa" ? (
          <QaMode snapshot={snapshot} activeCandidateId={activeCandidateId} />
        ) : mode === "design" ? (
          <DesignMode
            activeCandidateId={activeCandidateId}
            requiresSourceWorkspace={requiresSourceWorkspace}
            sourceWorkspaces={sourceWorkspaces}
            sourceWorkspaceId={sourceWorkspaceId}
            onSourceWorkspaceChange={onSourceWorkspaceChange}
            preview={preview}
            previewError={previewError}
            previewBusy={previewBusy}
            viewport={viewport}
            selection={selection}
            onStartPreview={onStartPreview}
            onPreviewSignal={onPreviewSignal}
          />
        ) : (
          <Unavailable availability="NOT_IMPLEMENTED" reason={MODE_REASON[mode]} />
        )}
      </div>
      <CandidateStrip
        snapshot={snapshot}
        activeCandidateId={activeCandidateId}
        onActiveCandidateChange={onActiveCandidateChange}
        verificationBusy={verificationBusy}
        verificationError={verificationError}
      />
      <FrontendChatComposer
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
        onIncludeSelectionChange={onChatIncludeSelectionChange}
        onSend={onChatSend}
      />
    </div>
  );
}

const MODE_REASON: Record<StudioMode, string> = {
  design: "",
  coverage: "",
  architecture:
    "The PXG graph view is DDE-069 M12. The graph itself is real — see Coverage — but this rendering is not built.",
  qa: "Verification evidence summary is implemented; Screen Audit findings land in the next DDE-069 packet.",
  source: "The design-source registry is DDE-069 M8. No source adapter is wired yet.",
};

function CanvasToolbar({
  mode,
  viewport,
  onViewportChange,
  snapshot,
  screenKey,
  onScreenChange,
  preview,
}: {
  readonly mode: StudioMode;
  readonly viewport: string;
  readonly onViewportChange: (value: string) => void;
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly screenKey: string | null;
  readonly onScreenChange: (value: string) => void;
  readonly preview: PreviewDocument | null;
}) {
  return (
    <div
      className="dde-canvas-toolbar"
      data-testid="canvas-toolbar"
      role="toolbar"
      aria-label="Canvas tools"
    >
      <select
        className="dde-viewport"
        data-testid="viewport-select"
        aria-label="Preview viewport"
        value={viewport}
        onChange={(event) => onViewportChange(event.target.value)}
      >
        <option value="1440">Desktop 1440</option>
        <option value="1024">Tablet 1024</option>
        <option value="390">Mobile 390</option>
      </select>
      <select
        className="dde-viewport dde-screen-select"
        data-testid="screen-select"
        aria-label="Preview screen"
        value={screenKey ?? ""}
        onChange={(event) => onScreenChange(event.target.value)}
        disabled={!snapshot?.screens.length}
      >
        {!snapshot?.screens.length ? <option value="">No screens</option> : null}
        {snapshot?.screens.map((screen) => (
          <option key={screen.pxgKey} value={screen.pxgKey}>
            {screen.title}
          </option>
        ))}
      </select>
      {preview ? (
        <span
          className="dde-preview-badge"
          data-testid="preview-badge"
          data-state={preview.state}
          title={preview.stateDetail ?? undefined}
        >
          {preview.state}
        </span>
      ) : null}
      <span className="dde-toolbar-spacer" />
      <button
        type="button"
        className="dde-action dde-action-ai"
        data-testid="claude-design"
        disabled
        title="Claude /design — unavailable: no certified design provider transport. DesignGateway is implemented; generic Claude Code invocation is not an allowed fallback."
        aria-label="Claude /design — unavailable: no certified design provider transport"
      >
        Claude /design
      </button>
      <span className="dde-zoom" data-testid="zoom">
        100%
      </span>
      <span className="dde-muted dde-mode-label">{mode}</span>
    </div>
  );
}

function DesignMode({
  activeCandidateId,
  requiresSourceWorkspace,
  sourceWorkspaces,
  sourceWorkspaceId,
  onSourceWorkspaceChange,
  preview,
  previewError,
  previewBusy,
  viewport,
  selection,
  onStartPreview,
  onPreviewSignal,
}: {
  readonly activeCandidateId: string | null;
  readonly requiresSourceWorkspace: boolean;
  readonly sourceWorkspaces: SourceWorkspaceInventory | null;
  readonly sourceWorkspaceId: string | null;
  readonly onSourceWorkspaceChange: (workspaceId: string) => void;
  readonly preview: PreviewDocument | null;
  readonly previewError: string | null;
  readonly previewBusy: boolean;
  readonly viewport: string;
  readonly selection: PreviewSelection | null;
  readonly onStartPreview: () => void;
  readonly onPreviewSignal: (signal: PreviewRuntimeSignal) => void;
}) {
  if (!activeCandidateId) {
    return (
      <Unavailable
        availability="EMPTY"
        reason="Select a real candidate below. No placeholder candidate is fabricated."
      />
    );
  }
  if (!preview) {
    const sourceBlocked = requiresSourceWorkspace && !sourceWorkspaceId;
    return (
      <div className="dde-preview-empty" data-testid="preview-empty">
        {previewError ? (
          <Unavailable availability="UNAVAILABLE" reason={previewError} />
        ) : (
          <p className="dde-muted">This candidate has no loaded preview document.</p>
        )}
        {requiresSourceWorkspace ? (
          <SourceWorkspacePicker
            inventory={sourceWorkspaces}
            value={sourceWorkspaceId}
            onChange={onSourceWorkspaceChange}
          />
        ) : null}
        <button
          type="button"
          className="dde-action"
          data-testid="start-preview"
          disabled={previewBusy || sourceBlocked}
          title={
            sourceBlocked
              ? (sourceWorkspaces?.reason ?? "A READY source workspace is required.")
              : undefined
          }
          onClick={onStartPreview}
        >
          {previewBusy ? "Building preview…" : "Start code-backed preview"}
        </button>
      </div>
    );
  }
  return (
    <LivePreview
      preview={preview}
      viewport={viewport}
      selection={selection}
      onSignal={onPreviewSignal}
    />
  );
}

function SourceWorkspacePicker({
  inventory,
  value,
  onChange,
}: {
  readonly inventory: SourceWorkspaceInventory | null;
  readonly value: string | null;
  readonly onChange: (workspaceId: string) => void;
}) {
  if (!inventory || inventory.selectionState === "EMPTY") {
    return (
      <Unavailable
        availability={inventory?.availability ?? "UNAVAILABLE"}
        reason={inventory?.reason ?? "Source workspace inventory is unavailable."}
      />
    );
  }
  return (
    <label className="dde-source-workspace-picker">
      <span>Source workspace</span>
      <select
        className="dde-viewport"
        data-testid="source-workspace-select"
        aria-label="Candidate source workspace"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      >
        {inventory.selectionState === "AMBIGUOUS" ? (
          <option value="">Select READY source…</option>
        ) : null}
        {inventory.options.map((option) => (
          <option key={option.workspaceId} value={option.workspaceId}>
            {option.purpose ?? "project workspace"} · {option.currentRevision.slice(0, 8)}
          </option>
        ))}
      </select>
      {inventory.selectionState === "AMBIGUOUS" && inventory.reason ? (
        <span className="dde-muted">{inventory.reason}</span>
      ) : null}
    </label>
  );
}

function LivePreview({
  preview,
  viewport,
  selection,
  onSignal,
}: {
  readonly preview: PreviewDocument;
  readonly viewport: string;
  readonly selection: PreviewSelection | null;
  readonly onSignal: (signal: PreviewRuntimeSignal) => void;
}) {
  const frame = useRef<HTMLIFrameElement | null>(null);
  useEffect(() => {
    const receive = (event: MessageEvent<unknown>) => {
      if (event.source !== frame.current?.contentWindow) return;
      if (!event.data || typeof event.data !== "object") return;
      const message = event.data as Record<string, unknown>;
      if (message.type !== "dde.preview") return;
      if (
        message.previewSessionId !== preview.previewSessionId ||
        message.contentHash !== preview.contentHash
      ) {
        return;
      }
      if (message.kind === "ready" && typeof message.contentHash === "string") {
        onSignal({
          kind: "ready",
          previewSessionId: preview.previewSessionId,
          contentHash: message.contentHash,
        });
      } else if (
        message.kind === "selection" &&
        typeof message.pxgKey === "string" &&
        isGeometry(message.geometry)
      ) {
        onSignal({
          kind: "selection",
          previewSessionId: preview.previewSessionId,
          contentHash: String(message.contentHash),
          pxgKey: message.pxgKey,
          geometry: message.geometry,
        });
      } else if (message.kind === "runtime_error") {
        onSignal({
          kind: "runtime_error",
          previewSessionId: preview.previewSessionId,
          contentHash: String(message.contentHash),
          detail:
            typeof message.detail === "string" ? message.detail : "runtime error",
        });
      }
    };
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [onSignal, preview.contentHash, preview.previewSessionId]);

  const frameWidth = Number.parseInt(viewport, 10) || 1440;
  return (
    <div className="dde-preview-stage" data-testid="live-preview-surface">
      <div
        className="dde-preview-frame-wrap"
        style={{ width: `${frameWidth}px` }}
        data-preview-state={preview.state}
      >
        <iframe
          ref={frame}
          key={preview.previewSessionId}
          className="dde-preview-frame"
          title={`Candidate preview ${preview.screenKey}`}
          sandbox="allow-scripts"
          srcDoc={preview.content}
        />
        {selection ? (
          <div
            className="dde-selection-outline"
            data-testid="selection-outline"
            data-pxg-key={selection.pxgKey}
            style={{
              left: selection.geometry.x,
              top: selection.geometry.y,
              width: selection.geometry.width,
              height: selection.geometry.height,
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

function isGeometry(value: unknown): value is PreviewSelection["geometry"] {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return ["x", "y", "width", "height"].every(
    (key) => typeof row[key] === "number",
  );
}

function CoverageMode({
  snapshot,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
}) {
  const coverage = snapshot?.coverage;
  if (!coverage) {
    return (
      <Unavailable
        availability="NOT_CONFIGURED"
        reason="No coverage snapshot has been computed for this project."
      />
    );
  }
  return (
    <div className="dde-coverage-mode" data-testid="coverage-mode">
      <h2 className="dde-panel-heading">Coverage</h2>
      <p className="dde-muted">
        Contract v{coverage.contractVersion ?? "—"} against PXG revision{" "}
        {coverage.pxgRevision ?? "—"}
        {coverage.stale ? " (stale — recompute)" : ""}
      </p>
      <table className="dde-table">
        <thead>
          <tr>
            <th scope="col">Dimension</th>
            <th scope="col">State</th>
          </tr>
        </thead>
        <tbody>
          {coverage.dimensionStates.map(([dimension, state]) => (
            <tr key={dimension} data-testid={`coverage-dimension-${dimension}`}>
              <th scope="row">{dimension}</th>
              <td data-state={state}>{state}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function QaMode({
  snapshot,
  activeCandidateId,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly activeCandidateId: string | null;
}) {
  if (!snapshot) {
    return <Unavailable availability="UNAVAILABLE" reason="Verification inventory is loading." />;
  }
  const cards = snapshot.candidates.cards.filter(
    (candidate) =>
      candidate.verificationRequestId !== null || candidate.verificationRunId !== null,
  );
  if (!cards.length) {
    return (
      <Unavailable
        availability="EMPTY"
        reason="No candidate verification request or run exists yet."
      />
    );
  }
  return (
    <div className="dde-coverage-mode" data-testid="qa-mode">
      <h2 className="dde-panel-heading">Candidate verification</h2>
      <p className="dde-muted">
        Real DDE-068 request, check and evidence state. PENDING/BLOCKED/SUPERSEDED are
        not verdicts.
      </p>
      {cards.map((candidate) => (
        <section
          key={candidate.candidateId}
          className="dde-qa-candidate"
          data-testid={`qa-candidate-${candidate.candidateId}`}
          data-active={candidate.candidateId === activeCandidateId}
        >
          <div className="dde-qa-heading">
            <strong>{candidate.title}</strong>
            <span>{candidate.verificationRequestState ?? "NOT REQUESTED"}</span>
            <span>{candidate.verificationRunStatus ?? "NO RUN"}</span>
          </div>
          {candidate.verificationChecks.length ? (
            <table className="dde-table">
              <thead>
                <tr>
                  <th scope="col">Check</th>
                  <th scope="col">Kind</th>
                  <th scope="col">State</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {candidate.verificationChecks.map((check) => (
                  <tr key={check.checkRef} data-testid={`qa-check-${check.kind}`}>
                    <td>{check.checkRef}</td>
                    <td>{check.kind}</td>
                    <td data-state={check.status}>{check.status}</td>
                    <td>{check.detail ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="dde-muted">No completed check results are attached.</p>
          )}
          <p className="dde-muted">
            Evidence: {candidate.verificationEvidenceRefs.length} · confidence {" "}
            {candidate.verificationConfidence ?? "—"}
          </p>
        </section>
      ))}
    </div>
  );
}

function CandidateStrip({
  snapshot,
  activeCandidateId,
  onActiveCandidateChange,
  verificationBusy,
  verificationError,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly activeCandidateId: string | null;
  readonly onActiveCandidateChange: (candidateId: string) => void;
  readonly verificationBusy: boolean;
  readonly verificationError: string | null;
}) {
  const cards = snapshot?.candidates.cards ?? [];
  if (!snapshot) {
    return (
      <div className="dde-candidate-strip" data-testid="candidate-strip">
        <Unavailable availability="UNAVAILABLE" reason="Candidate board is loading." />
      </div>
    );
  }
  if (!cards.length) {
    return (
      <div className="dde-candidate-strip" data-testid="candidate-strip">
        <Unavailable
          availability="EMPTY"
          reason="No frontend candidates exist in this project. No placeholder candidate is fabricated."
        />
      </div>
    );
  }
  return (
    <div className="dde-candidate-strip" data-testid="candidate-strip">
      {cards.map((candidate) => (
        <CandidateCard
          key={candidate.candidateId}
          candidate={candidate}
          active={candidate.candidateId === activeCandidateId}
          onSelect={() => onActiveCandidateChange(candidate.candidateId)}
          verificationBusy={
            verificationBusy && candidate.candidateId === activeCandidateId
          }
          verificationError={
            candidate.candidateId === activeCandidateId ? verificationError : null
          }
        />
      ))}
    </div>
  );
}

function CandidateCard({
  candidate,
  active,
  onSelect,
  verificationBusy,
  verificationError,
}: {
  readonly candidate: CandidateCardSnapshot;
  readonly active: boolean;
  readonly onSelect: () => void;
  readonly verificationBusy: boolean;
  readonly verificationError: string | null;
}) {
  return (
    <button
      type="button"
      className="dde-candidate-card"
      data-testid={`candidate-${candidate.candidateId}`}
      data-active={active}
      onClick={onSelect}
    >
      <span className="dde-candidate-title">{candidate.title}</span>
      <span className="dde-candidate-meta">
        {candidate.state}
        {candidate.stale ? " · STALE" : ""}
      </span>
      <span className="dde-candidate-preview-state">
        {candidate.previewState ?? "NO PREVIEW"}
      </span>
      <span
        className="dde-candidate-verification-state"
        data-testid={`candidate-verification-${candidate.candidateId}`}
        title={candidate.verificationRequestReason ?? undefined}
      >
        {verificationBusy
          ? "VERIFYING…"
          : candidate.verificationRequestState
            ? `VERIFY ${candidate.verificationRequestState}`
            : "NOT EVALUATED"}
      </span>
      {verificationError ? (
        <span className="dde-candidate-detail" role="alert">
          Verification command failed: {verificationError}
        </span>
      ) : null}
      {candidate.previewStateDetail ? (
        <span className="dde-candidate-detail">{candidate.previewStateDetail}</span>
      ) : null}
    </button>
  );
}
