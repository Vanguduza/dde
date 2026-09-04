/** Global status bar (ST-01..ST-06). Counts are real or an em-dash. */

import type { FrontendStudioSnapshot } from "../state/projections";

export interface StatusBarProps {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly breadcrumb: readonly string[];
  readonly buildVersion: string | null;
}

export function StatusBar({ snapshot, breadcrumb, buildVersion }: StatusBarProps) {
  const blocking = snapshot?.coverage.blockingFindingCount ?? null;
  return (
    <div className="dde-statusbar-inner">
      <nav className="dde-breadcrumb" aria-label="Selection path" data-testid="breadcrumb">
        {breadcrumb.length === 0 ? (
          <span className="dde-muted">No selection</span>
        ) : (
          breadcrumb.map((segment, index) => (
            <span key={segment}>
              {index > 0 ? <span aria-hidden="true"> / </span> : null}
              {segment}
            </span>
          ))
        )}
      </nav>

      <div className="dde-statusbar-metrics">
        <span data-testid="error-count">
          {blocking === null
            ? "Errors —"
            : blocking === 0
              ? "No errors"
              : `${blocking} blocking`}
        </span>
        <span data-testid="build-version">{buildVersion ?? "build —"}</span>
      </div>
    </div>
  );
}
