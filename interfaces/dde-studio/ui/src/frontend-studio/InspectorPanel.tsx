import { useEffect, useMemo, useState } from "react";
import type { DdeHostBridge } from "../bridge/DdeHostBridge";
import { Unavailable } from "../components/Honest";
import type {
  CandidateCardSnapshot,
  FrontendProvenanceRecord,
  InspectorDescriptor,
  InspectorPropertyDescriptor,
  ScreenAuditMatrix,
} from "../state/projections";

type InspectorTab = "layout" | "style" | "behaviour" | "responsive" | "lock" | "source";
const TABS: readonly { id: InspectorTab; label: string }[] = [
  { id: "layout", label: "Layout" },
  { id: "style", label: "Style" },
  { id: "behaviour", label: "Behaviour" },
  { id: "responsive", label: "Responsive" },
  { id: "lock", label: "Lock" },
  { id: "source", label: "Source/code" },
];

export interface InspectorPanelProps {
  readonly bridge: DdeHostBridge;
  readonly selectedKey: string | null;
  readonly descriptor: InspectorDescriptor | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly applyingProperty: string | null;
  readonly candidate: CandidateCardSnapshot | null;
  readonly auditMatrix: ScreenAuditMatrix | null;
  readonly provenance: readonly FrontendProvenanceRecord[];
  readonly viewport: string;
  readonly lockBusy: boolean;
  readonly onApply: (propertyName: string, value: string) => void;
  readonly onViewportChange: (viewport: string) => void;
  readonly onCreateLock: (kind: "STYLE" | "SECTION") => void;
  readonly onReleaseLock: (lockId: string) => void;
}

