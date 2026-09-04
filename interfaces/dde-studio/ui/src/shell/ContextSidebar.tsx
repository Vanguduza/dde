/**
 * Project explorer (EX-02..EX-22) and the Orchestrator card (OR-01..OR-06).
 *
 * Groups whose backing domain does not exist are listed with an unknown
 * count rather than hidden. Showing the real information architecture with
 * honest gaps beats a shorter, tidier lie about what the product does.
 */

import { Count } from "../components/Honest";
import type {
  ExplorerGroup,
  OrchestratorFrontendStatus,
  ProjectExplorerSnapshot,
} from "../state/projections";

export interface ContextSidebarProps {
  readonly explorer: ProjectExplorerSnapshot | null;
  readonly orchestrator: OrchestratorFrontendStatus | null;
  readonly selectedGroup: string | null;
  readonly onSelectGroup: (key: string) => void;
}

export function ContextSidebar({
  explorer,
  orchestrator,
  selectedGroup,
  onSelectGroup,
}: ContextSidebarProps) {
  return (
    <div className="dde-explorer-inner">
      <div className="dde-explorer-header">
        <span className="dde-explorer-title">Project</span>
        <button
          type="button"
          className="dde-icon-button"
          aria-label="Search project"
          data-testid="explorer-search"
        >
          <span aria-hidden="true">⌕</span>
        </button>
      </div>

      <ul className="dde-explorer-groups" data-testid="explorer-groups">
        {(explorer?.groups ?? []).map((group) => (
          <GroupRow
            key={group.key}
            group={group}
            selected={group.key === selectedGroup}
            onSelect={onSelectGroup}
          />
        ))}
      </ul>

      <OrchestratorCard status={orchestrator} />
    </div>
  );
}

function GroupRow({
  group,
  selected,
  onSelect,
}: {
  readonly group: ExplorerGroup;
  readonly selected: boolean;
  readonly onSelect: (key: string) => void;
}) {
  const unavailable = group.count.value === null;
  return (
    <li>
      <button
        type="button"
        className="dde-explorer-group"
        data-active={selected}
        data-unavailable={unavailable}
        data-testid={`explorer-group-${group.key}`}
        aria-current={selected ? "true" : undefined}
        onClick={() => onSelect(group.key)}
      >
        <span className="dde-explorer-group-title">{group.title}</span>
        <Count value={group.count} />
      </button>
    </li>
  );
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
      {status.reason ? (
        <p className="dde-orchestrator-reason">{status.reason}</p>
      ) : null}
    </div>
  );
}
