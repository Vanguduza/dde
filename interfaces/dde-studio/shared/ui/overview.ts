/**
 * Main Dashboard (Mission Overview) — primary home for DDE Code.
 *
 * Visual composition aligned to docs/dde-mission-overview-mockup.png:
 * header → Core status strip → operator actions → manufacturing spine →
 * three-column body (missions/work | fleet + modules + attention | activity).
 *
 * Live today: Core /healthz+/readyz only. Lists stay empty until Gateway/CLI.
 */

import type { ProbeState } from "../healthClient";
import type { StudioConnection } from "../settings";
import { HARNESS_PROFILES, type HarnessId } from "../stubGateway";
import {
  escapeHtml,
  messageBridgeScript,
  sharedStyles,
} from "./base";

/** Zone ids asserted by tests — keep stable. */
export const OVERVIEW_ZONES = [
  "system",
  "missions",
  "spine",
  "work-in-flight",
  "fleet",
  "approvals",
  "verification",
  "integration",
  "activity",
  "attention",
] as const;

export type OverviewZoneId = (typeof OVERVIEW_ZONES)[number];

const SPINE_STEPS = [
  "Truth",
  "Graph",
  "Context",
  "Route",
  "Run",
  "Verify",
  "Integrate",
  "Evidence",
] as const;

const FLEET_ORDER: HarnessId[] = ["hermes", "claude-code", "deepseek"];

const UNAVAILABLE = "Unavailable";

/** Inline SVG icons (stroke, monochrome) — match mockup density without assets. */
const ICONS = {
  check: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.5" d="M3.5 8.5 6.5 11.5 12.5 4.5"/></svg>`,
  warn: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.5" d="M8 3.5 13.5 13H2.5L8 3.5z"/><path fill="currentColor" d="M7.4 7h1.2v3.2H7.4zm0 4h1.2v1.2H7.4z"/></svg>`,
  book: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M3 3.5h4.5a2 2 0 0 1 2 2v7H5a2 2 0 0 0-2 2v-11zm10 0H8.5a2 2 0 0 0-2 2v7H13a2 2 0 0 1 2 2v-11z"/></svg>`,
  gear: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="2.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path fill="none" stroke="currentColor" stroke-width="1.4" d="M8 1.8v1.6M8 12.6v1.6M1.8 8h1.6M12.6 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M12.6 3.4l-1.1 1.1M4.5 11.5l-1.1 1.1"/></svg>`,
  menu: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M2.5 4h11v1.4H2.5zm0 3.3h11v1.4H2.5zm0 3.3h11V12H2.5z"/></svg>`,
  play: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M5 3.5v9l8-4.5z"/></svg>`,
  pause: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M4 3.5h2.5v9H4zm5.5 0H12v9H9.5z"/></svg>`,
  x: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.6" d="m4 4 8 8M12 4 4 12"/></svg>`,
  refresh: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M13 8a5 5 0 1 1-1.4-3.4"/><path fill="currentColor" d="M13 2.5v3.5H9.5z"/></svg>`,
  plane: `<svg class="ov-ico ov-ico-lg" viewBox="0 0 20 20" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M3 10.5 17 4l-3.5 12-3-3.5L7 16.5 6 12.5z"/></svg>`,
  claude: `<svg class="ov-ico ov-ico-lg" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-width="1.4"/><text x="10" y="13.5" text-anchor="middle" fill="currentColor" font-size="9" font-family="Segoe UI,sans-serif" font-weight="600">C</text></svg>`,
  whale: `<svg class="ov-ico ov-ico-lg" viewBox="0 0 20 20" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M3 11c2-4 6-6 10-5 2 .4 3.5 1.5 4 3.2-1.2.2-2.2.8-2.8 1.8H14c-1.2 2-3.5 3-6 2.2C5.5 12.6 3.8 12 3 11z"/><circle cx="7.5" cy="9.2" r="0.8" fill="currentColor"/></svg>`,
  shield: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M8 2.5 13 4.5v3.2c0 3.2-2.1 5.2-5 6.3-2.9-1.1-5-3.1-5-6.3V4.5L8 2.5z"/></svg>`,
  verify: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path fill="none" stroke="currentColor" stroke-width="1.5" d="m5.2 8.1 1.8 1.8 3.8-3.8"/></svg>`,
  link: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M6.5 9.5 9.5 6.5M7 11.5H5.2A2.7 2.7 0 0 1 5.2 6H7m2 4.5h1.8a2.7 2.7 0 0 0 0-5.5H9"/></svg>`,
  activity: `<svg class="ov-ico" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M2 10.5c2-4 3-6 4-6s2 5 3 5 2-3 3-3 2 2 2 2"/><circle cx="13" cy="4" r="1.2" fill="currentColor"/></svg>`,
  doc: `<svg class="ov-ico ov-ico-empty" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"/><path fill="none" stroke="currentColor" stroke-width="1.4" d="M14 3.5V8h4.5M9 12h6M9 15.5h6"/></svg>`,
  inbox: `<svg class="ov-ico ov-ico-empty" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M4 8h16v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V8zm0 0 2.5-4h11L20 8"/><path fill="none" stroke="currentColor" stroke-width="1.4" d="M4 14h5l1.2 2h3.6L15 14h5"/></svg>`,
  external: `<svg class="ov-ico ov-ico-sm" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.4" d="M6.5 3.5H3.5v9h9v-3M8.5 3.5h4v4M12.5 3.5 7 9"/></svg>`,
} as const;

