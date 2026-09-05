import { useEffect, useState } from "react";
import type { DdeHostBridge } from "../bridge/DdeHostBridge";
import { Unavailable } from "../components/Honest";
import type {
  CandidateCardSnapshot,
  InspectorDescriptor,
  ScreenAuditMatrix,
  InspectorPropertyDescriptor,
} from "../state/projections";

export interface InspectorPanelProps {
  readonly bridge: DdeHostBridge;
  readonly selectedKey: string | null;
  readonly descriptor: InspectorDescriptor | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly applyingProperty: string | null;
  readonly candidate: CandidateCardSnapshot | null;
  readonly auditMatrix: ScreenAuditMatrix | null;
  readonly onApply: (propertyName: string, value: string) => void;
}

export function InspectorPanel({
  bridge,
  selectedKey,
  descriptor,
  loading,
  error,
  applyingProperty,
  candidate,
  auditMatrix,
  onApply,
}: InspectorPanelProps) {
  if (!selectedKey) {
    return (
      <div className="dde-inspector-inner" data-testid="inspector">
        <div className="dde-panel-header">Inspector</div>
        <Unavailable
          availability="EMPTY"
          reason="Select an instrumented element in the code-backed preview to inspect it."
        />
      </div>
    );
  }
  if (loading) {
    return (
      <div className="dde-inspector-inner" data-testid="inspector">
        <div className="dde-panel-header">{selectedKey}</div>
        <p className="dde-inspector-loading">Resolving governed descriptor…</p>
      </div>
    );
  }
  if (!descriptor) {
    return (
      <div className="dde-inspector-inner" data-testid="inspector">
        <div className="dde-panel-header">{selectedKey}</div>
        <Unavailable
          availability="UNAVAILABLE"
          reason={error ?? "Inspector descriptor unavailable."}
        />
      </div>
    );
  }
  return (
    <div className="dde-inspector-inner" data-testid="inspector">
      <div className="dde-panel-header">
        <span>{descriptor.title}</span>
        <span className="dde-inspector-key" title={descriptor.pxgKey}>
          {descriptor.pxgKey}
        </span>
      </div>
      <div className="dde-inspector-summary">
        <span>{descriptor.nodeKind}</span>
        <span data-state={descriptor.candidateState}>{descriptor.candidateState}</span>
        <span data-source-mapping={descriptor.sourceMapping}>
          source {descriptor.sourceMapping.toLowerCase()}
        </span>
        {descriptor.stale ? <strong>STALE — edits disabled</strong> : null}
      </div>
      <div className="dde-inspector-properties" data-testid="inspector-properties">
        {descriptor.properties.map((property) => (
          <PropertyControl
            key={property.propertyName}
            property={property}
            busy={applyingProperty === property.propertyName}
            onApply={onApply}
          />
        ))}
      </div>
      <div className="dde-inspector-section" data-testid="inspector-audit">
        <h3>Screen Audit</h3>
        {(() => {
          const screen = auditMatrix?.screens.find((item) => item.pxgKey === descriptor.pxgKey || descriptor.pxgKey.startsWith(`${item.pxgKey}#`) || descriptor.pxgKey.startsWith(`${item.pxgKey}/`));
          if (!screen) return <span data-state="NOT_EVALUATED">Not evaluated.</span>;
          const findings = auditMatrix?.findings.filter((item) => item.pxgKey === screen.pxgKey) ?? [];
          return <><strong data-state={screen.assessmentState}>{screen.assessmentState}</strong><div className="dde-chip-row">{Object.entries(screen.dimensionStates).map(([dimension,state]) => <span key={dimension} className="dde-chip" data-state={state}>{dimension} · {state}</span>)}</div>{findings.length ? <span>{findings.length} unresolved finding(s)</span> : <span data-state="PASS">No current findings.</span>}</>;
        })()}
      </div>
      <div className="dde-inspector-section" data-testid="inspector-verification-evidence">
        <h3>Current verification evidence</h3>
        <InspectorVerificationEvidence descriptor={descriptor} candidate={candidate} />
      </div>
      <div className="dde-inspector-section">
        <h3>Verification after edit</h3>
        {descriptor.requiredVerification.length ? (
          <div className="dde-chip-row">
            {descriptor.requiredVerification.map((kind) => (
              <span key={kind} className="dde-chip">
                {kind}
              </span>
            ))}
          </div>
        ) : (
          <span className="dde-muted">No screen verification binding resolved.</span>
        )}
      </div>
      <div className="dde-inspector-section">
        <h3>Source</h3>
        {descriptor.sourcePath ? (
          <>
            <code>{descriptor.sourcePath}</code>
            <button
              type="button"
              className="dde-action"
              onClick={() => void bridge.revealFile({ path: descriptor.sourcePath! })}
            >
              View source
            </button>
          </>
        ) : (
          <span className="dde-muted">Source mapping unavailable.</span>
        )}
      </div>
    </div>
  );
}

