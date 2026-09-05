/**
 * The universal DDE shell (locked visual constitution, section 4).
 *
 * Every first-party DDE window uses this composition, so Frontend Studio is
 * the reference implementation rather than a one-off theme. The four-zone
 * geometry lives in `styles/global.css` as a grid over the token
 * measurements, which is what the structural conformance test asserts.
 */

import type { ReactNode } from "react";

export interface DdeShellProps {
  readonly topBar: ReactNode;
  readonly rail: ReactNode;
  readonly explorer: ReactNode;
  readonly workspace: ReactNode;
  readonly inspector: ReactNode;
  readonly statusBar: ReactNode;
  readonly chat?: ReactNode;
  readonly explorerCollapsed?: boolean;
  readonly inspectorCollapsed?: boolean;
}

export function DdeShell({
  topBar,
  rail,
  explorer,
  workspace,
  inspector,
  statusBar,
  chat,
  explorerCollapsed = false,
  inspectorCollapsed = false,
}: DdeShellProps) {
  return (
    <div className="dde-shell" data-testid="dde-shell">
      <header className="dde-topbar" data-testid="dde-topbar">
        {topBar}
      </header>
      <nav className="dde-rail" data-testid="dde-rail" aria-label="DDE modules">
        {rail}
      </nav>
      <aside
        className="dde-explorer"
        data-testid="dde-explorer"
        data-collapsed={explorerCollapsed}
        aria-label="Project explorer"
      >
        {explorer}
      </aside>
      <main className="dde-workspace" data-testid="dde-workspace">
        {workspace}
      </main>
      <aside
        className="dde-inspector"
        data-testid="dde-inspector"
        data-collapsed={inspectorCollapsed}
        aria-label="Inspector"
      >
        {inspector}
      </aside>
      <footer className="dde-statusbar" data-testid="dde-statusbar">
        {statusBar}
      </footer>
      {chat ? (
        <div className="dde-chat-layer" data-testid="dde-chat-layer">
          {chat}
        </div>
      ) : null}
    </div>
  );
}