function fleetIcon(harness: HarnessId): string {
  if (harness === "hermes") return ICONS.plane;
  if (harness === "claude-code") return ICONS.claude;
  return ICONS.whale;
}

/** Minimal empty marker — title optional; no instructional detail. */
function emptyState(opts: {
  title?: string;
  icon?: string;
  label?: string;
}): string {
  const icon = opts.icon ?? ICONS.doc;
  const title = opts.title
    ? `<div class="ov-empty-title">${escapeHtml(opts.title)}</div>`
    : "";
  const label = opts.label ?? opts.title ?? "Empty";
  return `
    <div class="ov-empty" role="status" aria-label="${escapeHtml(label)}">
      ${icon}
      ${title}
    </div>`;
}

function systemStrip(
  connection: StudioConnection | undefined,
  probe: ProbeState,
  configError?: string,
): string {
  const target = connection?.preferredTarget ?? "local";
  const url = connection?.effectiveUrl;
  const urlHtml = url
    ? `<code class="ov-sys-url">${escapeHtml(url)}</code>`
    : `<span class="muted">${escapeHtml(configError ?? "—")}</span>`;

  let statusHtml: string;
  switch (probe.kind) {
    case "ok": {
      const ready = probe.readyz.status === "ready";
      statusHtml = ready
        ? `<span class="ov-sys-ready">${ICONS.check}<strong>Core ready</strong></span>`
        : `<span class="ov-sys-warn">${ICONS.warn}<strong>Core not ready</strong></span>`;
      break;
    }
    case "checking":
      statusHtml = `<span class="muted"><strong>Checking…</strong></span>`;
      break;
    case "unreachable":
      statusHtml = `<span class="ov-sys-err"><strong>Core unreachable</strong></span>`;
      break;
    case "misconfigured":
      statusHtml = `<span class="ov-sys-warn"><strong>Misconfigured</strong></span>`;
      break;
    default:
      statusHtml = `<span class="muted"><strong>Core idle</strong></span>`;
  }

  const tip =
    probe.kind === "unreachable" || probe.kind === "misconfigured"
      ? escapeHtml(probe.error)
      : "";

  const tone =
    probe.kind === "ok" && probe.readyz.status === "ready"
      ? "ok"
      : probe.kind === "unreachable"
        ? "err"
        : probe.kind === "ok" || probe.kind === "misconfigured"
          ? "warn"
          : "idle";

  return `
  <section class="ov-sys ov-sys-tone-${tone}" data-zone="system" aria-label="System status"${tip ? ` title="${tip}"` : ""}>
    <div class="ov-sys-left" role="status" aria-live="polite">
      ${statusHtml}
      <span class="pill ${target === "cloud" ? "" : "ok"}">${escapeHtml(target)}</span>
      ${urlHtml}
    </div>
  </section>`;
}

function missionBucket(
  label: string,
  tone: "active" | "blocked" | "completed",
  bind: string,
  emptyLine: string,
): string {
  return `
    <div class="ov-mission-bucket">
      <h3 class="ov-subhead ov-tone-${tone}">${escapeHtml(label)}</h3>
      <ul class="ov-mission-list" data-bind="${escapeHtml(bind)}" aria-label="${escapeHtml(label)}">
        <li class="muted">${escapeHtml(emptyLine)}</li>
      </ul>
    </div>`;
}

