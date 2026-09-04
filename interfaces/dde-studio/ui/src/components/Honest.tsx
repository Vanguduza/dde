/**
 * Primitives for rendering state that may honestly be unknown.
 *
 * These exist so "we do not know" has one consistent, accessible
 * presentation across the whole workbench, and so no component has to
 * invent a fallback. A count with no backing renders an em-dash carrying
 * the reason, never `0`; an action the system cannot perform renders
 * disabled with the reason attached, never enabled-and-hopeful.
 */

import type { ReactNode } from "react";
import {
  type Availability,
  type CountValue,
  UNKNOWN_MARK,
  formatCount,
} from "../state/projections";

export function Count({ value }: { readonly value: CountValue }) {
  const known = value.value !== null;
  return (
    <span
      className="dde-count"
      data-known={known}
      data-availability={value.availability}
      title={known ? undefined : (value.reason ?? "unavailable")}
      aria-label={
        known
          ? undefined
          : `count unavailable: ${value.reason ?? "not implemented"}`
      }
    >
      {formatCount(value)}
    </span>
  );
}

const AVAILABILITY_LABEL: Record<Availability, string> = {
  AVAILABLE: "Available",
  EMPTY: "None",
  NOT_CONFIGURED: "Not configured",
  NOT_IMPLEMENTED: "Not available in this build",
  UNAVAILABLE: "Unavailable",
  DEGRADED: "Degraded",
};

/**
 * The typed unavailable state a golden control renders when its backing
 * capability is absent. It says which kind of absence it is, because
 * "not configured" and "broken" call for different actions.
 */
export function Unavailable({
  availability,
  reason,
}: {
  readonly availability: Availability;
  readonly reason?: string | null;
}) {
  return (
    <div
      className="dde-unavailable"
      role="status"
      data-availability={availability}
    >
      <span className="dde-unavailable-label">
        {AVAILABILITY_LABEL[availability]}
      </span>
      {reason ? <span className="dde-unavailable-reason">{reason}</span> : null}
    </div>
  );
}

/**
 * A control whose capability is absent. Rendered visibly disabled with the
 * reason on the element itself rather than hidden: hiding it would make the
 * product look complete while removing the user's ability to find out why
 * it is not.
 */
export function DisabledAction({
  label,
  reason,
  children,
}: {
  readonly label: string;
  readonly reason: string;
  readonly children?: ReactNode;
}) {
  return (
    <button
      type="button"
      className="dde-action"
      disabled
      title={reason}
      aria-label={`${label} — unavailable: ${reason}`}
      data-unavailable-reason={reason}
    >
      {children ?? label}
    </button>
  );
}

export function EmDash() {
  return <span aria-hidden="true">{UNKNOWN_MARK}</span>;
}
