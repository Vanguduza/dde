import { useEffect, useMemo, useState } from "react";
import type {
  FrontendChatActivity,
  FrontendChatAttachment,
  FrontendChatChange,
  FrontendChatChanges,
  FrontendChatCheckpoint,
  FrontendChatContextBudget,
  FrontendChatConversation,
  FrontendChatMode,
  FrontendChatModelOption,
  FrontendChatPlan,
  FrontendChatPlanStep,
  FrontendChatThread,
} from "../state/projections";

export interface CursorChatController {
  readonly canPickLocalFile: boolean;
  readonly conversations: readonly FrontendChatConversation[];
  readonly attachments: readonly FrontendChatAttachment[];
  readonly pendingAttachmentIds: readonly string[];
  readonly plans: readonly FrontendChatPlan[];
  readonly activities: readonly FrontendChatActivity[];
  readonly checkpoints: readonly FrontendChatCheckpoint[];
  readonly changes: FrontendChatChanges | null;
  readonly models: readonly FrontendChatModelOption[];
  readonly contextBudget: FrontendChatContextBudget | null;
  readonly onNewConversation: () => Promise<void>;
  readonly onSelectConversation: (conversationId: string) => Promise<void>;
  readonly onSearchConversations: (query: string) => Promise<void>;
  readonly onRenameConversation: (title: string) => Promise<void>;
  readonly onArchiveConversation: () => Promise<void>;
  readonly onBranchConversation: (turnId?: string) => Promise<void>;
  readonly onModeChange: (mode: FrontendChatMode) => Promise<void>;
  readonly onModelChange: (modelProfileId: string | null) => Promise<void>;
  readonly onAttachLocalFile: () => Promise<void>;
  readonly onRemoveAttachment: (attachmentId: string) => Promise<void>;
  readonly onCreateCheckpoint: (note?: string) => Promise<void>;
  readonly onRestoreCheckpoint: (checkpointId: string) => Promise<void>;
  readonly onApprovePlan: (plan: FrontendChatPlan) => Promise<void>;
  readonly onRunPlanStep: (
    plan: FrontendChatPlan,
    step: FrontendChatPlanStep,
  ) => Promise<void>;
  readonly onRetryPlanStep: (
    plan: FrontendChatPlan,
    step: FrontendChatPlanStep,
  ) => Promise<void>;
  readonly onCancelPlan: (plan: FrontendChatPlan) => Promise<void>;
  readonly onCancelActivity: (activity: FrontendChatActivity) => Promise<void>;
  readonly onAcceptChange: (change: FrontendChatChange) => Promise<void>;
  readonly onRevertChange: (change: FrontendChatChange) => Promise<void>;
  readonly onRevertAll: () => Promise<void>;
  readonly onApplyPatch: (patch: string) => Promise<void>;
  readonly onPinContext: (ref: string, pinned: boolean) => Promise<void>;
}

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
  readonly cursor: CursorChatController;
}