function missionsZone(): string {
  return `
  <section class="ov-panel" data-zone="missions" aria-labelledby="ov-missions">
    <div class="ov-panel-head">
      <h2 id="ov-missions">Missions</h2>
      <button type="button" class="ov-text-btn" data-cmd="openMission">Open Mission</button>
    </div>
    ${missionBucket("Active", "active", "missions-active", "No active missions")}
    ${missionBucket("Blocked", "blocked", "missions-blocked", "No blocked missions")}
    ${missionBucket("Completed", "completed", "missions-completed", "No completed missions")}
  </section>`;
}

function spineZone(): string {
  const steps = SPINE_STEPS.map(
    (s, i) => `
      <li class="ov-spine-step" aria-current="false">
        <span class="ov-spine-index">${i + 1}</span>
        <span class="ov-spine-label">${escapeHtml(s)}</span>
      </li>`,
  ).join("");
  return `
  <section class="ov-spine-wrap" data-zone="spine" aria-labelledby="ov-spine">
    <h2 id="ov-spine" class="ov-visually-hidden">Manufacturing spine</h2>
    <ol class="ov-spine" data-bind="spine" aria-label="Manufacturing spine">${steps}</ol>
  </section>`;
}

function workInFlightZone(): string {
  return `
  <section class="ov-panel" data-zone="work-in-flight" aria-labelledby="ov-wif">
    <h2 id="ov-wif">Work in flight</h2>
    <table class="ov-compact-table" aria-label="Work in flight" data-bind="work-in-flight">
      <thead><tr><th>Status</th><th>Count</th></tr></thead>
      <tbody>
        <tr>
          <td><span class="ov-dot ov-dot-ready"></span> Ready</td>
          <td class="muted">—</td>
        </tr>
        <tr>
          <td><span class="ov-dot ov-dot-running"></span> Running</td>
          <td class="muted">—</td>
        </tr>
        <tr>
          <td><span class="ov-dot ov-dot-failed"></span> Failed</td>
          <td class="muted">—</td>
        </tr>
      </tbody>
    </table>
  </section>`;
}

function fleetCard(harness: HarnessId): string {
  const profile = HARNESS_PROFILES[harness];
  const openCmd =
    harness === "hermes"
      ? "openHermes"
      : harness === "claude-code"
        ? "openClaudeCode"
        : "openDeepSeek";
  const status =
    harness === "deepseek"
      ? `<span class="pill warn">pending</span>`
      : `<span class="pill">idle</span>`;
  return `
    <article class="ov-fleet-card" data-harness="${escapeHtml(harness)}" data-bind="fleet-${escapeHtml(harness)}">
      <div class="ov-fleet-top">
        <span class="ov-fleet-icon" aria-hidden="true">${fleetIcon(harness)}</span>
        <div>
          <div class="ov-fleet-title">${escapeHtml(profile.title)}</div>
          <div class="meta-row">${status}</div>
        </div>
      </div>
      <p class="muted ov-fleet-note">—</p>
      <button type="button" class="secondary ov-fleet-btn" data-cmd="${openCmd}" data-harness="${escapeHtml(harness)}"
        aria-label="Open ${escapeHtml(profile.title)} fleet room">
        Open fleet room ${ICONS.external}
      </button>
    </article>`;
}

function fleetZone(): string {
  return `
  <section class="ov-panel ov-fleet" data-zone="fleet" aria-labelledby="ov-fleet">
    <h2 id="ov-fleet">Fleet summary</h2>
    <div class="ov-fleet-grid" role="list">${FLEET_ORDER.map(fleetCard).join("")}</div>
  </section>`;
}

function moduleCard(
  id: "approvals" | "verification" | "integration",
  title: string,
  icon: string,
  body: string,
  openCmd: string,
  openLabel: string,
  extra = "",
): string {
  return `
  <section class="ov-panel ov-module-card" data-zone="${id}" aria-labelledby="ov-${id}">
    <div class="ov-panel-head">
      <h2 id="ov-${id}">${icon} ${escapeHtml(title)}</h2>
      <button type="button" class="ov-text-btn" data-cmd="${openCmd}">${escapeHtml(openLabel)}</button>
    </div>
    <div class="ov-module-body">${body}</div>
    ${extra}
  </section>`;
}