function InspectorVerificationEvidence({
  descriptor,
  candidate,
}: {
  readonly descriptor: InspectorDescriptor;
  readonly candidate: CandidateCardSnapshot | null;
}) {
  if (!candidate?.verificationRunId) {
    const stale =
      candidate?.verificationRequestState === "SUPERSEDED" ||
      candidate?.state === "DIRTY" ||
      candidate?.stale;
    return (
      <span data-state={stale ? "STALE" : "NOT_EVALUATED"}>
        {stale ? "Evidence stale — re-verification required." : "Not evaluated."}
      </span>
    );
  }
  const required = new Set(descriptor.requiredVerification);
  const relevant = candidate.verificationChecks.filter((check) => required.has(check.kind));
  const missing = descriptor.requiredVerification.filter(
    (kind) => !relevant.some((check) => check.kind === kind),
  );
  const failed = relevant.filter((check) => check.status !== "PASSED");
  const current = missing.length === 0 && failed.length === 0;
  return (
    <div>
      <strong data-state={current ? "PASSED" : "INCOMPLETE"}>
        {current ? "Current screen evidence: PASSED" : "Current evidence incomplete"}
      </strong>
      <div className="dde-chip-row">
        {relevant.map((check) => (
          <span key={check.checkRef} className="dde-chip" data-state={check.status}>
            {check.kind} · {check.status}
          </span>
        ))}
        {missing.map((kind) => (
          <span key={kind} className="dde-chip" data-state="MISSING">
            {kind} · MISSING
          </span>
        ))}
      </div>
    </div>
  );
}

function PropertyControl({
  property,
  busy,
  onApply,
}: {
  readonly property: InspectorPropertyDescriptor;
  readonly busy: boolean;
  readonly onApply: (propertyName: string, value: string) => void;
}) {
  const initial = property.value ?? property.legalValues[0] ?? "";
  const [value, setValue] = useState(initial);
  useEffect(() => {
    setValue(property.value ?? property.legalValues[0] ?? "");
  }, [property.legalValues, property.value]);
  return (
    <div
      className="dde-inspector-property"
      data-testid={`inspector-property-${property.propertyName}`}
      data-writable={property.writable}
    >
      <div className="dde-inspector-property-heading">
        <label htmlFor={`dde-property-${property.propertyName}`}>
          {property.propertyName}
        </label>
        <span className="dde-computed-value">
          {property.computedValue ?? property.units ?? "token"}
        </span>
      </div>
      <div className="dde-inspector-property-editor">
        <select
          id={`dde-property-${property.propertyName}`}
          value={value}
          disabled={!property.writable || busy || !property.legalValues.length}
          onChange={(event) => setValue(event.target.value)}
        >
          {property.legalValues.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="dde-action"
          data-testid={`apply-${property.propertyName}`}
          disabled={!property.writable || busy || !value || value === property.value}
          onClick={() => onApply(property.propertyName, value)}
        >
          {busy ? "Applying…" : "Apply"}
        </button>
      </div>
      {!property.writable ? (
        <span className="dde-property-refusal">
          {property.lockReason ?? "Candidate state does not permit this edit."}
        </span>
      ) : null}
      <span className="dde-property-impact">
        {property.accessibilityEffect} · invalidates {property.previewInvalidation.join(", ")}
      </span>
    </div>
  );
}
