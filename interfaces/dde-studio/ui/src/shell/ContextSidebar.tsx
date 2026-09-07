/**
 * Project explorer (EX-02..EX-22) and the Orchestrator card (OR-01..OR-06).
 *
 * Groups whose backing domain does not exist are listed with an unknown
 * count rather than hidden. Showing the real information architecture with
 * honest gaps beats a shorter, tidier lie about what the product does.
 */

import { useMemo, useState } from "react";
import { Count } from "../components/Honest";
import { displaySlug } from "../state/projections";
import type {
  CountValue,
  ExplorerGroup,
  OrchestratorFrontendStatus,
  ProjectExplorerSnapshot,
  ScreenAuditMatrix,
} from "../state/projections";

export interface ContextSidebarProps {
  readonly explorer: ProjectExplorerSnapshot | null;
  readonly auditMatrix: ScreenAuditMatrix | null;
  readonly orchestrator: OrchestratorFrontendStatus | null;
  readonly projectSlug: string | null;
  readonly selectedGroup: string | null;
  readonly onSelectGroup: (key: string) => void;
}

export function ContextSidebar({
  explorer,
  auditMatrix,
  orchestrator,
  projectSlug,
  selectedGroup,
  onSelectGroup,
}: ContextSidebarProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const groups = useMemo(() => {
    const source = [...(explorer?.groups ?? []).filter((group) => group.key !== "qa")];
    source.push(qaExplorerGroup(auditMatrix));
    return query.trim() ? source.map((group) => filterGroup(group, query)).filter(Boolean) as ExplorerGroup[] : source;
  }, [explorer, auditMatrix, query]);
  return (
    <div className="dde-explorer-inner">
      <div className="dde-explorer-header">
        <span className="dde-explorer-title" data-testid="explorer-project-heading">
          {displaySlug(projectSlug) ?? "No project"}
        </span>
        <button
          type="button"
          className="dde-icon-button"
          aria-label="Search project"
          aria-expanded={searchOpen}
          data-testid="explorer-search"
          onClick={() => setSearchOpen((value) => !value)}
        >
          <span aria-hidden="true">⌕</span>
        </button>
      </div>
      {searchOpen ? (
        <input
          type="search"
          className="dde-explorer-search-input"
          data-testid="explorer-search-input"
          value={query}
          autoFocus
          placeholder="Filter project tree"
          onChange={(event) => setQuery(event.target.value)}
        />
      ) : null}

      <ul className="dde-explorer-groups" data-testid="explorer-groups">
        {groups.map((group) => (
          <GroupRow
            key={group.key}
            group={group}
            selectedKey={selectedGroup}
            onSelect={onSelectGroup}
          />
        ))}
      </ul>

      <OrchestratorCard status={orchestrator} />
    </div>
  );
}

function filterGroup(group: ExplorerGroup, rawQuery: string): ExplorerGroup | null {
  const query = rawQuery.trim().toLowerCase();
  const children = (group.children ?? [])
    .map((child) => filterGroup(child, query))
    .filter(Boolean) as ExplorerGroup[];
  if (group.title.toLowerCase().includes(query) || group.key.toLowerCase().includes(query) || children.length) {
    return { ...group, children };
  }
  return null;
}

