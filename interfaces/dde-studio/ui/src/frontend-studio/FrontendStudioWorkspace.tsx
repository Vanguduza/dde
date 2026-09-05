import { useEffect, useRef, useState } from "react";
import { Unavailable } from "../components/Honest";
import type {
  CandidateCardSnapshot,
  FrontendStudioSnapshot,
  PreviewDocument,
  ScreenAuditMatrix,
  ScreenAuditFinding,
  SourceCatalogRead,
  FrontendProvenanceRecord,
  FrontendSourceBlendPreference,
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
  readonly auditMatrix: ScreenAuditMatrix | null;
  readonly sourceCatalog: SourceCatalogRead | null;
  readonly sourceBusy: boolean;
  readonly sourceError: string | null;
  readonly selectedProvenance: readonly FrontendProvenanceRecord[];
  readonly targetBlend: FrontendSourceBlendPreference | null;
  readonly targetBlendScope: string;
  readonly onTargetBlendChange: (weights: Readonly<Record<string, number>>) => void;
  readonly onInitializeSources: () => void;
  readonly onSearchSources: (query: string) => void;
  readonly onRecommendTemplates: () => void;
  readonly onSourceArtifactAction: (
    action: "inspect" | "fetch" | "sandbox" | "validate_sandbox" | "admit",
    artifactId: string,
  ) => void;
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
}

export function FrontendStudioWorkspace({
  mode,
  snapshot,
  auditMatrix,
  sourceCatalog,
  sourceBusy,
  sourceError,
  selectedProvenance,
  targetBlend,
  targetBlendScope,
  onTargetBlendChange,
  onInitializeSources,
  onSearchSources,
  onRecommendTemplates,
  onSourceArtifactAction,
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
          <CoverageMode snapshot={snapshot} auditMatrix={auditMatrix} />
        ) : mode === "qa" ? (
          <QaMode snapshot={snapshot} auditMatrix={auditMatrix} activeCandidateId={activeCandidateId} />
        ) : mode === "architecture" ? (
          <ArchitectureMode auditMatrix={auditMatrix} />
        ) : mode === "source" ? (
          <SourceMode
            snapshot={snapshot}
            catalog={sourceCatalog}
            busy={sourceBusy}
            error={sourceError}
            provenance={selectedProvenance}
            targetBlend={targetBlend}
            targetBlendScope={targetBlendScope}
            onTargetBlendChange={onTargetBlendChange}
            onInitialize={onInitializeSources}
            onSearch={onSearchSources}
            onRecommendTemplates={onRecommendTemplates}
            onArtifactAction={onSourceArtifactAction}
          />
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
    </div>
  );
}

const MODE_REASON: Record<StudioMode, string> = {
  design: "",
  coverage: "",
  architecture: "",
  qa: "",
  source: "",
};

