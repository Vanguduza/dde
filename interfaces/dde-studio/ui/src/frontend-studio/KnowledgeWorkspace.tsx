import { useMemo, useState } from "react";

import type {
  VeklKnowledgeEdgeView,
  VeklKnowledgeNodeView,
  VeklProjection,
  VeklResourceView,
  VeklTruthChallengeView,
} from "../state/projections";

export type KnowledgeChallengeDecision =
  | "ACCEPT"
  | "DEFER"
  | "REJECT"
  | "REQUEST_MORE_EVIDENCE";

export interface KnowledgeWorkspaceProps {
  readonly projection: VeklProjection | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly onRefresh: () => void;
  readonly onChallengeDecision: (
    challengeId: string,
    decision: KnowledgeChallengeDecision,
    reason: string,
  ) => Promise<void>;
  readonly onChallengeReopen: (challengeId: string, reason: string) => Promise<void>;
}

const SECTION_LABELS: Readonly<Record<string, string>> = {
  stack_map: "Stack Map",
  knowledge: "Knowledge",
  tools_plugins_mcp: "Tools / Plugins / MCP",
  rules_hooks: "Rules / Hooks",
  loops: "Loops",
  community_evidence: "Community Evidence",
  security: "Security",
  learning: "Learning",
};

const TERMINAL_REVIEW_STATES = new Set([
  "REJECTED",
  "DEFERRED",
  "MORE_EVIDENCE_REQUIRED",
]);

const TOPOLOGY_OVERLAYS = [
  "ALL",
  "TRUTH",
  "EXECUTION",
  "CONTRACTS",
  "RESOURCES",
  "PRODUCT",
] as const;
type TopologyOverlay = (typeof TOPOLOGY_OVERLAYS)[number];

const OVERLAY_NODE_KINDS: Readonly<Record<Exclude<TopologyOverlay, "ALL">, readonly string[]>> = {
  TRUTH: ["PRODUCT_CONSTITUTION", "REQUIREMENT", "EDR"],
  EXECUTION: ["TASK_GRAPH", "TASK", "DEVELOPMENT_UNIT_PROJECTION", "STACK_FINGERPRINT"],
  CONTRACTS: ["CONTRACT", "API", "EVENT", "SCHEMA"],
  RESOURCES: ["VEKL_RESOURCE", "SOURCE", "SOURCE_ARTIFACT"],
  PRODUCT: ["PXG_NODE", "FRONTEND_CONTRACT_OBLIGATION", "SCREEN", "USER_JOURNEY", "DESIGN_AUTHORITY"],
};

