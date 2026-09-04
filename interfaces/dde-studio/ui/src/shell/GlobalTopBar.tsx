/**
 * Global top bar (binding matrix rows TB-01..TB-14).
 *
 * Every value here comes from a projection. Where the projection cannot
 * answer, the control renders a typed unavailable state rather than a
 * plausible one — the sync chip in particular never says "Synced" off the
 * back of an accepted command (FS-GAP-022).
 */

import { Count } from "../components/Honest";
import {
  type CoverageSummary,
  type FrontendStudioSnapshot,
  STUDIO_MODES,
  type StudioMode,
  formatCoverage,
} from "../state/projections";

const MODE_LABEL: Record<StudioMode, string> = {
  design: "Design",
  coverage: "Coverage",
  architecture: "Architecture",
  qa: "QA",
  source: "Source",
};

export interface GlobalTopBarProps {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly projectName: string | null;
  readonly mode: StudioMode;
  readonly onModeChange: (mode: StudioMode) => void;
}

export function GlobalTopBar({
  snapshot,
  projectName,
  mode,
  onModeChange,
}: GlobalTopBarProps) {
  return (
    <div className="dde-topbar-inner">
      <div className="dde-topbar-identity">
        <span className="dde-product">DDE</span>
        <span className="dde-module">Frontend Studio</span>
        <button
          type="button"
          className="dde-project-selector"
          data-testid="project-selector"
          aria-label={
            projectName ? `Project: ${projectName}` : "No project selected"
          }
        >
          {projectName ?? "No project"}
        </button>
        <SyncChip snapshot={snapshot} />
      </div>

      <nav className="dde-mode-tabs" aria-label="Workspace mode">
        {STUDIO_MODES.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={item === mode}
            className="dde-mode-tab"
            data-active={item === mode}
            data-testid={`mode-${item}`}
            onClick={() => onModeChange(item)}
          >
            {MODE_LABEL[item]}
          </button>
        ))}
      </nav>

      <div className="dde-topbar-status">
        <CoverageRing coverage={snapshot?.coverage ?? null} />
        <AttentionBadge snapshot={snapshot} />
      </div>
    </div>
  );
}

/**
 * TB-04. A 202 command acceptance is not "Synced". The chip shows the
 * durable state and, when local mutations are outstanding, says so.
 */
function SyncChip({ snapshot }: { readonly snapshot: FrontendStudioSnapshot | null }) {
  if (!snapshot) {
    return (
      <span className="dde-sync" data-state="UNKNOWN" data-testid="sync-chip">
        Unknown
      </span>
    );
  }
  const { sync } = snapshot;
  const pending = sync.pendingMutationCount > 0;
  const state = pending ? "PENDING" : sync.state;
  return (
    <span
      className="dde-sync"
      data-state={state}
      data-testid="sync-chip"
      title={
        pending
          ? `${sync.pendingMutationCount} local mutation(s) not yet durable`
          : `durable at PXG revision ${sync.durablePxgRevision}`
      }
    >
      {pending ? `Pending (${sync.pendingMutationCount})` : state}
    </span>
  );
}

/**
 * TB-10. Renders an em-dash whenever the summary carries no number —
 * unassessed, partially assessed, blocked or stale. One percentage must
 * never launder a project nobody has checked.
 */
function CoverageRing({ coverage }: { readonly coverage: CoverageSummary | null }) {
  if (!coverage) {
    return (
      <span className="dde-coverage" data-state="UNASSESSED" data-testid="coverage-ring">
        —
      </span>
    );
  }
  const title = coverage.stale
    ? (coverage.reason ?? "coverage is stale")
    : coverage.summaryState === "ASSESSED"
      ? `assessed against contract v${coverage.contractVersion}`
      : `coverage is ${coverage.summaryState.toLowerCase()}`;
  return (
    <span
      className="dde-coverage"
      data-state={coverage.summaryState}
      data-stale={coverage.stale}
      data-testid="coverage-ring"
      title={title}
      aria-label={`Coverage: ${formatCoverage(coverage)} (${title})`}
    >
      {formatCoverage(coverage)}
    </span>
  );
}

/** TB-12. Zero real items means no badge; unknown is never shown as a count. */
function AttentionBadge({
  snapshot,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
}) {
  const attention = snapshot?.attention;
  if (!attention || attention.count.value === 0) {
    return (
      <button
        type="button"
        className="dde-attention"
        data-testid="attention-badge"
        data-empty="true"
        aria-label="Attention centre: nothing needs attention"
      >
        Attention
      </button>
    );
  }
  return (
    <button
      type="button"
      className="dde-attention"
      data-testid="attention-badge"
      data-empty="false"
      aria-label={`Attention centre: ${attention.count.value ?? "unknown"} item(s)`}
    >
      Attention <Count value={attention.count} />
    </button>
  );
}