type DetailTab = "plan" | "activity" | "changes" | "checkpoints" | "context";

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
  cursor,
}: FrontendChatComposerProps) {
  const [text, setText] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [detailTab, setDetailTab] = useState<DetailTab>("plan");
  const [historyQuery, setHistoryQuery] = useState("");
  const [renameValue, setRenameValue] = useState("");
  const [checkpointNote, setCheckpointNote] = useState("");
  const [contextRef, setContextRef] = useState("");
  const [patchText, setPatchText] = useState("");
  const visibleTurns = useMemo(() => thread?.turns ?? [], [thread]);
  const conversation = thread?.conversation ?? null;
  const activePlan = useMemo(
    () =>
      cursor.plans.find((plan) => plan.planId === conversation?.activePlanId) ??
      cursor.plans[0] ??
      null,
    [conversation?.activePlanId, cursor.plans],
  );

  useEffect(() => {
    setRenameValue(conversation?.title ?? "");
  }, [conversation?.conversationId, conversation?.title]);

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
    <section className="dde-chat dde-chat-cursor" data-testid="frontend-chat" aria-label="DDE AI Chat">
      {expanded ? (
        <div className="dde-chat-thread dde-chat-cursor-panel" data-testid="chat-thread" aria-live="polite">
          <header className="dde-chat-thread-header dde-chat-cursor-header">
            <div>
              <strong>{conversation?.title || "DDE AI Chat"}</strong>
              <span className="dde-muted">
                {conversation ? `${conversation.mode} · persisted` : "new thread"}
              </span>
            </div>
            <div className="dde-chat-header-actions">
              <button type="button" data-testid="chat-new" onClick={() => void cursor.onNewConversation()}>
                New
              </button>
              <button
                type="button"
                data-testid="chat-history-toggle"
                aria-expanded={historyOpen}
                onClick={() => setHistoryOpen((value) => !value)}
              >
                History
              </button>
              {conversation ? (
                <button type="button" data-testid="chat-branch" onClick={() => void cursor.onBranchConversation()}>
                  Branch
                </button>
              ) : null}
            </div>
          </header>

          {historyOpen ? (
            <HistoryPanel
              conversations={cursor.conversations}
              query={historyQuery}
              onQueryChange={setHistoryQuery}
              onSearch={() => void cursor.onSearchConversations(historyQuery)}
              onSelect={(id) => void cursor.onSelectConversation(id)}
              activeId={conversation?.conversationId ?? null}
            />
          ) : null}

          <div className="dde-chat-modebar" data-testid="chat-modebar">
            {(["ASK", "PLAN", "EXECUTE"] as const).map((item) => (
              <button
                type="button"
                key={item}
                data-testid={`chat-mode-${item.toLowerCase()}`}
                aria-pressed={conversation?.mode === item}
                className={conversation?.mode === item ? "active" : ""}
                disabled={!conversation || busy}
                onClick={() => void cursor.onModeChange(item)}
              >
                {item === "ASK" ? "Ask" : item === "PLAN" ? "Plan" : "Execute"}
              </button>
            ))}
            <select
              data-testid="chat-model-select"
              aria-label="Chat model or profile"
              value={conversation?.modelProfileId ?? "AUTO"}
              disabled={!conversation || busy}
              onChange={(event) =>
                void cursor.onModelChange(event.target.value === "AUTO" ? null : event.target.value)
              }
            >
              {cursor.models.map((model) => (
                <option key={model.optionId} value={model.optionId}>
                  {model.label} · {model.status}
                </option>
              ))}
            </select>
          </div>

          {conversation ? (
            <div className="dde-chat-title-edit">
              <input
                aria-label="Conversation title"
                value={renameValue}
                onChange={(event) => setRenameValue(event.target.value)}
              />
              <button
                type="button"
                disabled={!renameValue.trim() || renameValue.trim() === (conversation.title ?? "")}
                onClick={() => void cursor.onRenameConversation(renameValue)}
              >
                Rename
              </button>
              <button type="button" onClick={() => void cursor.onArchiveConversation()}>
                Archive
              </button>
            </div>
          ) : null}

          {loading ? <p className="dde-muted">Loading conversation…</p> : null}
          {!loading && !visibleTurns.length ? (
            <p className="dde-muted">
              Ask is read-only. Plan prepares governed commands. Execute runs only admitted DDE operations.
            </p>
          ) : null}
          <div className="dde-chat-turn-list">
            {visibleTurns.map((turn) => (
              <article
                key={turn.turnId}
                className="dde-chat-turn"
                data-role={turn.role}
                data-outcome={turn.outcome}
                data-testid={`chat-turn-${turn.sequence}`}
              >
                <div className="dde-chat-turn-meta">
                  <span>{turn.role === "user" ? "You" : "DDE"}</span>
                  <span>{turn.intent}</span>
                  <span>{turn.outcome}</span>
                  {turn.modelProfileId ? <span>{turn.modelProfileId}</span> : null}
                </div>
                <p>{turn.text}</p>
                {turn.attachmentIds.length ? (
                  <div className="dde-chat-inline-refs">{turn.attachmentIds.length} attachment(s)</div>
                ) : null}
                {turn.planId ? <div className="dde-chat-inline-refs">Plan {shortId(turn.planId)}</div> : null}
                {turn.refusalCode ? (
                  <span className="dde-chat-refusal">
                    {turn.refusalCode}
                    {turn.refusalDetail ? ` — ${turn.refusalDetail}` : ""}
                  </span>
                ) : null}
                {turn.role === "studio" ? (
                  <button
                    className="dde-chat-branch-turn"
                    type="button"
                    onClick={() => void cursor.onBranchConversation(turn.turnId)}
                  >
                    Branch here
                  </button>
                ) : null}
              </article>
            ))}
          </div>

          {error ? (
            <div className="dde-chat-error" role="alert" data-testid="chat-error">
              {error}
            </div>
          ) : null}

          <div className="dde-chat-detail-tabs" role="tablist" aria-label="Chat work details">
            {(["plan", "activity", "changes", "checkpoints", "context"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={detailTab === tab}
                onClick={() => setDetailTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="dde-chat-detail-panel">
            {detailTab === "plan" ? (
              <PlanPanel
                plan={activePlan}
                onApprove={cursor.onApprovePlan}
                onRun={cursor.onRunPlanStep}
                onRetry={cursor.onRetryPlanStep}
                onCancel={cursor.onCancelPlan}
              />
            ) : detailTab === "activity" ? (
              <ActivityPanel activities={cursor.activities} onCancel={cursor.onCancelActivity} />
            ) : detailTab === "changes" ? (
              <ChangesPanel
                changes={cursor.changes}
                checkpoints={cursor.checkpoints}
                patchText={patchText}
                onPatchTextChange={setPatchText}
                onApplyPatch={async () => {
                  await cursor.onApplyPatch(patchText);
                  setPatchText("");
                }}
                onAccept={cursor.onAcceptChange}
                onRevert={cursor.onRevertChange}
                onRevertAll={cursor.onRevertAll}
              />
            ) : detailTab === "checkpoints" ? (
              <CheckpointPanel
                checkpoints={cursor.checkpoints}
                note={checkpointNote}
                onNoteChange={setCheckpointNote}
                onCreate={async () => {
                  await cursor.onCreateCheckpoint(checkpointNote || undefined);
                  setCheckpointNote("");
                }}
                onRestore={cursor.onRestoreCheckpoint}
              />
            ) : (
              <ContextPanel
                conversation={conversation}
                budget={cursor.contextBudget}
                refValue={contextRef}
                onRefValueChange={setContextRef}
                onPin={async () => {
                  if (!contextRef.trim()) return;
                  await cursor.onPinContext(contextRef.trim(), true);
                  setContextRef("");
                }}
                onUnpin={(ref) => cursor.onPinContext(ref, false)}
              />
            )}
          </div>
        </div>
      ) : null}

      {settingsOpen ? (
        <div className="dde-chat-settings" data-testid="chat-context-settings">
          <div>
            <strong>Conversation context</strong>
            <p className="dde-muted">Stable DDE identities are persisted before routing each turn.</p>
          </div>
          <p className="dde-muted">/design checks certified provider availability and never substitutes generic Claude Code.</p>
          <dl>
            <div><dt>Screen</dt><dd>{screenKey ?? "Not selected"}</dd></div>
            <div><dt>Candidate</dt><dd>{candidateLabel ?? candidateId ?? "Not selected"}</dd></div>
            <div><dt>Viewport</dt><dd>{viewportLabel(viewport)}</dd></div>
            <div><dt>Mode</dt><dd>{conversation?.mode ?? "ASK"}</dd></div>
            <div><dt>Model</dt><dd>{conversation?.modelProfileId ?? "Auto"}</dd></div>
          </dl>
        </div>
      ) : null}

      <div className="dde-chat-context" data-testid="chat-context-chips">
        {includeSelection && selectedKey ? (
          <span className="dde-chat-chip" data-testid="chat-selection-chip">
            <span title={selectedKey}>{shortKey(selectedKey)}</span>
            <button type="button" aria-label="Remove selected element from Chat scope" onClick={() => onIncludeSelectionChange(false)}>×</button>
          </span>
        ) : selectedKey ? (
          <button type="button" className="dde-chat-chip dde-chat-chip-muted" data-testid="chat-selection-excluded" onClick={() => onIncludeSelectionChange(true)}>+ selection</button>
        ) : null}
        {screenKey ? <span className="dde-chat-chip">{shortKey(screenKey)}</span> : null}
        {candidateLabel || candidateId ? <span className="dde-chat-chip">{candidateLabel ?? shortId(candidateId!)}</span> : null}
        <span className="dde-chat-chip">{viewportLabel(viewport)}</span>
        {cursor.pendingAttachmentIds.length ? (
          <span className="dde-chat-chip" data-testid="chat-pending-attachments">
            {cursor.pendingAttachmentIds.length} file(s)
          </span>
        ) : null}
      </div>

      <div className="dde-chat-composer">
        <button type="button" className="dde-chat-icon" aria-label={expanded ? "Hide DDE AI Chat" : "Show DDE AI Chat"} aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>◫</button>
        <button
          type="button"
          className="dde-chat-icon"
          data-testid="chat-attach"
          aria-label="Attach local file"
          disabled={!cursor.canPickLocalFile || busy}
          onClick={() => void cursor.onAttachLocalFile()}
        >
          ＋
        </button>
        <textarea
          data-testid="chat-input"
          aria-label="DDE AI Chat prompt"
          rows={1}
          value={text}
          disabled={busy}
          placeholder="Ask, @reference, plan, or execute…"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
        />
        <button type="button" className="dde-chat-icon" data-testid="chat-settings" aria-label="Chat context settings" aria-expanded={settingsOpen} onClick={() => setSettingsOpen((value) => !value)}>≛</button>
        <button type="button" className="dde-chat-send" data-testid="chat-send" disabled={busy || !text.trim()} onClick={() => void submit()}>{busy ? "…" : "Send"}</button>
      </div>

      {cursor.attachments.some((item) => item.status === "ACTIVE" && item.turnId === null) ? (
        <div className="dde-chat-attachment-tray" data-testid="chat-attachment-tray">
          {cursor.attachments
            .filter((item) => item.status === "ACTIVE" && item.turnId === null)
            .map((item) => (
              <span key={item.attachmentId} className="dde-chat-chip">
                {item.filename} · {formatBytes(item.sizeBytes)}
                <button type="button" aria-label={`Remove ${item.filename}`} onClick={() => void cursor.onRemoveAttachment(item.attachmentId)}>×</button>
              </span>
            ))}
        </div>
      ) : null}
    </section>
  );
}

function HistoryPanel({
  conversations,
  query,
  onQueryChange,
  onSearch,
  onSelect,
  activeId,
}: {
  conversations: readonly FrontendChatConversation[];
  query: string;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  onSelect: (id: string) => void;
  activeId: string | null;
}) {
  return (
    <aside className="dde-chat-history" data-testid="chat-history">
      <div className="dde-chat-search">
        <input aria-label="Search chat history" value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") onSearch(); }} />
        <button type="button" onClick={onSearch}>Search</button>
      </div>
      <div className="dde-chat-history-list">
        {conversations.map((item) => (
          <button key={item.conversationId} type="button" className={item.conversationId === activeId ? "active" : ""} onClick={() => onSelect(item.conversationId)}>
            <strong>{item.title || `Chat ${shortId(item.conversationId)}`}</strong>
            <span>{item.mode} · {item.status}</span>
          </button>
        ))}
        {!conversations.length ? <span className="dde-muted">No matching conversations.</span> : null}
      </div>
    </aside>
  );
}

function PlanPanel({
  plan,
  onApprove,
  onRun,
  onRetry,
  onCancel,
}: {
  plan: FrontendChatPlan | null;
  onApprove: (plan: FrontendChatPlan) => Promise<void>;
  onRun: (plan: FrontendChatPlan, step: FrontendChatPlanStep) => Promise<void>;
  onRetry: (plan: FrontendChatPlan, step: FrontendChatPlanStep) => Promise<void>;
  onCancel: (plan: FrontendChatPlan) => Promise<void>;
}) {
  if (!plan) return <p className="dde-muted">No durable plan in this conversation.</p>;
  return (
    <div data-testid="chat-plan-panel">
      <div className="dde-chat-detail-head">
        <div><strong>{plan.title}</strong><span>{plan.state}</span></div>
        {plan.state === "DRAFT" || plan.state === "READY" ? (
          <button type="button" data-testid="chat-plan-approve" onClick={() => void onApprove(plan)}>Approve</button>
        ) : null}
        {!(["COMPLETED", "CANCELLED"] as string[]).includes(plan.state) ? (
          <button type="button" onClick={() => void onCancel(plan)}>Cancel</button>
        ) : null}
      </div>
      <p>{plan.objective}</p>
      <ol className="dde-chat-plan-steps">
        {plan.steps.map((step) => (
          <li key={step.stepId} data-state={step.state}>
            <div><strong>{step.title}</strong><span>{step.state} · attempt {step.attempt}</span></div>
            <p>{step.description}</p>
            {step.commandType ? <code>{step.commandType}</code> : null}
            {step.state === "PENDING" || step.state === "READY" ? (
              <button type="button" data-testid={`chat-plan-run-${step.sequence}`} disabled={!(["APPROVED", "EXECUTING"] as string[]).includes(plan.state)} onClick={() => void onRun(plan, step)}>Run step</button>
            ) : null}
            {(["FAILED", "BLOCKED", "CANCELLED"] as string[]).includes(step.state) ? (
              <button type="button" onClick={() => void onRetry(plan, step)}>Retry</button>
            ) : null}
            {step.errorDetail ? <pre className="dde-chat-error-detail">{step.errorDetail}</pre> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

function ActivityPanel({ activities, onCancel }: { activities: readonly FrontendChatActivity[]; onCancel: (item: FrontendChatActivity) => Promise<void> }) {
  return (
    <div className="dde-chat-activity" data-testid="chat-activity-panel">
      {activities.map((item) => (
        <div key={item.activityId} className="dde-chat-activity-row" data-state={item.state}>
          <div><strong>{item.label}</strong><span>{item.kind} · {item.state}</span></div>
          {item.detail ? <p>{item.detail}</p> : null}
          {item.cancellable && (item.state === "PENDING" || item.state === "RUNNING") ? (
            <button type="button" onClick={() => void onCancel(item)}>Stop</button>
          ) : null}
        </div>
      ))}
      {!activities.length ? <p className="dde-muted">No tool/activity events yet.</p> : null}
    </div>
  );
}

function ChangesPanel({
  changes,
  checkpoints,
  patchText,
  onPatchTextChange,
  onApplyPatch,
  onAccept,
  onRevert,
  onRevertAll,
}: {
  changes: FrontendChatChanges | null;
  checkpoints: readonly FrontendChatCheckpoint[];
  patchText: string;
  onPatchTextChange: (value: string) => void;
  onApplyPatch: () => Promise<void>;
  onAccept: (change: FrontendChatChange) => Promise<void>;
  onRevert: (change: FrontendChatChange) => Promise<void>;
  onRevertAll: () => Promise<void>;
}) {
  if (!changes) return <p className="dde-muted">No active Chat workspace for diff review.</p>;
  const canRevertAll = checkpoints.some((item) => item.diffHash === changes.diffHash);
  return (
    <div data-testid="chat-changes-panel">
      <div className="dde-chat-detail-head"><strong>{changes.changes.length} changed file(s)</strong><span>{shortId(changes.diffHash)}</span></div>
      {changes.changes.map((change) => (
        <article key={change.path} className="dde-chat-change">
          <div className="dde-chat-detail-head"><strong>{change.path}</strong><span>{change.reviewDecision}</span></div>
          <pre>{change.diffText || "(binary or empty diff)"}</pre>
          <div>
            <button type="button" disabled={change.reviewDecision === "ACCEPTED"} onClick={() => void onAccept(change)}>Accept</button>
            <button type="button" onClick={() => void onRevert(change)}>Revert</button>
          </div>
        </article>
      ))}
      <textarea aria-label="Apply unified diff patch" rows={5} value={patchText} onChange={(event) => onPatchTextChange(event.target.value)} placeholder="Paste a unified diff to apply inside the isolated workspace…" />
      <button type="button" disabled={!patchText.trim()} onClick={() => void onApplyPatch()}>Apply patch</button>
      <button type="button" disabled={!canRevertAll || !changes.changes.length} onClick={() => void onRevertAll()}>Revert all to checkpoint</button>
    </div>
  );
}

function CheckpointPanel({ checkpoints, note, onNoteChange, onCreate, onRestore }: { checkpoints: readonly FrontendChatCheckpoint[]; note: string; onNoteChange: (value: string) => void; onCreate: () => Promise<void>; onRestore: (id: string) => Promise<void> }) {
  return (
    <div data-testid="chat-checkpoint-panel">
      <div className="dde-chat-search"><input aria-label="Checkpoint note" value={note} onChange={(event) => onNoteChange(event.target.value)} placeholder="Optional checkpoint note" /><button type="button" onClick={() => void onCreate()}>Checkpoint</button></div>
      {checkpoints.map((item) => (
        <div key={item.checkpointId} className="dde-chat-activity-row">
          <div><strong>{item.note || `Checkpoint ${item.turnSequence}`}</strong><span>{new Date(item.createdAt).toLocaleString()}</span></div>
          <span>context {shortId(item.contextHash)}{item.diffHash ? ` · diff ${shortId(item.diffHash)}` : ""}</span>
          <button type="button" onClick={() => void onRestore(item.checkpointId)}>Restore context</button>
        </div>
      ))}
    </div>
  );
}

function ContextPanel({ conversation, budget, refValue, onRefValueChange, onPin, onUnpin }: { conversation: FrontendChatConversation | null; budget: FrontendChatContextBudget | null; refValue: string; onRefValueChange: (value: string) => void; onPin: () => Promise<void>; onUnpin: (ref: string) => Promise<void> }) {
  return (
    <div data-testid="chat-context-panel">
      <div className="dde-chat-context-budget">
        <strong>Context budget</strong>
        <span>{budget ? `${budget.estimatedTokens.toLocaleString()} / ${budget.budgetTokens.toLocaleString()} tokens` : "Not assembled"}</span>
      </div>
      {budget?.omittedRefs.length ? <div className="dde-chat-refusal">Omitted: {budget.omittedRefs.join(", ")}</div> : null}
      <div className="dde-chat-search"><input aria-label="Pin context reference" value={refValue} onChange={(event) => onRefValueChange(event.target.value)} placeholder="@file:path or @screen:key" /><button type="button" onClick={() => void onPin()}>Pin</button></div>
      <div className="dde-chat-context-pins">
        {conversation?.pinnedContextRefs.map((ref) => (
          <span className="dde-chat-chip" key={ref}>{ref}<button type="button" onClick={() => void onUnpin(ref)}>×</button></span>
        ))}
      </div>
    </div>
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

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}
