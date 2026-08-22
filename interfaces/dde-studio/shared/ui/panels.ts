/**
 * Module panel layouts — structure and minimal empty markers only.
 * No instructional / blocked-on essays in the webview.
 * Core health lives only on Mission Overview + Connection (not here).
 */

import type { ModuleDescriptor, ModuleId } from "../registry";
import { escapeHtml, messageBridgeScript, sharedStyles } from "./base";

function pageShell(title: string, body: string, extraStyles = ""): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(title)}</title>
  <style>${sharedStyles()}${extraStyles}</style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <main id="main">${body}</main>
  <script>${messageBridgeScript()}</script>
</body>
</html>`;
}

function header(module: ModuleDescriptor, extraPills = ""): string {
  return `
  <h1>${escapeHtml(module.title)}</h1>
  <div class="meta-row" role="group" aria-label="Module status">
    <span class="pill">${escapeHtml(module.id)}</span>
    <span class="pill warn">${escapeHtml(module.status)}</span>
    ${extraPills}
  </div>`;
}

function emptyMarker(ariaLabel = "Empty"): string {
  return `<p class="muted" role="status" aria-label="${escapeHtml(ariaLabel)}">—</p>`;
}

function emptyTableCell(cols: number, text = "—"): string {
  return `<tr><td colspan="${cols}" class="muted">${escapeHtml(text)}</td></tr>`;
}

const UNAVAILABLE = "Unavailable";

function missionBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}

  <h2>Active mission</h2>
  <div class="banner empty" role="status">${emptyMarker("No mission")}</div>

  <h2>Tasks / TaskGraph</h2>
  <div class="banner empty">
    <table aria-label="Tasks">
      <thead><tr><th>Task</th><th>State</th><th>Worker</th><th>Scope</th></tr></thead>
      <tbody>${emptyTableCell(4)}</tbody>
    </table>
  </div>
`;
}

function integrationBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}

  <h2>Workspace</h2>
  <div class="banner empty" role="status">${emptyMarker()}</div>

  <h2>Merge queue</h2>
  <div class="banner empty">
    <table aria-label="Integration queue">
      <thead><tr><th>#</th><th>Task</th><th>State</th><th>Scope</th></tr></thead>
      <tbody>${emptyTableCell(4, "Queue empty")}</tbody>
    </table>
  </div>

  <h2>Branches</h2>
  <div class="banner empty">
    <ul class="compact muted">
      <li><code>main</code></li>
      <li><code>mission/…</code> —</li>
      <li><code>task/…</code> —</li>
    </ul>
  </div>

  <div class="row">
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">View mission branch</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">View main</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Open conflict → repair</button>
  </div>
`;
}

const COVERAGE_CATEGORIES = [
  "authoritative_requirements",
  "applicable_domain_rules",
  "impacted_code_and_deps",
  "architecture_constraints",
  "security_constraints",
  "verification_obligations",
  "known_unresolved_questions",
] as const;

function contextBody(module: ModuleDescriptor): string {
  const rows = COVERAGE_CATEGORIES.map(
    (c) =>
      `<tr><td><code>${escapeHtml(c)}</code></td><td><span class="pill">pending</span></td><td class="muted">—</td></tr>`,
  ).join("");
  return `
  ${header(module)}

  <h2>Index</h2>
  <div class="banner empty">
    <p><strong>index_version</strong> <span class="muted">—</span> · <strong>lag</strong> <span class="muted">—</span></p>
  </div>

  <h2>Package anchors</h2>
  <div class="banner empty">${emptyMarker()}</div>

  <h2>Coverage</h2>
  <div class="banner">
    <table aria-label="Coverage categories">
      <thead><tr><th>Category</th><th>Status</th><th>Note</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>

  <h2>Context Critic</h2>
  <div class="banner empty muted">—</div>

  <div class="row">
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Ask DDE why this file</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Request more context</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Show conflict</button>
  </div>
