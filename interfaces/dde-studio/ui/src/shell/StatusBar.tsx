/** Global status bar (ST-01..ST-06). Counts are real or an em-dash. */

import type { FrontendStudioSnapshot, ScreenAuditMatrix } from "../state/projections";

export interface StatusBarProps {
  readonly snapshot: FrontendStudioSnapshot | null;
  readonly breadcrumb: readonly string[];
  readonly buildVersion: string | null;
  readonly auditMatrix: ScreenAuditMatrix | null;
}

export function StatusBar({ snapshot, breadcrumb, buildVersion, auditMatrix }: StatusBarProps) {
  const warnings = auditMatrix
    ? auditMatrix.findings.filter((item) => item.severity === "WARNING" && item.status !== "RESOLVED").length
    : null;
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
        <span data-testid="warning-count">{warnings === null ? "Warnings —" : warnings === 0 ? "No warnings" : `${warnings} warnings`}</span>
        <span data-testid="build-version">
          {buildVersion ?? "build —"} · PXG r{snapshot?.pxgRevision ?? "—"}
        </span>
      </div>
    </div>
  );
}
