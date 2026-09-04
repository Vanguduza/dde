/**
 * The Frontend Studio application.
 *
 * It holds no domain state of its own: every value it renders came from a
 * projection through the bridge, and a projection that cannot answer
 * produces a typed unavailable state rather than a default. That is the
 * whole reason the app takes a bridge rather than reaching for a host API.
 */

import { useEffect, useState } from "react";
import type { DdeHostBridge } from "../bridge/DdeHostBridge";
import { AppRail, type RailModule } from "../shell/AppRail";
import { ContextSidebar } from "../shell/ContextSidebar";
import { DdeShell } from "../shell/DdeShell";
import { GlobalTopBar } from "../shell/GlobalTopBar";
import { StatusBar } from "../shell/StatusBar";
import { FrontendStudioWorkspace } from "../frontend-studio/FrontendStudioWorkspace";
import { InspectorPanel } from "../frontend-studio/InspectorPanel";
import type { FrontendStudioSnapshot, StudioMode } from "../state/projections";

const MODULES: readonly RailModule[] = [
  { id: "frontend", label: "Frontend Studio", glyph: "◧", available: true },
  { id: "projects", label: "Projects", glyph: "▤", available: false },
  { id: "models", label: "Models", glyph: "◈", available: false },
  { id: "orchestration", label: "Orchestration", glyph: "⌘", available: false },
  { id: "knowledge", label: "Knowledge", glyph: "◎", available: false },
];

export interface DdeStudioAppProps {
  readonly bridge: DdeHostBridge;
  readonly projectName?: string | null;
  readonly buildVersion?: string | null;
}

export function DdeStudioApp({
  bridge,
  projectName = null,
  buildVersion = null,
}: DdeStudioAppProps) {
  const [snapshot, setSnapshot] = useState<FrontendStudioSnapshot | null>(null);
  const [mode, setMode] = useState<StudioMode>("design");
  const [group, setGroup] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    bridge
      .requestRead<FrontendStudioSnapshot>({ resource: "frontend.studio.snapshot" })
      .then((value) => {
        if (!cancelled) setSnapshot(value);
      })
      .catch((error: unknown) => {
        // A failed read is reported, never silently rendered as an empty
        // project: "no screens" and "we could not ask" are different facts.
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : String(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [bridge]);

  const breadcrumb = group ? ["Project", group] : [];

  return (
    <DdeShell
      topBar={
        <GlobalTopBar
          snapshot={snapshot}
          projectName={projectName}
          mode={mode}
          onModeChange={setMode}
        />
      }
      rail={<AppRail modules={MODULES} activeId="frontend" onSelect={() => {}} />}
      explorer={
        <ContextSidebar
          explorer={snapshot?.explorer ?? null}
          orchestrator={snapshot?.orchestrator ?? null}
          selectedGroup={group}
          onSelectGroup={setGroup}
        />
      }
      workspace={
        loadError ? (
          <div className="dde-workspace-inner">
            <div className="dde-canvas">
              <div className="dde-unavailable" role="alert">
                <span className="dde-unavailable-label">Unavailable</span>
                <span className="dde-unavailable-reason">
                  Could not read the project snapshot: {loadError}
                </span>
              </div>
            </div>
          </div>
        ) : (
          <FrontendStudioWorkspace mode={mode} snapshot={snapshot} />
        )
      }
      inspector={<InspectorPanel selectedKey={null} />}
      statusBar={
        <StatusBar
          snapshot={snapshot}
          breadcrumb={breadcrumb}
          buildVersion={buildVersion ?? snapshot?.sync.buildVersion ?? null}
        />
      }
    />
  );
}
