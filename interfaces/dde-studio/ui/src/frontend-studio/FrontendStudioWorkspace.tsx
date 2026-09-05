import { useEffect, useRef } from "react";
import { Unavailable } from "../components/Honest";
import type {
  CandidateCardSnapshot,
  FrontendStudioSnapshot,
  PreviewDocument,
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
  readonly preview: PreviewDocument | null;
  readonly previewError: string | null;
  readonly previewBusy: boolean;
  readonly selection: PreviewSelection | null;
  readonly onStartPreview: () => void;
  readonly onPreviewSignal: (signal: PreviewRuntimeSignal) => void;
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
  preview,
  previewError,
  previewBusy,
  selection,
  onStartPreview,
  onPreviewSignal,
}: WorkspaceProps) {
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
        ) : mode === "design" ? (
          <DesignMode
            activeCandidateId={activeCandidateId}
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
      />
    </div>
  );
}

const MODE_REASON: Record<StudioMode, string> = {
  design: "",
  coverage: "",
  architecture:
    "The PXG graph view is DDE-069 M12. The graph itself is real — see Coverage — but this rendering is not built.",
  qa: "The QA finding inventory read is DDE-069 M17. Verification evidence exists and gates promotion; this aggregation view does not.",
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
  preview,
  previewError,
  previewBusy,
  viewport,
  selection,
  onStartPreview,
  onPreviewSignal,
}: {
  readonly activeCandidateId: string | null;
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
    return (
      <div className="dde-preview-empty" data-testid="preview-empty">
        {previewError ? (
          <Unavailable availability="UNAVAILABLE" reason={previewError} />
        ) : (
          <p className="dde-muted">This candidate has no loaded preview document.</p>
        )}
        <button
          type="button"
          className="dde-action"
          data-testid="start-preview"
          disabled={previewBusy}
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

function CandidateStrip({
  snapshot,
  activeCandidateId,
  onActiveCandidateChange,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly activeCandidateId: string | null;
  readonly onActiveCandidateChange: (candidateId: string) => void;
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
        />
      ))}
    </div>
  );
}

function CandidateCard({
  candidate,
  active,
  onSelect,
}: {
  readonly candidate: CandidateCardSnapshot;
  readonly active: boolean;
  readonly onSelect: () => void;
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
      {candidate.previewStateDetail ? (
        <span className="dde-candidate-detail">{candidate.previewStateDetail}</span>
      ) : null}
    </button>
  );
}