`;
}

function routingBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}

  <h2>Task / policy</h2>
  <div class="banner empty muted">—</div>

  <h2>Gates 0–5</h2>
  <div class="banner empty">
    <table aria-label="Hard gates">
      <thead><tr><th>Candidate</th><th>Result</th></tr></thead>
      <tbody>${emptyTableCell(2)}</tbody>
    </table>
  </div>

  <h2>Gates 6–7</h2>
  <div class="banner empty">
    <table aria-label="Ranked survivors">
      <thead><tr><th>Candidate</th><th>Score</th><th>Note</th></tr></thead>
      <tbody>${emptyTableCell(3)}</tbody>
    </table>
  </div>

  <h2>Plans</h2>
  <div class="banner empty muted">—</div>

  <div class="row">
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Ask DDE why</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Override</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Escalate</button>
  </div>
`;
}

const VERIFY_STAGES = [
  "Build",
  "Static analysis",
  "Diff gates",
  "Unit",
  "Contract",
  "Integration",
  "E2E/browser",
  "Visual",
  "Security",
  "Domain invariants",
  "AcceptanceOracle",
  "Requirement trace",
  "EDR consistency",
] as const;

function verificationBody(module: ModuleDescriptor): string {
  const rows = VERIFY_STAGES.map(
    (s) =>
      `<tr><td>${escapeHtml(s)}</td><td><span class="pill">pending</span></td><td class="muted">—</td></tr>`,
  ).join("");
  return `
  ${header(module)}

  <h2>Chain</h2>
  <div class="banner">
    <table aria-label="Verification stages">
      <thead><tr><th>Stage</th><th>Result</th><th>Detail</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>

  <h2>Independence</h2>
  <div class="banner empty muted">—</div>

  <h2>Oracles</h2>
  <div class="banner empty">
    <p><strong>Task oracle</strong> <span class="pill">pending</span> · <strong>Mission oracle</strong> <span class="pill">pending</span></p>
  </div>

  <div class="row">
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">View failing outcome</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">View diff</button>
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Repair task</button>
  </div>
`;
}

function approvalsBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}

  <h2>Pending approvals</h2>
  <div class="banner empty" role="status">
    <table aria-label="Pending approvals">
      <thead><tr><th>Type</th><th>Subject</th><th>Requested</th><th>Actions</th></tr></thead>
      <tbody>${emptyTableCell(4, "None")}</tbody>
    </table>
  </div>

  <h2>Standing approval</h2>
  <div class="banner empty">
    <div class="row">
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Grant standing approval</button>
      <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Revoke all</button>
    </div>
  </div>

  <h2>Morning Review</h2>
  <div class="banner">
    <button type="button" data-cmd="openMorningReview" aria-label="Open Morning Review panel">Open Morning Review</button>
  </div>
`;
}

const CHAT_STYLES = `
  .chat-panel { max-width: 640px; }
  .chat-shell {
    display: flex;
    flex-direction: column;
    gap: 8px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--card);
    padding: 10px;
    margin: 10px 0;
  }
  .chat-thread {
    min-height: 160px;
    max-height: 360px;
    overflow: auto;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .chat-composer {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .chat-composer textarea {
    min-height: 56px;
    border-radius: 4px;
  }
  .chat-actions { margin-top: 0; }
`;

function chatBody(module: ModuleDescriptor): string {
  return `
  <div class="chat-panel">
  ${header(module)}

  <h2>Session</h2>
  <div class="chat-shell" aria-disabled="true">
    <div class="chat-thread muted" role="log" aria-label="Chat messages">—</div>
    <div class="chat-composer">
      <label class="field" for="chat-input">Message</label>
      <textarea id="chat-input" rows="2" disabled placeholder="Message" aria-label="Message"></textarea>
      <div class="row chat-actions">
        <button type="button" disabled title="${UNAVAILABLE}">Send</button>
        <button type="button" class="secondary" disabled title="${UNAVAILABLE}">New session</button>
      </div>
    </div>
  </div>
  </div>`;
}

function donorBody(module: ModuleDescriptor): string {
  const classes = [
    "OPEN_REUSE",
    "CONDITIONAL_REUSE",
    "SOURCE_REFERENCE_ONLY",
    "RESTRICTED",
    "UNKNOWN",
    "REJECTED",
  ];
  return `
  ${header(module)}

  <h2>Classification</h2>
  <div class="banner">
    <div class="row" role="list">
      ${classes.map((c) => `<span class="pill" role="listitem">${escapeHtml(c)}</span>`).join("")}
    </div>
  </div>

  <h2>Donor repositories</h2>
  <div class="banner empty" role="status">${emptyMarker()}</div>
`;
}

function knowledgeBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}
  <h2>Derived graph</h2>
  <div class="banner empty" role="status">${emptyMarker()}</div>
  <h2>Asserted facts</h2>
  <div class="banner empty" role="status">${emptyMarker()}</div>
`;
}

function evaluationBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}
  <h2>Eval corpus</h2>
  <div class="banner empty" role="status">${emptyMarker()}</div>
  <h2>Promotion gates</h2>
  <div class="banner empty" role="status">${emptyMarker()}</div>