function approvalsZone(): string {
  return moduleCard(
    "approvals",
    "Approvals",
    ICONS.shield,
    `<p class="muted">No pending approvals</p>
     <ul class="ov-visually-hidden" data-bind="approvals-waiting" aria-label="Waiting approvals">
       <li>No pending approvals.</li>
     </ul>`,
    "openApprovals",
    "Open",
    `<div class="row ov-module-actions">
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}" data-cmd="approve">Approve</button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}" data-cmd="reject">Reject</button>
    </div>`,
  );
}

function verificationZone(): string {
  return moduleCard(
    "verification",
    "Verification",
    ICONS.verify,
    `<p class="muted">No outcomes</p>
     <table class="ov-visually-hidden" aria-label="Latest verification" data-bind="verification-latest">
       <tbody><tr><td>No outcomes</td></tr></tbody>
     </table>`,
    "openVerification",
    "Open",
  );
}

function integrationZone(): string {
  return moduleCard(
    "integration",
    "Integration",
    ICONS.link,
    `<p class="muted">Queue empty</p>
     <table class="ov-visually-hidden" aria-label="Merge queue" data-bind="merge-queue">
       <tbody><tr><td>Queue empty</td></tr></tbody>
     </table>`,
    "openIntegration",
    "Open",
  );
}

function activityZone(): string {
  return `
  <section class="ov-panel ov-activity" data-zone="activity" aria-labelledby="ov-activity">
    <div class="ov-panel-head">
      <h2 id="ov-activity">${ICONS.activity} Unified activity</h2>
    </div>
    <ul class="ov-visually-hidden" data-bind="activity-events" aria-label="Unified activity">
      <li>No events</li>
    </ul>
    ${emptyState({ title: "No events", icon: ICONS.doc, label: "No events" })}
  </section>`;
}

function attentionZone(): string {
  return `
  <section class="ov-panel ov-attention" data-zone="attention" aria-labelledby="ov-attention">
    <div class="ov-panel-head">
      <h2 id="ov-attention">${ICONS.warn} Attention (blocked)</h2>
    </div>
    <table class="ov-attention-table" aria-label="Attention (blocked)" data-bind="attention-blocked">
      <thead>
        <tr>
          <th>Mission</th>
          <th>Stage</th>
          <th>Reason</th>
          <th>Blocked since</th>
          <th>Owner</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td colspan="6">
            ${emptyState({ icon: ICONS.inbox, label: "Nothing blocked" })}
          </td>
        </tr>
      </tbody>
    </table>
  </section>`;
}

function operatorActions(): string {
  return `
  <div class="ov-actions-bar" role="toolbar" aria-label="Operator commands" data-bind="operator-actions">
    <span class="ov-actions-label">Operator actions</span>
    <div class="row ov-actions">
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}" data-cmd="startMission">
        ${ICONS.play} Start mission
      </button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}" data-cmd="pauseMission">
        ${ICONS.pause} Pause
      </button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}" data-cmd="resumeMission">
        ${ICONS.play} Resume
      </button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}" data-cmd="cancelMission">
        ${ICONS.x} Cancel
      </button>
      <button type="button" class="secondary" data-cmd="refresh" aria-label="Refresh Core health">
        ${ICONS.refresh} Refresh
      </button>
    </div>
  </div>`;
}

function overviewHeader(): string {
  return `
  <header class="ov-header">
    <div class="ov-header-left">
      <h1>DDE Code — Mission Overview</h1>
      <div class="meta-row" role="group" aria-label="Dashboard">
        <span class="pill accent">main dashboard</span>
        <span class="pill warn">${ICONS.warn} Gateway pending</span>
      </div>
    </div>
    <div class="ov-header-right">
      <button type="button" class="ov-nav-link" disabled title="${UNAVAILABLE}" aria-label="Docs">${ICONS.book} Docs</button>
      <button type="button" class="ov-nav-link" data-cmd="openSettings" aria-label="Settings">${ICONS.gear} Settings</button>
      <button type="button" class="ov-nav-link ov-menu-btn" disabled title="${UNAVAILABLE}" aria-label="More">${ICONS.menu}</button>
    </div>
  </header>`;
}