function GroupRow({
  group,
  selectedKey,
  onSelect,
}: {
  readonly group: ExplorerGroup;
  readonly selectedKey: string | null;
  readonly onSelect: (key: string) => void;
}) {
  const selected = group.key === selectedKey;
  const unavailable = group.count.value === null;
  const [expanded, setExpanded] = useState(true);
  return (
    <li>
      <button
        type="button"
        className="dde-explorer-group"
        data-active={selected}
        data-unavailable={unavailable}
        data-testid={`explorer-group-${group.key}`}
        aria-current={selected ? "true" : undefined}
        aria-expanded={group.children?.length ? expanded : undefined}
        onClick={() => {
          onSelect(group.key);
          if (group.children?.length) setExpanded((value) => !value);
        }}
      >
        <span className="dde-explorer-group-title">{group.title}</span>
        <Count value={group.count} />
      </button>
      {group.children?.length && expanded ? (
        <ul className="dde-explorer-children" data-testid={`explorer-children-${group.key}`}>
          {group.children.map((child) => (
            <GroupRow
              key={child.key}
              group={child}
              selectedKey={selectedKey}
              onSelect={onSelect}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function qaExplorerGroup(auditMatrix: ScreenAuditMatrix | null): ExplorerGroup {
  if (!auditMatrix) {
    const unknown: CountValue = {
      value: null,
      availability: "UNAVAILABLE",
      reason: "Screen Audit matrix is unavailable for the current project.",
    };
    return {
      key: "qa",
      title: "QA",
      count: unknown,
      children: [
        { key: "qa:issues", title: "QA Issues", count: unknown },
        { key: "qa:accessibility", title: "Accessibility", count: unknown },
      ],
    };
  }
  const issueCount: CountValue = {
    value: auditMatrix.summary.unresolvedFindings,
    availability: auditMatrix.summary.unresolvedFindings ? "AVAILABLE" : "EMPTY",
  };
  const accessibilityAssessed = auditMatrix.screens.every((screen) => {
    const state = screen.dimensionStates.ACCESSIBILITY;
    return Boolean(state && !["UNKNOWN", "UNASSESSED", "NOT_EVALUATED"].includes(state));
  });
  const accessibilityFindings = auditMatrix.findings.filter(
    (finding) => finding.dimension === "ACCESSIBILITY" && finding.status !== "RESOLVED",
  ).length;
  const accessibilityCount: CountValue = accessibilityAssessed
    ? { value: accessibilityFindings, availability: accessibilityFindings ? "AVAILABLE" : "EMPTY" }
    : { value: null, availability: "UNAVAILABLE", reason: "Accessibility is not evaluated for every current audited screen." };
  return {
    key: "qa",
    title: "QA",
    count: issueCount,
    children: [
      { key: "qa:issues", title: "QA Issues", count: issueCount },
      { key: "qa:accessibility", title: "Accessibility", count: accessibilityCount },
    ],
  };
}

/**
 * OR-01..OR-06. Desired, configured and serving are three separate rows and
 * are never collapsed. Blueprint Rev 3 section 5.4 makes serving identity
 * claimable only from ModelServingEvidence; with no such source implemented
 * the card says "Unattested" rather than repeating the configured name in a
 * third slot and implying it was observed.
 */
function OrchestratorCard({
  status,
}: {
  readonly status: OrchestratorFrontendStatus | null;
}) {
  if (!status) {
    return (
      <div className="dde-orchestrator" data-testid="orchestrator-card">
        <span className="dde-orchestrator-state" data-state="UNKNOWN">
          Orchestrator: unknown
        </span>
      </div>
    );
  }
  return (
    <div className="dde-orchestrator" data-testid="orchestrator-card">
      <div className="dde-orchestrator-header">
        <span
          className="dde-status-dot"
          data-state={status.runtimeState}
          data-testid="orchestrator-dot"
          aria-hidden="true"
        />
        <span className="dde-orchestrator-state">
          Orchestrator: {status.runtimeState}
        </span>
      </div>
      {status.roles.map((role) => (
        <dl
          key={role.role}
          className="dde-role"
          data-testid={`role-${role.role}`}
        >
          <div>
            <dt>Desired</dt>
            <dd>{role.desired ?? "—"}</dd>
          </div>
          <div>
            <dt>Configured</dt>
            <dd>{role.configured ?? "—"}</dd>
          </div>
          <div>
            <dt>Serving</dt>
            <dd data-confidence={role.servingConfidence}>
              {role.serving ?? role.servingConfidence}
            </dd>
          </div>
        </dl>
      ))}
      <div className="dde-design-director" data-testid="design-director-state">
        <span>Design Director</span>
        <strong>{status.designDirector ?? "UNASSIGNED"}</strong>
      </div>
      <div className="dde-orchestrator-activity" data-testid="orchestrator-activity">
        {status.activityWindow.length ? (
          status.activityWindow.map((event, index) => (
            <span
              key={`${event.occurredAt}-${index}`}
              className="dde-activity-bar"
              title={`${event.eventType} · ${event.occurredAt}`}
              aria-label={event.eventType}
            />
          ))
        ) : (
          <span className="dde-muted">No recent activity</span>
        )}
      </div>
      {status.reason ? (
        <p className="dde-orchestrator-reason">{status.reason}</p>
      ) : null}
    </div>
  );
}