export function KnowledgeWorkspace({
  projection,
  loading,
  error,
  onRefresh,
  onChallengeDecision,
  onChallengeReopen,
}: KnowledgeWorkspaceProps) {
  const graph = projection?.knowledgeGraph ?? null;
  const units = graph?.unitMaps ?? [];
  const challenges = graph?.challenges ?? [];
  const activeChallenges = challenges.filter(
    (item) => !["REJECTED", "DEFERRED", "TRUTH_CHANGED", "STALE"].includes(item.status),
  );
  const [selectedChallengeId, setSelectedChallengeId] = useState<string | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const [reviewError, setReviewError] = useState<string | null>(null);
  const selectedChallenge = useMemo(
    () => challenges.find((item) => item.challengeId === selectedChallengeId) ?? null,
    [challenges, selectedChallengeId],
  );

  const decide = async (
    challenge: VeklTruthChallengeView,
    decision: KnowledgeChallengeDecision,
  ) => {
    const reason = reviewReason.trim();
    if (!reason) {
      setReviewError("A review rationale or evidence request is required.");
      return;
    }
    setReviewError(null);
    try {
      await onChallengeDecision(challenge.challengeId, decision, reason);
      setReviewReason("");
    } catch (decisionError) {
      setReviewError(decisionError instanceof Error ? decisionError.message : String(decisionError));
    }
  };

  const reopen = async (challenge: VeklTruthChallengeView) => {
    const reason = reviewReason.trim();
    if (!reason) {
      setReviewError("A material reopen trigger or owner reconsideration reason is required.");
      return;
    }
    setReviewError(null);
    try {
      await onChallengeReopen(challenge.challengeId, reason);
      setReviewReason("");
    } catch (reopenError) {
      setReviewError(reopenError instanceof Error ? reopenError.message : String(reopenError));
    }
  };

  return (
    <div className="dde-knowledge-workspace" data-testid="dde-knowledge-workspace">
      <header className="dde-knowledge-header">
        <div>
          <span className="dde-eyebrow">Production VEKL</span>
          <h1>Unit Knowledge Graph</h1>
          <p>
            Deterministic, project-scoped engineering knowledge compiled from current
            Project Truth, TaskGraph, stack, product experience and qualified resources.
          </p>
        </div>
        <button type="button" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error ? <div className="dde-knowledge-alert">{error}</div> : null}
      {graph?.availability === "UNAVAILABLE" ? (
        <div className="dde-knowledge-alert">{graph.reason ?? "Knowledge graph unavailable."}</div>
      ) : null}

      <section className="dde-knowledge-metrics" aria-label="Knowledge status">
        <Metric label="Units" value={units.length} />
        <Metric label="Graph nodes" value={graph?.knowledgeNodes.length ?? 0} />
        <Metric label="Graph edges" value={graph?.knowledgeEdges.length ?? 0} />
        <Metric label="Active challenges" value={activeChallenges.length} />
        <Metric label="Qualified resources" value={projection?.resources.length ?? 0} />
      </section>

      <section className="dde-knowledge-panel">
        <div className="dde-knowledge-panel-title">
          <h2>Development Units</h2>
          <span>{graph?.graphSnapshotHash ? shortHash(graph.graphSnapshotHash) : "No graph snapshot"}</span>
        </div>
        {units.length === 0 ? (
          <EmptyState text="No active Unit Knowledge Maps are persisted for this target project." />
        ) : (
          <div className="dde-knowledge-unit-grid" data-testid="knowledge-unit-grid">
            {units.map((unit) => (
              <article className="dde-knowledge-unit" key={unit.unitMapId}>
                <div className="dde-knowledge-unit-topline">
                  <strong>{unit.objective || unit.unitLineageId}</strong>
                  <span data-state={unit.knowledgeReadinessState}>
                    {unit.knowledgeReadinessState}
                  </span>
                </div>
                <p>{unit.taskIds.length} task{unit.taskIds.length === 1 ? "" : "s"}</p>
                <code title={unit.unitRevisionHash}>{shortHash(unit.unitRevisionHash)}</code>
                {unit.invalidationReasons.length ? (
                  <small data-state="STALE">{unit.invalidationReasons.join(" · ")}</small>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>

      <TopologyExplorer
        nodes={graph?.knowledgeNodes ?? []}
        edges={graph?.knowledgeEdges ?? []}
        units={units}
        researchFindings={graph?.researchFindings ?? []}
        invalidations={graph?.graphInvalidations ?? []}
        resolutionTraces={graph?.resolutionTraces ?? []}
      />

      <section className="dde-knowledge-panel">
        <div className="dde-knowledge-panel-title">
          <h2>Truth Challenges</h2>
          <span>{challenges.length} recorded</span>
        </div>
        {challenges.length === 0 ? (
          <EmptyState text="No governed Project Truth challenges are recorded." />
        ) : (
          <div className="dde-knowledge-challenge-layout">
            <div className="dde-knowledge-table" role="table" aria-label="Truth challenges">
              {challenges.map((challenge) => (
                <button
                  type="button"
                  className="dde-knowledge-table-row dde-knowledge-challenge-row"
                  data-testid={`knowledge-challenge-${challenge.challengeId}`}
                  data-active={challenge.challengeId === selectedChallengeId}
                  role="row"
                  key={challenge.challengeId}
                  onClick={() => {
                    setSelectedChallengeId(challenge.challengeId);
                    setReviewReason("");
                    setReviewError(null);
                  }}
                >
                  <span>{challenge.challengeClass}</span>
                  <strong>{challenge.severity}</strong>
                  <span data-state={challenge.status}>{challenge.status}</span>
                  <code>{shortHash(challenge.currentTruthHash)}</code>
                </button>
              ))}
            </div>
            {selectedChallenge ? (
              <ChallengeReview
                challenge={selectedChallenge}
                reason={reviewReason}
                error={reviewError}
                busy={loading}
                onReasonChange={setReviewReason}
                onDecision={(decision) => void decide(selectedChallenge, decision)}
                onReopen={() => void reopen(selectedChallenge)}
              />
            ) : (
              <EmptyState text="Select a challenge to inspect evidence, impact and governed actions." />
            )}
          </div>
        )}
      </section>

      <section className="dde-knowledge-resource-sections">
        {Object.entries(SECTION_LABELS).map(([key, label]) => (
          <ResourceSection
            key={key}
            label={label}
            resources={projection?.sections[key] ?? []}
          />
        ))}
      </section>
    </div>
  );
}

function TopologyExplorer({
  nodes,
  edges,
  units,
  researchFindings,
  invalidations,
  resolutionTraces,
}: {
  readonly nodes: readonly VeklKnowledgeNodeView[];
  readonly edges: readonly VeklKnowledgeEdgeView[];
  readonly units: readonly { readonly unitMapId: string; readonly objective: string }[];
  readonly researchFindings: readonly Readonly<Record<string, unknown>>[];
  readonly invalidations: readonly Readonly<Record<string, unknown>>[];
  readonly resolutionTraces: readonly Readonly<Record<string, unknown>>[];
}) {
  const [overlay, setOverlay] = useState<TopologyOverlay>("ALL");
  const [unitMapId, setUnitMapId] = useState("");
  const [relationship, setRelationship] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const byId = useMemo(
    () => new Map(nodes.map((node) => [node.knowledgeNodeId, node])),
    [nodes],
  );
  const unitNodeId = useMemo(() => {
    if (!unitMapId) return null;
    return nodes.find(
      (node) => node.nodeKind === "DEVELOPMENT_UNIT_PROJECTION" && node.objectId === unitMapId,
    )?.knowledgeNodeId ?? null;
  }, [nodes, unitMapId]);
  const neighbourhood = useMemo(() => {
    if (!unitNodeId) return null;
    const ids = new Set<string>([unitNodeId]);
    for (const edge of edges) {
      if (edge.fromNodeId === unitNodeId) ids.add(edge.toNodeId);
      if (edge.toNodeId === unitNodeId) ids.add(edge.fromNodeId);
    }
    return ids;
  }, [edges, unitNodeId]);
  const allowedKinds = overlay === "ALL" ? null : new Set(OVERLAY_NODE_KINDS[overlay]);
  const visibleNodes = nodes.filter((node) =>
    (!allowedKinds || allowedKinds.has(node.nodeKind)) && (!neighbourhood || neighbourhood.has(node.knowledgeNodeId)),
  );
  const visibleNodeIds = new Set(visibleNodes.map((node) => node.knowledgeNodeId));
  const relationships = Array.from(new Set(edges.map((edge) => edge.relationship))).sort();
  const visibleEdges = edges.filter(
    (edge) =>
      visibleNodeIds.has(edge.fromNodeId) &&
      visibleNodeIds.has(edge.toNodeId) &&
      (!relationship || edge.relationship === relationship),
  );
  const selectedNode = selectedNodeId ? byId.get(selectedNodeId) ?? null : null;

  return (
    <section className="dde-knowledge-panel" data-testid="knowledge-topology">
      <div className="dde-knowledge-panel-title">
        <div>
          <h2>Graph topology & evidence</h2>
          <span>{visibleNodes.length} nodes · {visibleEdges.length} edges</span>
        </div>
        <code>{nodes.length ? "rebuildable projection" : "no graph"}</code>
      </div>
      <div className="dde-knowledge-topology-controls">
        <label>
          <span>Unit neighbourhood</span>
          <select data-testid="knowledge-unit-filter" value={unitMapId} onChange={(event) => setUnitMapId(event.target.value)}>
            <option value="">All Units</option>
            {units.map((unit) => (
              <option key={unit.unitMapId} value={unit.unitMapId}>
                {unit.objective || unit.unitMapId}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Overlay</span>
          <select data-testid="knowledge-overlay-filter" value={overlay} onChange={(event) => setOverlay(event.target.value as TopologyOverlay)}>
            {TOPOLOGY_OVERLAYS.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Relationship</span>
          <select data-testid="knowledge-relationship-filter" value={relationship} onChange={(event) => setRelationship(event.target.value)}>
            <option value="">All relationships</option>
            {relationships.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
          </select>
        </label>
      </div>
      {visibleNodes.length === 0 ? (
        <EmptyState text="No graph nodes match the selected Unit/overlay filters." />
      ) : (
        <div className="dde-knowledge-topology-layout">
          <div className="dde-knowledge-node-list" aria-label="Knowledge graph nodes">
            {visibleNodes.slice(0, 80).map((node) => (
              <button
                type="button"
                key={node.knowledgeNodeId}
                data-testid={`knowledge-node-${node.knowledgeNodeId}`}
                data-active={selectedNodeId === node.knowledgeNodeId}
                onClick={() => setSelectedNodeId(node.knowledgeNodeId)}
              >
                <strong>{node.nodeKind}</strong>
                <span>{node.stableRef}</span>
                <small>{node.authorityClass}</small>
              </button>
            ))}
          </div>
          <div className="dde-knowledge-edge-list" aria-label="Knowledge graph edges">
            {visibleEdges.slice(0, 100).map((edge) => (
              <div key={edge.knowledgeEdgeId}>
                <span>{nodeLabel(byId.get(edge.fromNodeId))}</span>
                <strong>{humanize(edge.relationship)}</strong>
                <span>{nodeLabel(byId.get(edge.toNodeId))}</span>
              </div>
            ))}
          </div>
          <aside className="dde-knowledge-node-inspector" data-testid="knowledge-node-inspector">
            {selectedNode ? (
              <>
                <span className="dde-eyebrow">Node authority</span>
                <h3>{selectedNode.nodeKind}</h3>
                <ReviewDatum label="Stable reference" value={selectedNode.stableRef} />
                <ReviewDatum label="Authority class" value={selectedNode.authorityClass} />
                <ReviewDatum label="Authority service" value={selectedNode.authorityService ?? "Not recorded"} />
                <ReviewDatum label="Content hash" value={selectedNode.contentHash} code />
                <ReviewDatum label="Metadata" value={summarize(selectedNode.metadata ?? {})} />
              </>
            ) : (
              <EmptyState text="Select a node to inspect its authority and provenance metadata." />
            )}
          </aside>
        </div>
      )}
      <div className="dde-knowledge-evidence-metrics" aria-label="Knowledge evidence inventory">
        <Metric label="Research findings" value={researchFindings.length} />
        <Metric label="Graph invalidations" value={invalidations.length} />
        <Metric label="Resolution traces" value={resolutionTraces.length} />
      </div>
      {resolutionTraces.length ? (
        <div className="dde-knowledge-evidence-list" data-testid="knowledge-resolution-evidence">
          {resolutionTraces.slice(-12).reverse().map((trace, index) => (
            <div key={String(trace.resolutionTraceId ?? trace.traceHash ?? index)}>
              <strong>Resolution {shortHash(String(trace.traceHash ?? "unknown"))}</strong>
              <span>Unit {shortHash(String(trace.unitRevisionHash ?? "unknown"))}</span>
              <span>{Array.isArray(trace.candidateDecisions) ? trace.candidateDecisions.length : 0} candidate decisions</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function nodeLabel(node: VeklKnowledgeNodeView | undefined): string {
  if (!node) return "Unknown node";
  return `${node.nodeKind}: ${node.stableRef}`;
}

function ChallengeReview({
  challenge,
  reason,
  error,
  busy,
  onReasonChange,
  onDecision,
  onReopen,
}: {
  readonly challenge: VeklTruthChallengeView;
  readonly reason: string;
  readonly error: string | null;
  readonly busy: boolean;
  readonly onReasonChange: (value: string) => void;
  readonly onDecision: (decision: KnowledgeChallengeDecision) => void;
  readonly onReopen: () => void;
}) {
  const reviewable = challenge.status === "REVIEW_REQUIRED";
  const reopenable = TERMINAL_REVIEW_STATES.has(challenge.status);
  return (
    <article className="dde-knowledge-challenge-review" data-testid="knowledge-challenge-review">
      <div className="dde-knowledge-panel-title">
        <div>
          <span className="dde-eyebrow">Governed review</span>
          <h3>{challenge.challengeClass}</h3>
        </div>
        <span data-state={challenge.status}>{challenge.status}</span>
      </div>
      <ReviewDatum label="Current truth" value={challenge.currentTruthHash} code />
      <ReviewDatum label="New evidence" value={summarize(challenge.evidence)} />
      <ReviewDatum label="Why conflict exists" value={summarize(challenge.conflict)} />
      <ReviewDatum label="Evidence quality / confidence" value={summarize(challenge.confidence)} />
      <ReviewDatum label="Affected scope" value={summarize(challenge.impact)} />
      <ReviewDatum label="Proposed exact truth patch" value={summarize(challenge.proposal)} />
      <ReviewDatum
        label="Migration plan"
        value={summarizeRecordMember(challenge.proposal, "migration_plan")}
      />
      <ReviewDatum
        label="Verification plan"
        value={summarizeRecordMember(challenge.proposal, "verification_plan")}
      />
      {challenge.reopenConditions.length ? (
        <ReviewDatum label="Reopen conditions" value={challenge.reopenConditions.join(" · ")} />
      ) : null}
      {challenge.decision ? (
        <ReviewDatum
          label="Recorded decision"
          value={`${challenge.decision}${challenge.decisionReason ? ` — ${challenge.decisionReason}` : ""}`}
        />
      ) : null}
      {(reviewable || reopenable) ? (
        <div className="dde-knowledge-review-controls">
          <label>
            <span>{reopenable ? "Reopen trigger" : "Decision rationale / evidence request"}</span>
            <textarea
              rows={3}
              value={reason}
              disabled={busy}
              data-testid="knowledge-challenge-reason"
              onChange={(event) => onReasonChange(event.target.value)}
            />
          </label>
          {error ? <p role="alert" className="dde-property-refusal">{error}</p> : null}
          {reviewable ? (
            <div className="dde-knowledge-review-actions">
              <button type="button" disabled={busy} onClick={() => onDecision("ACCEPT")}>Accept</button>
              <button type="button" disabled={busy} onClick={() => onDecision("DEFER")}>Defer</button>
              <button type="button" disabled={busy} onClick={() => onDecision("REJECT")}>Reject</button>
              <button
                type="button"
                disabled={busy}
                data-testid="knowledge-challenge-more-evidence"
                onClick={() => onDecision("REQUEST_MORE_EVIDENCE")}
              >
                Request more evidence
              </button>
            </div>
          ) : (
            <button type="button" disabled={busy} data-testid="knowledge-challenge-reopen" onClick={onReopen}>
              Reopen governed review
            </button>
          )}
        </div>
      ) : null}
    </article>
  );
}

function ReviewDatum({
  label,
  value,
  code = false,
}: {
  readonly label: string;
  readonly value: string;
  readonly code?: boolean;
}) {
  return (
    <div className="dde-knowledge-review-datum">
      <strong>{label}</strong>
      {code ? <code title={value}>{shortHash(value)}</code> : <span>{value}</span>}
    </div>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: number }) {
  return (
    <div className="dde-knowledge-metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function ResourceSection({
  label,
  resources,
}: {
  readonly label: string;
  readonly resources: readonly VeklResourceView[];
}) {
  return (
    <article className="dde-knowledge-panel dde-knowledge-resource-panel">
      <div className="dde-knowledge-panel-title">
        <h2>{label}</h2>
        <span>{resources.length}</span>
      </div>
      {resources.length === 0 ? (
        <EmptyState text="No active qualified resources in this section." />
      ) : (
        <div className="dde-knowledge-resource-list">
          {resources.slice(0, 8).map((resource) => (
            <div key={resource.resourceId} className="dde-knowledge-resource">
              <strong>{resource.title}</strong>
              <span>{resource.publisher} · {resource.revision}</span>
              <code>{resource.resourceKind} · {resource.sourceTrust}</code>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function EmptyState({ text }: { readonly text: string }) {
  return <p className="dde-knowledge-empty">{text}</p>;
}

function shortHash(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

function summarize(value: Readonly<Record<string, unknown>>): string {
  const entries = Object.entries(value);
  if (!entries.length) return "None recorded";
  return entries
    .slice(0, 8)
    .map(([key, item]) => `${humanize(key)}: ${summarizeValue(item)}`)
    .join(" · ");
}

function summarizeRecordMember(
  value: Readonly<Record<string, unknown>>,
  key: string,
): string {
  return summarizeValue(value[key]);
}

function summarizeValue(value: unknown): string {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) return value.length ? value.map(summarizeValue).join(", ") : "None";
  if (typeof value === "object") {
    return Object.entries(value as Readonly<Record<string, unknown>>)
      .slice(0, 6)
      .map(([key, item]) => `${humanize(key)}=${summarizeValue(item)}`)
      .join(", ");
  }
  return String(value);
}

function humanize(value: string): string {
  return value.replaceAll("_", " ");
}