export function overviewStyles(): string {
  return `
    [data-surface="overview"] {
      --ov-gap: 10px;
      --ov-radius: 6px;
      max-width: 1400px;
      margin: 0 auto;
    }
    [data-surface="overview"] h1 {
      font-size: 1.15rem;
      font-weight: 600;
      margin: 0;
      letter-spacing: -0.01em;
    }
    [data-surface="overview"] h2 {
      font-size: 0.78rem;
      text-transform: none;
      letter-spacing: 0;
      color: var(--fg);
      margin: 0;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .ov-header {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px 16px;
      margin-bottom: 10px;
    }
    .ov-header-left { display: flex; flex-direction: column; gap: 6px; }
    .ov-header-right { display: flex; gap: 2px; align-items: center; }
    .ov-nav-link {
      background: transparent;
      color: var(--muted);
      border: none;
      padding: 4px 8px;
      min-height: 28px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 0.8rem;
      border-radius: 4px;
    }
    .ov-nav-link:not(:disabled):hover { color: var(--fg); background: rgba(255,255,255,0.04); }
    .ov-nav-link:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
    .ov-menu-btn { padding: 4px 6px; }
    .pill.accent { border-color: var(--accent); color: #6cb6ff; }
    .ov-ico { width: 14px; height: 14px; flex: 0 0 auto; vertical-align: -2px; }
    .ov-ico-sm { width: 12px; height: 12px; }
    .ov-ico-lg { width: 22px; height: 22px; color: #6cb6ff; }
    .ov-ico-empty { width: 36px; height: 36px; opacity: 0.45; margin-bottom: 4px; }
    .ov-sys {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      margin: 0 0 var(--ov-gap);
      border-radius: var(--ov-radius);
      border: 1px solid var(--border);
      background: var(--card);
    }
    .ov-sys-tone-ok {
      border-color: rgba(63, 185, 80, 0.4);
      background: rgba(63, 185, 80, 0.1);
    }
    .ov-sys-tone-warn {
      border-color: rgba(227, 179, 65, 0.4);
      background: rgba(227, 179, 65, 0.08);
    }
    .ov-sys-tone-err {
      border-color: rgba(248, 81, 73, 0.4);
      background: rgba(248, 81, 73, 0.08);
    }
    .ov-sys-left {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
      font-size: 0.85rem;
    }
    .ov-sys-ready { color: var(--ok); display: inline-flex; align-items: center; gap: 6px; }
    .ov-sys-warn { color: var(--warn); display: inline-flex; align-items: center; gap: 6px; }
    .ov-sys-err { color: var(--err); }
    .ov-sys-url { color: var(--muted); font-size: 0.8rem; }
    .ov-actions-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
      margin: 0 0 var(--ov-gap);
      padding: 8px 10px;
      border: 1px solid var(--border);
      border-radius: var(--ov-radius);
      background: var(--card);
    }
    .ov-actions-label {
      font-size: 0.75rem;
      color: var(--muted);
      font-weight: 600;
      margin-right: 4px;
    }
    .ov-actions { margin: 0; gap: 6px; }
    .ov-actions button {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 0.8rem;
      padding: 5px 10px;
    }
    .ov-spine-wrap { margin: 0 0 12px; }
    .ov-spine {
      list-style: none;
      display: flex;
      flex-wrap: nowrap;
      align-items: center;
      gap: 0;
      padding: 0;
      margin: 0;
      overflow-x: auto;
    }
    .ov-spine-step {
      display: flex;
      align-items: center;
      gap: 6px;
      border: 1px dashed var(--border);
      border-radius: 4px;
      padding: 5px 10px;
      font-size: 0.78rem;
      color: var(--muted);
      background: rgba(0,0,0,0.15);
      white-space: nowrap;
      flex: 0 0 auto;
    }
    .ov-spine-step:not(:last-child)::after {
      content: "";
      display: block;
      width: 18px;
      height: 0;
      border-top: 1px dashed var(--border);
      margin-left: 8px;
      flex: 0 0 auto;
    }
    .ov-spine-index {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 1.15rem;
      height: 1.15rem;
      border-radius: 3px;
      border: 1px solid var(--border);
      font-size: 0.68rem;
      color: var(--muted);
    }
    .ov-body {
      display: grid;
      grid-template-columns: minmax(180px, 0.85fr) minmax(0, 2.2fr) minmax(180px, 0.95fr);
      gap: var(--ov-gap);
      align-items: start;
    }
    .ov-sidebar {
      display: flex;
      flex-direction: column;
      gap: var(--ov-gap);
      min-width: 0;
    }
    .ov-main {
      display: flex;
      flex-direction: column;
      gap: var(--ov-gap);
      min-width: 0;
    }
    .ov-panel {
      border: 1px solid var(--border);
      border-radius: var(--ov-radius);
      background: var(--card);
      padding: 10px 12px;
      margin: 0;
    }
    .ov-panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }
    .ov-text-btn {
      background: transparent;
      color: var(--muted);
      border: none;
      padding: 2px 4px;
      min-height: 22px;
      font-size: 0.72rem;
      border-radius: 3px;
    }
    .ov-text-btn:hover { color: var(--fg); }
    .ov-text-btn:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
    .ov-subhead {
      font-size: 0.78rem;
      font-weight: 600;
      margin: 8px 0 2px;
      text-transform: none;
      letter-spacing: 0;
    }
    .ov-tone-active { color: #6cb6ff; }
    .ov-tone-blocked { color: var(--warn); }
    .ov-tone-completed { color: var(--ok); }
    .ov-mission-list {
      list-style: none;
      padding: 0;
      margin: 0 0 4px;
      font-size: 0.8rem;
    }
    .ov-compact-table { font-size: 0.8rem; }
    .ov-compact-table th, .ov-compact-table td { padding: 5px 2px; }
    .ov-dot {
      display: inline-block;
      width: 7px;
      height: 7px;
      border-radius: 50%;
      margin-right: 6px;
      vertical-align: middle;
    }
    .ov-dot-ready { background: #6cb6ff; }
    .ov-dot-running { background: var(--warn); }
    .ov-dot-failed { background: var(--err); }
    .ov-fleet-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 4px;
    }
    .ov-fleet-card {
      border: 1px solid var(--border);
      border-radius: var(--ov-radius);
      padding: 10px;
      background: var(--bg);
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 0;
    }
    .ov-fleet-top { display: flex; gap: 8px; align-items: flex-start; }
    .ov-fleet-title { font-weight: 600; font-size: 0.88rem; }
    .ov-fleet-note { font-size: 0.78rem; margin: 0; }
    .ov-fleet-btn {
      width: 100%;
      justify-content: center;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-top: auto;
      font-size: 0.78rem;
    }
    .ov-modules {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--ov-gap);
    }
    .ov-module-card .ov-module-body { font-size: 0.8rem; }
    .ov-module-card .ov-module-body p { margin: 0 0 4px; }
    .ov-module-actions { margin-top: 8px; }
    .ov-activity {
      min-height: 280px;
      display: flex;
      flex-direction: column;
    }
    .ov-activity .ov-empty { flex: 1; }
    .ov-empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 18px 10px;
      color: var(--muted);
      min-height: 100px;
    }
    .ov-empty-title { font-size: 0.85rem; color: var(--muted); margin-top: 2px; }
    .ov-attention-table { font-size: 0.78rem; }
    .ov-attention-table th { white-space: nowrap; }
    .ov-attention-table td { border-bottom: none; }
    .ov-visually-hidden {
      position: absolute !important;
      width: 1px; height: 1px;
      padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0,0,0,0);
      white-space: nowrap; border: 0;
    }
    @media (max-width: 960px) {
      .ov-body { grid-template-columns: 1fr; }
      .ov-fleet-grid { grid-template-columns: 1fr; }
      .ov-modules { grid-template-columns: 1fr; }
      .ov-spine { flex-wrap: wrap; gap: 6px; }
      .ov-spine-step:not(:last-child)::after { display: none; }
    }
  `;
}

export function overviewHtml(
  connection: StudioConnection | undefined,
  probe: ProbeState,
  configError?: string,
): string {
  const body = `
  ${overviewHeader()}
  ${systemStrip(connection, probe, configError)}
  ${operatorActions()}
  ${spineZone()}

  <div class="ov-body">
    <aside class="ov-sidebar">
      ${missionsZone()}
      ${workInFlightZone()}
    </aside>
    <div class="ov-main">
      ${fleetZone()}
      <div class="ov-modules">
        ${approvalsZone()}
        ${verificationZone()}
        ${integrationZone()}
      </div>
      ${attentionZone()}
    </div>
    ${activityZone()}
  </div>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DDE Code — Mission Overview</title>
  <style>${sharedStyles()}${overviewStyles()}</style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <main id="main" data-surface="overview">${body}</main>
  <script>${messageBridgeScript()}</script>
</body>
</html>`;
}