`;
}

function debugBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}

  <h2>Events</h2>
  <div class="banner empty">
    <table aria-label="Events">
      <thead><tr><th>Time</th><th>Type</th><th>Subject</th><th>Payload</th></tr></thead>
      <tbody>${emptyTableCell(4)}</tbody>
    </table>
  </div>
`;
}

function previewBody(module: ModuleDescriptor): string {
  return `
  ${header(module)}

  <h2>ProductEnvironment</h2>
  <div class="banner empty" role="status">
    <p><strong>class</strong> <span class="muted">—</span></p>
    <p><strong>state</strong> <span class="pill">pending</span></p>
    <p><strong>base_url</strong> <span class="muted">—</span></p>
    <p><strong>TTL</strong> <span class="muted">—</span></p>
  </div>

  <div class="row">
    <button type="button" class="secondary" disabled title="${UNAVAILABLE}">Open preview</button>
  </div>
`;
}

export function morningReviewHtml(): string {
  const body = `
  <h1>Morning Review</h1>
  <div class="meta-row">
    <span class="pill warn">blocked</span>
  </div>

  <h2>Overnight summary</h2>
  <div class="banner empty" role="status">${emptyMarker()}</div>

  <h2>Blocked items</h2>
  <div class="banner empty">
    <table aria-label="Blocked items">
      <thead><tr><th>Kind</th><th>Subject</th><th>Reason</th></tr></thead>
      <tbody>${emptyTableCell(3, "None")}</tbody>
    </table>
  </div>

  <h2>Attention debt</h2>
  <div class="banner empty">
    <p class="muted">—</p>
  </div>

  <div class="row">
    <button type="button" class="secondary" data-cmd="openApprovals">Open Approvals</button>
  </div>
`;
  return pageShell("Morning Review", body);
}

const BODY_BY_ID: Record<
  Exclude<ModuleId, "dde-core-ui" | "dde-workers">,
  (m: ModuleDescriptor) => string
> = {
  "dde-mission": missionBody,
  "dde-integration": integrationBody,
  "dde-context": contextBody,
  "dde-routing": routingBody,
  "dde-verification": verificationBody,
  "dde-approvals": approvalsBody,
  "dde-chat": chatBody,
  "dde-donor": donorBody,
  "dde-knowledge": knowledgeBody,
  "dde-evaluation": evaluationBody,
  "dde-debug": debugBody,
  "product-environment": previewBody,
};

/** Rich panel for a sidebar stub module; falls back to generic empty shell. */
export function modulePanelHtml(module: ModuleDescriptor): string {
  if (module.id === "dde-core-ui" || module.id === "dde-workers") {
    return pageShell(module.title, `${header(module)}`);
  }
  const build = BODY_BY_ID[module.id];
  const extra = module.id === "dde-chat" ? CHAT_STYLES : "";
  return pageShell(module.title, build(module), extra);
}
