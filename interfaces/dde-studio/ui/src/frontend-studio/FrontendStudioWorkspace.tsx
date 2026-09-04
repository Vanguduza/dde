/**
 * The central work surface. Modes change what the workspace shows without
 * navigating away, per the locked composition (section 5).
 *
 * Where a mode's backing domain does not exist yet, it says so in the
 * mode's own terms rather than rendering an empty canvas that looks like a
 * finished feature with no data.
 */

import { Unavailable } from "../components/Honest";
import type { FrontendStudioSnapshot, StudioMode } from "../state/projections";

export interface WorkspaceProps {
  readonly mode: StudioMode;
  readonly snapshot: FrontendStudioSnapshot | null;
}

export function FrontendStudioWorkspace({ mode, snapshot }: WorkspaceProps) {
  return (
    <div className="dde-workspace-inner" data-mode={mode}>
      <CanvasToolbar mode={mode} />
      <div className="dde-canvas" data-testid="canvas">
        {mode === "coverage" ? (
          <CoverageMode snapshot={snapshot} />
        ) : mode === "design" ? (
          <DesignMode />
        ) : (
          <Unavailable
            availability="NOT_IMPLEMENTED"
            reason={MODE_REASON[mode]}
          />
        )}
      </div>
      <CandidateStrip />
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

function CanvasToolbar({ mode }: { readonly mode: StudioMode }) {
  return (
    <div className="dde-canvas-toolbar" data-testid="canvas-toolbar" role="toolbar" aria-label="Canvas tools">
      <select
        className="dde-viewport"
        data-testid="viewport-select"
        aria-label="Preview viewport"
        defaultValue="1440"
      >
        <option value="1440">Desktop 1440</option>
        <option value="1024">Tablet 1024</option>
        <option value="390">Mobile 390</option>
      </select>
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

function DesignMode() {
  return (
    <Unavailable
      availability="NOT_IMPLEMENTED"
      reason="The candidate preview runtime is DDE-069 M9. Candidates, mutations and locks are real and governed; rendering one on this canvas is not built, and a screenshot shown here would not be a live preview."
    />
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

/**
 * CA-01..CA-09. The strip is a permanent concept in the locked
 * composition, so it is present — but with no preview runtime there is
 * nothing to render in a card, and inventing Direction A/B/C placeholders
 * with scores would be exactly the theatre the mission forbids.
 */
function CandidateStrip() {
  return (
    <div className="dde-candidate-strip" data-testid="candidate-strip">
      <Unavailable
        availability="NOT_IMPLEMENTED"
        reason="Candidate cards need thumbnails from the preview runtime (DDE-069 M9) and scores from a CandidateScorecard (M8). Neither exists, so no card is shown rather than a placeholder carrying an invented score."
      />
    </div>
  );
}
