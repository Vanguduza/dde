/**
 * Inspector (IN-01..IN-16).
 *
 * Property editing is backed by descriptors from the mutation engine's
 * token catalogue, so a field only appears when a real governed mutation
 * can write it. With no canvas selection there is nothing to inspect, and
 * that is a designed state rather than a blank panel.
 */

import { Unavailable } from "../components/Honest";

export interface InspectorPanelProps {
  readonly selectedKey: string | null;
}

export function InspectorPanel({ selectedKey }: InspectorPanelProps) {
  if (!selectedKey) {
    return (
      <div className="dde-inspector-inner" data-testid="inspector">
        <div className="dde-panel-header">Inspector</div>
        <Unavailable
          availability="EMPTY"
          reason="Select an element on the canvas to inspect it."
        />
      </div>
    );
  }
  return (
    <div className="dde-inspector-inner" data-testid="inspector">
      <div className="dde-panel-header">{selectedKey}</div>
      <Unavailable
        availability="NOT_IMPLEMENTED"
        reason="Stable canvas selection needs the preview instrumentation layer (DDE-069 M9). The mutation path behind these controls is real and governed; the selection that would target it is not wired."
      />
    </div>
  );
}
