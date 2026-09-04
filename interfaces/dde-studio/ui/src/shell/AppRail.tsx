/** Far-left module switcher (EX-01). Icon-first, narrow, persistent. */

export interface RailModule {
  readonly id: string;
  readonly label: string;
  readonly glyph: string;
  readonly available: boolean;
}

export interface AppRailProps {
  readonly modules: readonly RailModule[];
  readonly activeId: string;
  readonly onSelect: (id: string) => void;
}

export function AppRail({ modules, activeId, onSelect }: AppRailProps) {
  return (
    <ul className="dde-rail-list">
      {modules.map((module) => (
        <li key={module.id}>
          <button
            type="button"
            className="dde-rail-item"
            data-active={module.id === activeId}
            data-testid={`rail-${module.id}`}
            disabled={!module.available}
            aria-current={module.id === activeId ? "page" : undefined}
            aria-label={
              module.available
                ? module.label
                : `${module.label} — not available in this build`
            }
            title={module.available ? module.label : `${module.label} — unavailable`}
            onClick={() => onSelect(module.id)}
          >
            <span aria-hidden="true">{module.glyph}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
