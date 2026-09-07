/** Global top bar (binding matrix rows TB-01..TB-14). */

import { useState } from "react";
import { Count } from "../components/Honest";
import {
  type AttentionItemView,
  type CoverageSummary,
  type FrontendHostContext,
  type FrontendProjectOption,
  type FrontendStudioSnapshot,
  STUDIO_MODES,
  type StudioMode,
  formatCoverage,
  displaySlug,
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
  readonly context: FrontendHostContext | null;
  readonly mode: StudioMode;
  readonly onModeChange: (mode: StudioMode) => void;
  readonly onProjectSwitch: (project: FrontendProjectOption) => void;
  readonly onHelp: () => void;
  readonly onAcknowledgeAttention?: (item: AttentionItemView) => void;
}

export function GlobalTopBar({
  snapshot,
  context,
  mode,
  onModeChange,
  onProjectSwitch,
  onHelp,
  onAcknowledgeAttention,
}: GlobalTopBarProps) {
  const [activityOpen, setActivityOpen] = useState(false);
  const [attentionOpen, setAttentionOpen] = useState(false);
  const projects = context?.availableProjects ?? [];
  const activity = snapshot?.orchestrator.activityWindow ?? [];
  const principal = context?.principalSlug ?? null;
  const principalGlyph = principal?.trim().slice(0, 1).toUpperCase() ?? "?";

  return (
    <div className="dde-topbar-inner">
      <div className="dde-topbar-identity">
        <span className="dde-product">DDE</span>
        <span className="dde-module">Frontend Studio</span>
        <select
          className="dde-project-selector"
          data-testid="project-selector"
          aria-label="Active project"
          value={context?.projectId ?? ""}
          disabled={!context || projects.length === 0}
          onChange={(event) => {
            const target = projects.find((item) => item.projectId === event.target.value);
            if (target?.available) onProjectSwitch(target);
          }}
        >
          {!context ? <option value="">No project</option> : null}
          {projects.map((project) => (
            <option
              key={project.projectId}
              value={project.projectId}
              disabled={!project.available}
              title={project.reason ?? undefined}
            >
              {displaySlug(project.projectSlug) ?? project.projectSlug}{project.available ? "" : " — unavailable"}
            </option>
          ))}
        </select>
        <SyncChip snapshot={snapshot} />
        <SavedStamp snapshot={snapshot} />
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
        <div className="dde-topbar-popover-anchor">
          <button
            type="button"
            className="dde-icon-button"
            data-testid="activity-button"
            aria-label={`Project activity: ${activity.length} recent event(s)`}
            aria-expanded={activityOpen}
            onClick={() => setActivityOpen((value) => !value)}
          >
            ≋
          </button>
          {activityOpen ? (
            <div className="dde-topbar-popover" data-testid="activity-popover">
              <strong>Recent project activity</strong>
              {activity.length ? (
                <ol className="dde-activity-list">
                  {activity.map((item, index) => (
                    <li key={`${item.occurredAt}-${index}`} title={item.occurredAt}>
                      <span className="dde-activity-pulse" aria-hidden="true" />
                      <span>{item.eventType}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <span className="dde-muted">No retained project activity</span>
              )}
            </div>
          ) : null}
        </div>
        <AttentionBadge
          snapshot={snapshot}
          open={attentionOpen}
          onToggle={() => setAttentionOpen((value) => !value)}
          onAcknowledge={onAcknowledgeAttention}
        />
        <button
          type="button"
          className="dde-icon-button"
          data-testid="help-button"
          aria-label="Open Frontend Studio help"
          disabled={!context?.helpRef}
          onClick={onHelp}
        >
          ?
        </button>
        <span
          className="dde-principal-avatar"
          data-testid="principal-avatar"
          data-known={Boolean(principal)}
          title={principal ? `Signed in as ${principal}` : "Principal unavailable"}
          aria-label={principal ? `Signed in as ${principal}` : "Principal unavailable"}
        >
          {principalGlyph}
        </span>
      </div>
    </div>
  );
}

function SyncChip({ snapshot }: { readonly snapshot: FrontendStudioSnapshot | null }) {
  if (!snapshot) {
    return <span className="dde-sync" data-state="UNKNOWN" data-testid="sync-chip">Unknown</span>;
  }
  const { sync } = snapshot;
  const pending = sync.pendingMutationCount > 0;
  const state = pending ? "PENDING" : sync.state;
  return (
    <span
      className="dde-sync"
      data-state={state}
      data-testid="sync-chip"
      title={pending
        ? `${sync.pendingMutationCount} local mutation(s) not yet durable`
        : `durable at PXG revision ${sync.durablePxgRevision}`}
    >
      {pending ? `Pending (${sync.pendingMutationCount})` : state}
    </span>
  );
}

function SavedStamp({ snapshot }: { readonly snapshot: FrontendStudioSnapshot | null }) {
  const savedAt = snapshot?.sync.durableRevisionAt ?? null;
  if (!savedAt) {
    return (
      <span className="dde-saved-at dde-muted" data-testid="saved-at" data-known="false" title="No durable frontend revision has been observed yet.">
        Saved —
      </span>
    );
  }
  const clock = savedAt.length >= 16 ? savedAt.slice(11, 16) : savedAt;
  return (
    <span className="dde-saved-at dde-muted" data-testid="saved-at" data-known="true" title={`Durable frontend revision observed at ${savedAt}`}>
      Saved {clock} UTC
    </span>
  );
}

function CoverageRing({ coverage }: { readonly coverage: CoverageSummary | null }) {
  if (!coverage) {
    return <span className="dde-coverage" data-state="UNASSESSED" data-testid="coverage-ring">—</span>;
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

function AttentionBadge({
  snapshot,
  open,
  onToggle,
  onAcknowledge,
}: {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly open: boolean;
  readonly onToggle: () => void;
  readonly onAcknowledge?: (item: AttentionItemView) => void;
}) {
  const attention = snapshot?.attention;
  const items = attention?.items ?? [];
  return (
    <div className="dde-topbar-popover-anchor">
      <button
        type="button"
        className="dde-attention"
        data-testid="attention-badge"
        data-empty={!attention || attention.count.value === 0}
        aria-label={`Attention centre: ${attention?.count.value ?? "unknown"} item(s)`}
        aria-expanded={open}
        onClick={onToggle}
      >
        Attention {attention && attention.count.value !== 0 ? <Count value={attention.count} /> : null}
      </button>
      {open ? (
        <div className="dde-topbar-popover" data-testid="attention-popover">
          <strong>Attention</strong>
          {items.length ? (
            <ul className="dde-attention-list">
              {items.map((item, index) => (
                <li key={`${item.category}-${item.pxgKey ?? "project"}-${index}`}>
                  <span>{item.detail}</span>
                  {onAcknowledge ? (
                    <button type="button" onClick={() => onAcknowledge(item)}>Acknowledge</button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <span className="dde-muted">Nothing currently needs attention</span>
          )}
        </div>
      ) : null}
    </div>
  );
}
