/**
 * Shared Mission Control / agent fleet-manager chrome for Hermes,
 * Claude Code, and DeepSeek harness views.
 *
 * Five capability surfaces (same structure per fleet role):
 * 1. Status report  2. Activity stream  3. Task routing
 * 4. Observability  5. Control room
 *
 * Empty markers only until Gateway/CLI binds — no helper essays.
 * Core health is Overview + Connection only (not on fleet rooms).
 */

import {
  claudeCodeAuthBannerHtml,
  type ClaudeCodeAuthState,
} from "../claudeAuth";
import {
  HARNESS_PROFILES,
  type HarnessId,
  type MissionSummary,
  type RunSummary,
} from "../stubGateway";
import { escapeHtml } from "./base";

export const MISSION_CONTROL_SECTIONS = [
  "status-report",
  "activity-stream",
  "task-routing",
  "observability",
  "control-room",
] as const;

export type MissionControlSectionId = (typeof MISSION_CONTROL_SECTIONS)[number];

const LIFECYCLE_STATES = [
  "PLANNED",
  "PREPARING",
  "READY",
  "RUNNING",
  "CHECKPOINTING",
  "PAUSING",
  "PAUSED",
  "RESUMING",
  "CANCELLING",
  "CANCELLED",
  "COMPLETED",
  "FAILED",
] as const;

const UNAVAILABLE = "Unavailable";

function section(
  id: MissionControlSectionId,
  title: string,
  body: string,
  opts?: { empty?: boolean },
): string {
  const emptyClass = opts?.empty ? " empty" : "";
  return `
  <section class="mc-section" data-section="${id}" aria-labelledby="mc-${id}">
    <h2 id="mc-${id}">${escapeHtml(title)}</h2>
    <div class="banner${emptyClass}">${body}</div>
  </section>`;
}

function statusReportStrip(): string {
  return `
    <div class="mc-status-strip" role="group" aria-label="Status report">
      <div class="mc-stat">
        <div class="mc-stat-label">Fleet missions</div>
        <div class="mc-stat-value muted">—</div>
      </div>
      <div class="mc-stat">
        <div class="mc-stat-label">Active runs</div>
        <div class="mc-stat-value muted">—</div>
      </div>
      <div class="mc-stat">
        <div class="mc-stat-label">Autonomy</div>
        <div class="mc-stat-value muted">—</div>
      </div>
    </div>`;
}

function activityStreamBody(): string {
  return `
    <ul class="compact mc-stream" data-bind="activity-events" aria-label="Activity stream">
      <li class="muted">—</li>
    </ul>`;
}

function taskRoutingBody(): string {
  return `
    <table aria-label="Routing panel" data-bind="route-candidates">
      <thead>
        <tr><th>Candidate</th><th>Gate</th><th>Rank</th><th>Note</th></tr>
      </thead>
      <tbody>
        <tr>
          <td colspan="4" class="muted">—</td>
        </tr>
      </tbody>
    </table>
    <div class="row">
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Re-evaluate route</button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Override</button>
    </div>`;
}

function observabilityBody(
  missions: MissionSummary[],
  runs: RunSummary[],
): string {
  const missionRows =
    missions.length === 0
      ? `<tr><td colspan="4" class="muted">—</td></tr>`
      : missions
          .map(
            (m) => `
      <tr>
        <td><code>${escapeHtml(m.missionId)}</code></td>
        <td>${escapeHtml(m.title)}</td>
        <td><span class="pill">${escapeHtml(m.state)}</span></td>
        <td class="muted">${escapeHtml(m.note)}</td>
      </tr>`,
          )
          .join("");

  const runRows =
    runs.length === 0
      ? `<tr><td colspan="3" class="muted">—</td></tr>`
      : runs
          .map(
            (r) => `
      <tr>
        <td><code>${escapeHtml(r.runId)}</code></td>
        <td><span class="pill">${escapeHtml(r.state)}</span></td>
        <td class="muted">${escapeHtml(r.note)}</td>
      </tr>`,
          )
          .join("");

  return `
    <h3 class="mc-subhead">Missions</h3>
    <table data-bind="missions" aria-label="Fleet missions">
      <thead><tr><th>ID</th><th>Title</th><th>State</th><th>Note</th></tr></thead>
      <tbody>${missionRows}</tbody>
    </table>
    <h3 class="mc-subhead">Worker runs</h3>
    <table data-bind="runs" aria-label="Fleet worker runs">
      <thead><tr><th>ID</th><th>State</th><th>Note</th></tr></thead>
      <tbody>${runRows}</tbody>
    </table>`;
}

function controlRoomBody(): string {
  const lifecycle = LIFECYCLE_STATES.map(
    (s) => `<span aria-hidden="true">${escapeHtml(s)}</span>`,
  ).join("");

  return `
    <div class="lifecycle-grid" aria-label="WorkerRun states">${lifecycle}</div>
    <div class="row" data-bind="control-actions">
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Pause → checkpoint</button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Resume from checkpoint</button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Cancel</button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Inspect context</button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">View diff</button>
    </div>`;
}

/**
 * Inner Mission Control body (sections only) — shared by sidebar + editor panel.
 */
export function missionControlBody(opts: {
  missions: MissionSummary[];
  runs: RunSummary[];
}): string {
  return [
    section("status-report", "1. Status report", statusReportStrip()),
    section("activity-stream", "2. Activity stream", activityStreamBody(), {
      empty: true,
    }),
    section("task-routing", "3. Task routing", taskRoutingBody(), {
      empty: true,
    }),
    section(
      "observability",
      "4. Observability",
      observabilityBody(opts.missions, opts.runs),
      { empty: opts.missions.length === 0 && opts.runs.length === 0 },
    ),
    section("control-room", "5. Control room", controlRoomBody()),
  ].join("\n");
}

export function missionControlHeader(opts: {
  harness: HarnessId;
  panel?: boolean;
  claudeAuth?: ClaudeCodeAuthState;
}): string {
  const profile = HARNESS_PROFILES[opts.harness];
  const openPanelBtn = opts.panel
    ? ""
    : `<button type="button" class="secondary" data-cmd="openPanel">Open full Mission Control</button>`;

  const claudeAuth =
    opts.harness === "claude-code"
      ? `
  <h2>Auth</h2>
  ${claudeCodeAuthBannerHtml(opts.claudeAuth ?? { kind: "none" })}`
      : "";

  return `
  <h1>${escapeHtml(profile.title)} — Mission Control</h1>
  <div class="meta-row" role="group" aria-label="Fleet Mission Control">
    <span class="pill">fleet</span>
    <span class="pill">${escapeHtml(profile.appendixRole)}</span>
    <span class="pill">T2</span>
    <span class="pill warn">cert: ${escapeHtml(profile.certification)}</span>
  </div>
  <div class="row">
    ${openPanelBtn}
  </div>
  ${claudeAuth}`;
}

/** Extra CSS for Mission Control layout (appended to sharedStyles). */
export function missionControlStyles(): string {
  return `
    .mc-section { margin: 0; }
    .mc-subhead {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--muted);
      margin: 12px 0 6px;
      text-transform: none;
      letter-spacing: 0;
    }
    .mc-status-strip {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 4px;
    }
    .mc-stat {
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 8px 10px;
      background: var(--bg);
    }
    .mc-stat-label {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .mc-stat-value { font-size: 0.9rem; }
    .mc-stream { margin: 0; list-style: none; padding: 0; }
  `;
}