function SourceMode({
  snapshot,
  catalog,
  busy,
  error,
  provenance,
  targetBlend,
  targetBlendScope,
  onTargetBlendChange,
  onInitialize,
  onSearch,
  onRecommendTemplates,
  onArtifactAction,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly catalog: SourceCatalogRead | null;
  readonly busy: boolean;
  readonly error: string | null;
  readonly provenance: readonly FrontendProvenanceRecord[];
  readonly targetBlend: FrontendSourceBlendPreference | null;
  readonly targetBlendScope: string;
  readonly onTargetBlendChange: (weights: Readonly<Record<string, number>>) => void;
  readonly onInitialize: () => void;
  readonly onSearch: (query: string) => void;
  readonly onRecommendTemplates: () => void;
  readonly onArtifactAction: (
    action: "inspect" | "fetch" | "sandbox" | "validate_sandbox" | "admit",
    artifactId: string,
  ) => void;
}) {
  const [query, setQuery] = useState("");
  const [blendDraft, setBlendDraft] = useState<Record<string, number>>({});
  const providers = snapshot?.sources.providers ?? [];
  const artifacts = catalog?.artifacts ?? [];
  const templates = catalog?.templates ?? [];
  useEffect(() => {
    const next: Record<string, number> = {};
    for (const provider of providers) {
      next[provider.providerKey] = Math.round(
        (targetBlend?.weights[provider.providerKey] ?? 0) * 100,
      );
    }
    setBlendDraft(next);
  }, [targetBlend?.contentHash, providers.map((item) => item.providerKey).join("|")]);
  const blendTotal = Object.values(blendDraft).reduce((total, value) => total + value, 0);
  return (
    <div className="dde-coverage-mode dde-source-mode" data-testid="source-mode">
      <div className="dde-mode-heading-row">
        <div>
          <h2 className="dde-panel-heading">Source Intelligence</h2>
          <p className="dde-muted">
            Search and inspect governed sources. Retrieved code remains isolated until
            exact bytes pass compiler, provenance, licence, security, accessibility and
            design-system admission.
          </p>
        </div>
        <button
          type="button"
          className="dde-action"
          data-testid="source-initialize"
          disabled={busy}
          onClick={onInitialize}
        >
          Refresh providers
        </button>
      </div>
      {error ? <p role="alert" className="dde-property-refusal">{error}</p> : null}
      <div className="dde-source-provider-grid" data-testid="source-providers">
        {providers.map((provider) => (
          <article
            key={provider.providerKey}
            className="dde-source-provider-card"
            data-testid={`source-provider-${provider.providerKey}`}
            data-state={provider.status}
          >
            <strong>{provider.displayName}</strong>
            <span>{provider.sourceClass}</span>
            <span data-state={provider.status}>{provider.status}</span>
            <span>{provider.itemCount.value ?? "—"} item(s)</span>
            {provider.healthDetail ? <small>{provider.healthDetail}</small> : null}
          </article>
        ))}
      </div>
      <form
        className="dde-source-search"
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim()) onSearch(query.trim());
        }}
      >
        <input
          aria-label="Search design sources"
          data-testid="source-search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search components, templates and donor evidence…"
        />
        <button
          type="submit"
          className="dde-action"
          data-testid="source-search"
          disabled={busy || !query.trim()}
        >
          {busy ? "Working…" : "Search"}
        </button>
        <button
          type="button"
          className="dde-action"
          data-testid="source-recommend-templates"
          disabled={busy}
          onClick={onRecommendTemplates}
        >
          Recommend templates
        </button>
      </form>
      <section data-testid="source-artifacts">
        <h3>Indexed artifacts</h3>
        {!catalog ? (
          <Unavailable
            availability={snapshot?.sources.availability ?? "NOT_CONFIGURED"}
            reason={snapshot?.sources.reason ?? "Source inventory has not been read."}
          />
        ) : artifacts.length ? (
          <div className="dde-source-artifact-list">
            {artifacts.map((artifact) => (
              <article
                key={artifact.artifactId}
                className="dde-source-artifact-card"
                data-testid={`source-artifact-${artifact.artifactId}`}
              >
                <div><strong>{artifact.title}</strong> · {artifact.artifactKind}</div>
                <div className="dde-chip-row">
                  <span className="dde-chip" data-state={artifact.retrievalState}>{artifact.retrievalState}</span>
                  <span className="dde-chip" data-state={artifact.licenseState}>{artifact.licenseState}</span>
                  <span className="dde-chip" data-state={artifact.securityState}>security {artifact.securityState}</span>
                  <span className="dde-chip" data-state={artifact.accessibilityState}>a11y {artifact.accessibilityState}</span>
                </div>
                <small>{artifact.sourceUri ?? artifact.providerArtifactKey}</small>
                <small>
                  bytes {artifact.contentObjectBackend ?? "not stored"}
                  {artifact.contentSizeBytes !== null ? ` · ${artifact.contentSizeBytes}` : ""}
                </small>
                <div className="dde-chip-row">
                  {(["inspect", "fetch", "admit"] as const).map((action) => (
                    <button
                      key={action}
                      type="button"
                      className="dde-action"
                      data-testid={`source-${action}-${artifact.artifactId}`}
                      disabled={busy}
                      onClick={() => onArtifactAction(action, artifact.artifactId)}
                    >
                      {action}
                    </button>
                  ))}
                  {artifact.retrievalState === "FETCHED" && !artifact.metadata.sandbox_candidate_id ? (
                    <button
                      type="button"
                      className="dde-action"
                      data-testid={`source-sandbox-${artifact.artifactId}`}
                      disabled={busy}
                      onClick={() => onArtifactAction("sandbox", artifact.artifactId)}
                    >
                      adapt in sandbox
                    </button>
                  ) : null}
                  {typeof artifact.metadata.sandbox_candidate_id === "string" ? (
                    <button
                      type="button"
                      className="dde-action"
                      data-testid={`source-validate_sandbox-${artifact.artifactId}`}
                      disabled={busy}
                      onClick={() => onArtifactAction("validate_sandbox", artifact.artifactId)}
                    >
                      validate sandbox
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <Unavailable availability="EMPTY" reason="No source artifacts are indexed for this project." />
        )}
      </section>
      <section data-testid="source-templates">
        <h3>Template recommendations</h3>
        {templates.length ? templates.map((template) => (
          <article key={template.templateId} className="dde-source-artifact-card">
            <strong>{template.title}</strong>
            <span data-state={template.status}>{template.status}</span>
            {template.hardFailures.length ? <small>{template.hardFailures.join(", ")}</small> : null}
          </article>
        )) : <span className="dde-muted">No recommendations have been computed.</span>}
      </section>
      <section data-testid="source-target-blend">
        <h3>Target blend for next candidate</h3>
        <p className="dde-muted">
          Scope <code>{targetBlendScope}</code>. This preference influences future
          generation only; it never rewrites actual attribution.
        </p>
        {providers.map((provider) => (
          <label key={provider.providerKey} className="dde-source-blend-row">
            <span>{provider.displayName}</span>
            <input
              type="number"
              min={0}
              max={100}
              step={5}
              data-testid={`source-blend-${provider.providerKey}`}
              value={blendDraft[provider.providerKey] ?? 0}
              onChange={(event) => {
                const value = Math.max(0, Math.min(100, Number(event.target.value) || 0));
                setBlendDraft((current) => ({ ...current, [provider.providerKey]: value }));
              }}
            />
            <span>%</span>
          </label>
        ))}
        <div className="dde-chip-row">
          <span data-testid="source-blend-total" data-state={blendTotal === 100 ? "PASS" : "PARTIAL"}>
            Total {blendTotal}%
          </span>
          <button
            type="button"
            className="dde-action"
            data-testid="source-blend-apply"
            disabled={busy || blendTotal !== 100}
            onClick={() =>
              onTargetBlendChange(
                Object.fromEntries(
                  Object.entries(blendDraft).map(([key, value]) => [key, value / 100]),
                ),
              )
            }
          >
            Apply to future candidates
          </button>
        </div>
        {targetBlend ? (
          <small data-testid="source-blend-saved">Saved · {targetBlend.contentHash.slice(0, 12)}</small>
        ) : (
          <small data-testid="source-blend-unsaved">No target blend is saved for this scope.</small>
        )}
      </section>
      <section data-testid="source-attribution">
        <h3>Actual attribution for selection</h3>
        {provenance.length ? provenance.map((record) => (
          <div key={record.provenanceId} className="dde-source-attribution-row">
            <span>{record.usageKind}</span>
            <code>{record.artifactId ?? record.sourceId ?? "project"}</code>
            <span>{record.attributionWeight === null ? "weight unknown" : `${Math.round(record.attributionWeight * 100)}%`}</span>
            <span>{record.licenseState} · {record.securityState}</span>
          </div>
        )) : <span className="dde-muted">No attributable source provenance for the current selection.</span>}
      </section>
    </div>
  );
}

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
  auditMatrix,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly auditMatrix: ScreenAuditMatrix | null;
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
      {auditMatrix ? (
        <>
          <p className="dde-muted" data-testid="audit-summary">
            Screen Audit {auditMatrix.summary.currentness} · {auditMatrix.summary.summaryState} · {auditMatrix.summary.blockingFindings} blocking
          </p>
          <table className="dde-table" data-testid="audit-screen-matrix">
            <thead><tr><th>Screen</th><th>Contract</th><th>Journey</th><th>Functional</th><th>State</th><th>A11y</th><th>Visual</th><th>Platform</th></tr></thead>
            <tbody>{auditMatrix.screens.map((screen) => (
              <tr key={screen.pxgKey} data-testid={`audit-screen-${screen.pxgKey}`}>
                <th scope="row">{screen.pxgKey}</th>
                {["CONTRACT","JOURNEY","FUNCTIONAL","STATE","ACCESSIBILITY","VISUAL","RESPONSIVE_PLATFORM"].map((dimension) => (
                  <td key={dimension} data-state={screen.dimensionStates[dimension] ?? "UNKNOWN"}>{screen.dimensionStates[dimension] ?? "UNKNOWN"}</td>
                ))}
              </tr>
            ))}</tbody>
          </table>
        </>
      ) : <p className="dde-muted">Screen Audit has not been evaluated.</p>}
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
  auditMatrix,
  activeCandidateId,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly auditMatrix: ScreenAuditMatrix | null;
  readonly activeCandidateId: string | null;
}) {
  if (!snapshot) {
    return <Unavailable availability="UNAVAILABLE" reason="Verification inventory is loading." />;
  }
  const cards = snapshot.candidates.cards.filter(
    (candidate) =>
      candidate.verificationRequestId !== null || candidate.verificationRunId !== null,
  );
  if (!cards.length && !auditMatrix?.findings.length) {
    return <Unavailable availability="EMPTY" reason="No audit findings or candidate verification runs exist yet." />;
  }
  return (
    <div className="dde-coverage-mode" data-testid="qa-mode">
      <h2 className="dde-panel-heading">QA findings & verification</h2>
      {auditMatrix?.findings.length ? <AuditFindingList findings={auditMatrix.findings} /> : null}
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

function AuditFindingList({ findings }: { readonly findings: readonly ScreenAuditFinding[] }) {
  return <div data-testid="audit-findings">{findings.map((finding) => (
    <article key={finding.findingId} className="dde-qa-candidate" data-severity={finding.severity}>
      <div className="dde-qa-heading"><strong>{finding.findingType}</strong><span>{finding.severity}</span><span>{finding.assessmentState}</span></div>
      <p>{finding.message}</p><span className="dde-muted">{finding.pxgKey ?? finding.nodeKey ?? "project"} · {finding.dimension} · {finding.ruleId}</span>
    </article>
  ))}</div>;
}

function ArchitectureMode({ auditMatrix }: { readonly auditMatrix: ScreenAuditMatrix | null }) {
  if (!auditMatrix) return <Unavailable availability="NOT_CONFIGURED" reason="Run Screen Audit to populate architecture overlays." />;
  const findings = auditMatrix.findings.filter((item) => ["JOURNEY","NAVIGATION","DRIFT","ROLE","RESPONSIVE_PLATFORM"].includes(item.dimension));
  return <div className="dde-coverage-mode" data-testid="architecture-audit-mode"><h2 className="dde-panel-heading">Experience graph audit overlays</h2><p className="dde-muted">Derived from PXG/Contract audit evidence; no demo graph is fabricated.</p>{findings.length ? <AuditFindingList findings={findings} /> : <p data-state="PASS">No current architecture findings.</p>}</div>;
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
        className="dde-candidate-score"
        data-testid={`candidate-score-${candidate.candidateId}`}
        data-state={candidate.scoreState}
        title={candidate.scoreHardFailures.join(", ") || undefined}
      >
        {candidate.score === null
          ? candidate.scoreClassification
          : `${Math.round(candidate.score)}% · ${candidate.scoreClassification}`}
        {candidate.scoreEvidenceRefs.length
          ? ` · ${candidate.scoreEvidenceRefs.length} evidence`
          : ""}
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
