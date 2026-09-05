import { useMemo, useState } from "react";
import type { FrontendChatThread } from "../state/projections";

export interface FrontendChatComposerProps {
  readonly thread: FrontendChatThread | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly busy: boolean;
  readonly screenKey: string | null;
  readonly candidateId: string | null;
  readonly candidateLabel: string | null;
  readonly selectedKey: string | null;
  readonly viewport: string;
  readonly includeSelection: boolean;
  readonly onIncludeSelectionChange: (value: boolean) => void;
  readonly onSend: (text: string) => Promise<boolean>;
}

export function FrontendChatComposer({
  thread,
  loading,
  error,
  busy,
  screenKey,
  candidateId,
  candidateLabel,
  selectedKey,
  viewport,
  includeSelection,
  onIncludeSelectionChange,
  onSend,
}: FrontendChatComposerProps) {
  const [text, setText] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const visibleTurns = useMemo(() => thread?.turns ?? [], [thread]);

  const submit = async () => {
    const message = text.trim();
    if (!message || busy) return;
    const accepted = await onSend(message);
    if (accepted) {
      setText("");
      setExpanded(true);
    }
  };

  return (
    <section className="dde-chat" data-testid="frontend-chat" aria-label="Frontend Chat">
      {expanded ? (
        <div className="dde-chat-thread" data-testid="chat-thread" aria-live="polite">
          <div className="dde-chat-thread-header">
            <strong>Frontend Chat</strong>
            <span className="dde-muted">
              {thread?.conversation ? "persisted thread" : "new thread"}
            </span>
          </div>
          {loading ? <p className="dde-muted">Loading conversation…</p> : null}
          {!loading && !visibleTurns.length ? (
            <p className="dde-muted">
              No turns yet. Deterministic edits use the Mutation Planner; /design uses
              the certified DesignGateway only.
            </p>
          ) : null}
          {visibleTurns.map((turn) => (
            <article
              key={turn.turnId}
              className="dde-chat-turn"
              data-role={turn.role}
              data-outcome={turn.outcome}
              data-testid={`chat-turn-${turn.sequence}`}
            >
              <div className="dde-chat-turn-meta">
                <span>{turn.role === "user" ? "You" : "Studio"}</span>
                <span>{turn.intent}</span>
                <span>{turn.outcome}</span>
              </div>
              <p>{turn.text}</p>
              {turn.refusalCode ? (
                <span className="dde-chat-refusal">
                  {turn.refusalCode}
                  {turn.refusalDetail ? ` — ${turn.refusalDetail}` : ""}
                </span>
              ) : null}
            </article>
          ))}
          {error ? (
            <div className="dde-chat-error" role="alert" data-testid="chat-error">
              {error}
            </div>
          ) : null}
        </div>
      ) : null}

      {settingsOpen ? (
        <div className="dde-chat-settings" data-testid="chat-context-settings">
          <div>
            <strong>Conversation context</strong>
            <p className="dde-muted">
              Scope is persisted on the FrontendConversation before a turn is routed.
            </p>
          </div>
          <dl>
            <div>
              <dt>Screen</dt>
              <dd>{screenKey ?? "Not selected"}</dd>
            </div>
            <div>
              <dt>Candidate</dt>
              <dd>{candidateLabel ?? candidateId ?? "Not selected"}</dd>
            </div>
            <div>
              <dt>Viewport</dt>
              <dd>{viewportLabel(viewport)}</dd>
            </div>
            <div>
              <dt>Design provider</dt>
              <dd>Resolved by intent; /design checks certified provider availability.</dd>
            </div>
          </dl>
        </div>
      ) : null}

      <div className="dde-chat-context" data-testid="chat-context-chips">
        {includeSelection && selectedKey ? (
          <span className="dde-chat-chip" data-testid="chat-selection-chip">
            <span title={selectedKey}>{shortKey(selectedKey)}</span>
            <button
              type="button"
              aria-label="Remove selected element from Chat scope"
              onClick={() => onIncludeSelectionChange(false)}
            >
              ×
            </button>
          </span>
        ) : selectedKey ? (
          <button
            type="button"
            className="dde-chat-chip dde-chat-chip-muted"
            data-testid="chat-selection-excluded"
            onClick={() => onIncludeSelectionChange(true)}
          >
            + selection
          </button>
        ) : null}
        {screenKey ? <span className="dde-chat-chip">{shortKey(screenKey)}</span> : null}
        {candidateLabel || candidateId ? (
          <span className="dde-chat-chip">{candidateLabel ?? shortId(candidateId!)}</span>
        ) : null}
        <span className="dde-chat-chip">{viewportLabel(viewport)}</span>
      </div>

      <div className="dde-chat-composer">
        <button
          type="button"
          className="dde-chat-icon"
          aria-label={expanded ? "Hide Frontend Chat thread" : "Show Frontend Chat thread"}
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          ◫
        </button>
        <textarea
          data-testid="chat-input"
          aria-label="Frontend Chat prompt"
          rows={1}
          value={text}
          disabled={busy}
          placeholder="Ask, inspect, edit, or /design…"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
        />
        <button
          type="button"
          className="dde-chat-icon"
          data-testid="chat-settings"
          aria-label="Chat context settings"
          aria-expanded={settingsOpen}
          onClick={() => setSettingsOpen((value) => !value)}
        >
          ≛
        </button>
        <button
          type="button"
          className="dde-chat-send"
          data-testid="chat-send"
          disabled={busy || !text.trim()}
          onClick={() => void submit()}
        >
          {busy ? "…" : "Send"}
        </button>
      </div>
    </section>
  );
}

function shortKey(value: string): string {
  const hash = value.split("#").at(-1);
  return hash && hash !== value ? hash : (value.split("/").at(-1) ?? value);
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

function viewportLabel(viewport: string): string {
  if (viewport === "1440" || viewport === "desktop-1440") return "Desktop 1440";
  if (viewport === "1024" || viewport === "tablet-1024") return "Tablet 1024";
  if (viewport === "390" || viewport === "mobile-390") return "Mobile 390";
  return viewport;
}