export function InspectorPanel(props: InspectorPanelProps) {
  const {
    bridge, selectedKey, descriptor, loading, error, applyingProperty, candidate,
    auditMatrix, provenance, viewport, lockBusy, onApply, onViewportChange,
    onCreateLock, onReleaseLock,
  } = props;
  const [tab, setTab] = useState<InspectorTab>("layout");
  useEffect(() => setTab("layout"), [selectedKey]);

  if (!selectedKey) return <InspectorEmpty />;
  if (loading) return (
    <div className="dde-inspector-inner" data-testid="inspector">
      <div className="dde-panel-header">{selectedKey}</div>
      <p className="dde-inspector-loading">Resolving governed descriptor…</p>
    </div>
  );
  if (!descriptor) return (
    <div className="dde-inspector-inner" data-testid="inspector">
      <div className="dde-panel-header">{selectedKey}</div>
      <Unavailable availability="UNAVAILABLE" reason={error ?? "Inspector descriptor unavailable."} />
    </div>
  );

  return (
    <div className="dde-inspector-inner" data-testid="inspector">
      <div className="dde-panel-header">
        <span>{descriptor.title}</span>
        <span className="dde-inspector-key" title={descriptor.pxgKey}>{descriptor.pxgKey}</span>
      </div>
      <div className="dde-inspector-summary">
        <span>{descriptor.nodeKind}</span>
        <span data-state={descriptor.candidateState}>{descriptor.candidateState}</span>
        <span data-source-mapping={descriptor.sourceMapping}>source {descriptor.sourceMapping.toLowerCase()}</span>
        {descriptor.stale ? <strong>STALE — edits disabled</strong> : null}
      </div>
      <div className="dde-inspector-tabs" role="tablist" aria-label="Inspector sections">
        {TABS.map((item) => (
          <button key={item.id} type="button" role="tab" aria-selected={tab === item.id}
            data-testid={`inspector-tab-${item.id}`} onClick={() => setTab(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
      <div className="dde-inspector-tabpanel" role="tabpanel" data-testid={`inspector-panel-${tab}`}>
        {tab === "layout" ? <LayoutPanel descriptor={descriptor} applyingProperty={applyingProperty} onApply={onApply} /> : null}
        {tab === "style" ? <PropertyGroup properties={descriptor.properties.filter(isStyleProperty)} applyingProperty={applyingProperty} onApply={onApply} empty="No style properties are mapped for this node." /> : null}
        {tab === "behaviour" ? <BehaviourPanel descriptor={descriptor} applyingProperty={applyingProperty} onApply={onApply} /> : null}
        {tab === "responsive" ? <ResponsivePanel viewport={viewport} onViewportChange={onViewportChange} auditMatrix={auditMatrix} descriptor={descriptor} /> : null}
        {tab === "lock" ? <LockPanel descriptor={descriptor} busy={lockBusy} onCreate={onCreateLock} onRelease={onReleaseLock} /> : null}
        {tab === "source" ? <SourcePanel bridge={bridge} descriptor={descriptor} provenance={provenance} auditMatrix={auditMatrix} /> : null}
      </div>
      <AuditSummary descriptor={descriptor} auditMatrix={auditMatrix} />
      <div className="dde-inspector-section" data-testid="inspector-verification-evidence">
        <h3>Current verification evidence</h3>
        <InspectorVerificationEvidence descriptor={descriptor} candidate={candidate} />
      </div>
    </div>
  );
}

function InspectorEmpty() {
  return <div className="dde-inspector-inner" data-testid="inspector">
    <div className="dde-panel-header">Inspector</div>
    <Unavailable availability="EMPTY" reason="Select an instrumented element in the code-backed preview to inspect it." />
  </div>;
}

function LayoutPanel({ descriptor, applyingProperty, onApply }: { readonly descriptor: InspectorDescriptor; readonly applyingProperty: string | null; readonly onApply: (name: string, value: string) => void }) {
  const names = ["layout_type", "direction", "gap", "padding"];
  const rows = names.map((name) => descriptor.properties.find((item) => item.propertyName === name)).filter((item): item is InspectorPropertyDescriptor => Boolean(item));
  return <PropertyGroup properties={rows} applyingProperty={applyingProperty} onApply={onApply} empty="Layout properties are not mapped for this node." />;
}

function BehaviourPanel({ descriptor, applyingProperty, onApply }: { readonly descriptor: InspectorDescriptor; readonly applyingProperty: string | null; readonly onApply: (name: string, value: string) => void }) {
  const rows = descriptor.properties.filter((item) => item.propertyName === "duration" || item.propertyName === "easing");
  return <>
    <div className="dde-inspector-section" data-testid="inspector-animation">
      <h3>Animation</h3>
      <span className="dde-muted">Tokenized duration and easing only. Every edit invalidates current visual evidence.</span>
      <PropertyGroup properties={rows} applyingProperty={applyingProperty} onApply={onApply} empty="No animation reference is mapped for this node." />
    </div>
  </>;
}

function ResponsivePanel({ viewport, onViewportChange, auditMatrix, descriptor }: { readonly viewport: string; readonly onViewportChange: (viewport: string) => void; readonly auditMatrix: ScreenAuditMatrix | null; readonly descriptor: InspectorDescriptor }) {
  const screen = resolveAuditScreen(auditMatrix, descriptor.pxgKey);
  const responsive = screen?.dimensionStates.RESPONSIVE_PLATFORM ?? "UNKNOWN";
  return <div className="dde-inspector-section" data-testid="inspector-responsive">
    <h3>Breakpoint preview</h3>
    <div className="dde-breakpoint-buttons" role="group" aria-label="Responsive breakpoint">
      {[{id:"1440",label:"Desktop"},{id:"1024",label:"Tablet"},{id:"390",label:"Mobile"}].map((item) =>
        <button key={item.id} type="button" className="dde-action" aria-pressed={viewport === item.id}
          data-testid={`inspector-breakpoint-${item.id}`} onClick={() => onViewportChange(item.id)}>{item.label}</button>
      )}
    </div>
    <span data-state={responsive}>Responsive evidence · {responsive}</span>
    <span className="dde-muted">Switching breakpoint starts a new code-backed preview for that viewport; it does not rewrite responsive rules.</span>
  </div>;
}

function LockPanel({ descriptor, busy, onCreate, onRelease }: { readonly descriptor: InspectorDescriptor; readonly busy: boolean; readonly onCreate: (kind: "STYLE" | "SECTION") => void; readonly onRelease: (id: string) => void }) {
  return <div className="dde-inspector-section" data-testid="inspector-locks">
    <h3>Effective locks</h3>
    {descriptor.locks.length ? descriptor.locks.map((lock) => <div key={lock.lockId} className="dde-inspector-lock-row">
      <div><strong>{lock.lockKind}</strong><span>{lock.scopeKey}</span></div>
      <span>{lock.reason}</span>
      <span className="dde-muted">{[lock.blocksSetProperty?"style":null,lock.blocksBehaviour?"behaviour":null,lock.blocksResponsive?"responsive":null].filter(Boolean).join(" · ")}</span>
      <button type="button" className="dde-action" disabled={busy} data-testid={`release-lock-${lock.lockId}`} onClick={() => onRelease(lock.lockId)}>Release</button>
    </div>) : <span className="dde-muted">No effective lock covers this selection.</span>}
    <div className="dde-chip-row">
      <button type="button" className="dde-action" disabled={busy} data-testid="create-style-lock" onClick={() => onCreate("STYLE")}>Style Lock</button>
      <button type="button" className="dde-action" disabled={busy} data-testid="create-section-lock" onClick={() => onCreate("SECTION")}>Section Lock</button>
    </div>
  </div>;
}

function SourcePanel({ bridge, descriptor, provenance, auditMatrix }: { readonly bridge: DdeHostBridge; readonly descriptor: InspectorDescriptor; readonly provenance: readonly FrontendProvenanceRecord[]; readonly auditMatrix: ScreenAuditMatrix | null }) {
  const screen = resolveAuditScreen(auditMatrix, descriptor.pxgKey);
  const accessibility = screen?.dimensionStates.ACCESSIBILITY ?? "UNKNOWN";
  return <>
    <div className="dde-inspector-section" data-testid="inspector-source-code">
      <h3>Source / code</h3>
      {descriptor.sourcePath ? <><code>{descriptor.sourcePath}</code><button type="button" className="dde-action" data-testid="inspector-view-source" onClick={() => void bridge.revealFile({ path: descriptor.sourcePath! })}>View source</button></> : <span className="dde-muted">Source mapping unavailable.</span>}
    </div>
    <div className="dde-inspector-section" data-testid="inspector-provenance">
      <h3>Provenance</h3>
      {provenance.length ? provenance.map((record) => <div key={record.provenanceId} className="dde-source-attribution-row"><strong>{record.usageKind}</strong><span>{record.licenseState} · {record.securityState}</span><code>{record.artifactId ?? record.sourceId ?? "project-native"}</code><span>{record.attributionWeight === null ? "weight unknown" : `${Math.round(record.attributionWeight * 100)}%`}</span></div>) : <span className="dde-muted">No attributable external/source provenance.</span>}
    </div>
    <div className="dde-inspector-section" data-testid="inspector-accessibility">
      <h3>Accessibility</h3>
      <strong data-state={accessibility}>{accessibility === "PASS" ? "AA · No current audit issues" : accessibility === "UNKNOWN" ? "Not evaluated" : accessibility}</strong>
      <span className="dde-muted">This badge is audit evidence, not an inferred score.</span>
    </div>
  </>;
}

function AuditSummary({ descriptor, auditMatrix }: { readonly descriptor: InspectorDescriptor; readonly auditMatrix: ScreenAuditMatrix | null }) {
  const screen = resolveAuditScreen(auditMatrix, descriptor.pxgKey);
  if (!screen) return <div className="dde-inspector-section" data-testid="inspector-audit"><h3>Screen Audit</h3><span data-state="NOT_EVALUATED">Not evaluated.</span></div>;
  const findings = auditMatrix?.findings.filter((item) => item.pxgKey === screen.pxgKey) ?? [];
  return <div className="dde-inspector-section" data-testid="inspector-audit"><h3>Screen Audit</h3><strong data-state={screen.assessmentState}>{screen.assessmentState}</strong><div className="dde-chip-row">{Object.entries(screen.dimensionStates).map(([dimension,state]) => <span key={dimension} className="dde-chip" data-state={state}>{dimension} · {state}</span>)}</div>{findings.length ? <span>{findings.length} unresolved finding(s)</span> : <span data-state="PASS">No current findings.</span>}</div>;
}

function resolveAuditScreen(matrix: ScreenAuditMatrix | null, key: string) {
  return matrix?.screens.find((item) => item.pxgKey === key || key.startsWith(`${item.pxgKey}#`) || key.startsWith(`${item.pxgKey}/`));
}

function PropertyGroup({ properties, applyingProperty, onApply, empty }: { readonly properties: readonly InspectorPropertyDescriptor[]; readonly applyingProperty: string | null; readonly onApply: (name: string, value: string) => void; readonly empty: string }) {
  if (!properties.length) return <span className="dde-muted">{empty}</span>;
  return <div className="dde-inspector-properties">{properties.map((property) => <PropertyControl key={property.propertyName} property={property} busy={applyingProperty === property.propertyName} onApply={onApply} />)}</div>;
}

function isStyleProperty(property: InspectorPropertyDescriptor) {
  return ["color", "radius", "shadow", "type", "z_index"].includes(property.propertyName);
}

function InspectorVerificationEvidence({ descriptor, candidate }: { readonly descriptor: InspectorDescriptor; readonly candidate: CandidateCardSnapshot | null }) {
  if (!candidate?.verificationRunId) {
    const stale = candidate?.verificationRequestState === "SUPERSEDED" || candidate?.state === "DIRTY" || candidate?.stale;
    return <span data-state={stale ? "STALE" : "NOT_EVALUATED"}>{stale ? "Evidence stale — re-verification required." : "Not evaluated."}</span>;
  }
  const required = new Set(descriptor.requiredVerification);
  const relevant = candidate.verificationChecks.filter((check) => required.has(check.kind));
  const missing = descriptor.requiredVerification.filter((kind) => !relevant.some((check) => check.kind === kind));
  const failed = relevant.filter((check) => check.status !== "PASSED");
  const current = missing.length === 0 && failed.length === 0;
  return <div><strong data-state={current ? "PASSED" : "INCOMPLETE"}>{current ? "Current screen evidence: PASSED" : "Current evidence incomplete"}</strong><div className="dde-chip-row">{relevant.map((check) => <span key={check.checkRef} className="dde-chip" data-state={check.status}>{check.kind} · {check.status}</span>)}{missing.map((kind) => <span key={kind} className="dde-chip" data-state="MISSING">{kind} · MISSING</span>)}</div></div>;
}

function PropertyControl({ property, busy, onApply }: { readonly property: InspectorPropertyDescriptor; readonly busy: boolean; readonly onApply: (propertyName: string, value: string) => void }) {
  const [value, setValue] = useState(property.value ?? "");
  useEffect(() => setValue(property.value ?? ""), [property.value]);
  const label = useMemo(() => ({layout_type:"Type",direction:"Direction",gap:"Gap",padding:"Padding",z_index:"Z index",type:"Typography"}[property.propertyName] ?? property.propertyName), [property.propertyName]);
  const computed = property.value ? `${property.value}${property.computedValue && property.computedValue !== property.value ? ` · ${property.computedValue}` : ""}` : "Not set";
  return <div className="dde-inspector-property" data-testid={`inspector-property-${property.propertyName}`} data-writable={property.writable}>
    <div className="dde-inspector-property-heading"><label htmlFor={`dde-property-${property.propertyName}`}>{label}</label><span className="dde-computed-value">{computed}</span></div>
    <div className="dde-inspector-property-editor"><select id={`dde-property-${property.propertyName}`} value={value} disabled={!property.writable || busy || !property.legalValues.length} onChange={(event) => setValue(event.target.value)}><option value="">Not set</option>{property.legalValues.map((item) => <option key={item} value={item}>{item}</option>)}</select><button type="button" className="dde-action" data-testid={`apply-${property.propertyName}`} disabled={!property.writable || busy || !value || value === property.value} onClick={() => onApply(property.propertyName, value)}>{busy ? "Applying…" : "Apply"}</button></div>
    {!property.writable ? <span className="dde-property-refusal">{property.lockReason ?? "Candidate state does not permit this edit."}</span> : null}
    <span className="dde-property-impact">{property.accessibilityEffect} · invalidates {property.previewInvalidation.join(", ")}</span>
  </div>;
}
