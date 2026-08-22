export type NavId =
  | "overview"
  | "connection"
  | "mission"
  | "integration"
  | "context"
  | "routing"
  | "hermes"
  | "claude-code"
  | "deepseek"
  | "verification"
  | "approvals"
  | "chat"
  | "donor"
  | "knowledge"
  | "evaluation"
  | "debug"
  | "preview"
  | "morning-review"
  | "settings";

export interface ShellModel {
  active: NavId;
  statusText: string;
  contentHtml: string;
  harnessTitles: {
    hermes: string;
    "claude-code": string;
    deepseek: string;
  };
}

const NAV: { id: NavId; label: string; group: string }[] = [
  { id: "overview", label: "Overview", group: "Home" },
  { id: "connection", label: "Connection", group: "Core" },
  { id: "mission", label: "Mission", group: "Plane" },
  { id: "integration", label: "Integration", group: "Plane" },
  { id: "context", label: "Context", group: "Plane" },
  { id: "routing", label: "Routing", group: "Plane" },
  { id: "hermes", label: "Hermes", group: "Fleet" },
  { id: "claude-code", label: "Claude Code", group: "Fleet" },
  { id: "deepseek", label: "DeepSeek", group: "Fleet" },
  { id: "verification", label: "Verification", group: "Quality" },
  { id: "approvals", label: "Approvals", group: "Quality" },
  { id: "chat", label: "Chat", group: "Quality" },
  { id: "morning-review", label: "Morning", group: "Quality" },
  { id: "donor", label: "Donors", group: "Lab" },
  { id: "knowledge", label: "Knowledge", group: "Lab" },
  { id: "evaluation", label: "Evaluate", group: "Lab" },
  { id: "debug", label: "Debug", group: "Lab" },
  { id: "preview", label: "Preview", group: "Lab" },
  { id: "settings", label: "Settings", group: "App" },
];

export function buildShellHtml(model: ShellModel): string {
  const navHtml = NAV.map((item) => {
    const active = item.id === model.active ? " active" : "";
    return `<button type="button" class="nav-item${active}" data-nav="${item.id}" title="${item.label}" aria-label="${item.label}" aria-current="${item.id === model.active ? "page" : "false"}">
      <span class="nav-label">${item.label}</span>
    </button>`;
  }).join("");

  const bodyMatch = model.contentHtml.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  let inner = bodyMatch ? bodyMatch[1] : model.contentHtml;
  inner = inner.replace(/<script>[\s\S]*?<\/script>/gi, "");
  const styleMatch = model.contentHtml.match(/<style>([\s\S]*?)<\/style>/i);
  const pageStyles = styleMatch ? styleMatch[1] : "";

  const isOverview = model.active === "overview";
  const sideInner = isOverview
    ? `<div class="panel side-home" id="side-panel">
        <div class="side-home-title">Overview</div>
      </div>`
    : `<div class="panel" id="side-panel">${inner}</div>`;
  const mainInner = isOverview
    ? `<div class="panel overview-pane" id="main-panel">${inner}</div>`
    : `<div class="panel main-placeholder">
        <button type="button" data-nav="overview">Open Mission Overview</button>
      </div>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;" />
  <title>DDE Code</title>
  <style>
    html, body { height: 100%; margin: 0; }
    body {
      display: flex;
      flex-direction: column;
      background: #1e1e1e;
      color: #e6e6e6;
      font-family: "Segoe UI", system-ui, sans-serif;
      font-size: 13px;
    }
    .titlebar {
      height: 36px;
      display: flex;
      align-items: center;
      padding: 0 12px;
      background: #323233;
      border-bottom: 1px solid #3c3c3c;
      font-weight: 600;
      letter-spacing: 0.02em;
      -webkit-app-region: drag;
      gap: 10px;
    }
    .titlebar .brand { color: #fff; }
    .titlebar .muted { color: #b0b0b0; font-weight: 400; }
    .workbench {
      flex: 1;
      display: flex;
      min-height: 0;
    }
    .activity {
      width: 56px;
      background: #333333;
      border-right: 1px solid #3c3c3c;
      display: flex;
      flex-direction: column;
      padding: 6px 0;
      gap: 1px;
      overflow-y: auto;
    }
    .nav-item {
      -webkit-app-region: no-drag;
      background: transparent;
      border: none;
      color: #ccc;
      cursor: pointer;
      padding: 8px 4px;
      font-size: 9px;
      line-height: 1.2;
      text-align: center;
      border-left: 2px solid transparent;
      border-radius: 0;
    }
    .nav-item:hover { background: #2a2d2e; color: #fff; }
    .nav-item:focus-visible {
      outline: 2px solid #4fc1ff;
      outline-offset: -2px;
    }
    .nav-item.active {
      background: #2a2d2e;
      border-left-color: #0078d4;
      color: #fff;
    }
    .nav-label { display: block; word-break: break-word; }
    .sidebar {
      width: ${isOverview ? "180px" : "320px"};
      min-width: ${isOverview ? "140px" : "240px"};
      background: #252526;
      border-right: 1px solid #3c3c3c;
      overflow: auto;
    }
    .main {
      flex: 1;
      overflow: auto;
      background: #1e1e1e;
    }
    .panel { padding: 0; }
    .side-home {
      padding: 14px 12px;
    }
    .side-home-title {
      font-size: 0.85rem;
      font-weight: 600;
      color: #ccc;
    }
    .overview-pane { padding: 0; }
    .main-placeholder {
      padding: 24px;
      display: flex;
      align-items: flex-start;
    }
    .main-placeholder button {
      background: #1177bb;
      color: #fff;
      border: none;
      border-radius: 4px;
      padding: 8px 14px;
      font: inherit;
      cursor: pointer;
      min-height: 32px;
    }
    .main-placeholder button:focus-visible {
      outline: 2px solid #4fc1ff;
      outline-offset: 2px;
    }
    .statusbar {
      height: 22px;
      display: flex;
      align-items: center;
      padding: 0 10px;
      background: #007acc;
      color: #fff;
      font-size: 12px;
    }
    ${pageStyles}
    .panel body, .panel { background: transparent; }
  </style>
</head>
<body>
  <a class="skip-link" href="#side-panel" style="position:absolute;left:-9999px">Skip to panel</a>
  <div class="titlebar">
    <span class="brand">DDE Code</span>
    <span class="muted">desktop</span>
  </div>
  <div class="workbench">
    <nav class="activity" aria-label="Activity bar">${navHtml}</nav>
    <aside class="sidebar" aria-label="Module panel">${sideInner}</aside>
    <section class="main" aria-label="Main">${mainInner}</section>
  </div>
  <footer class="statusbar" role="status">${escape(model.statusText)}</footer>
  <script>
    const api = window.ddeDesktop;
    document.querySelectorAll("[data-nav]").forEach((el) => {
      el.addEventListener("click", () => {
        api.navigate(el.getAttribute("data-nav"));
      });
    });
    document.querySelectorAll("[data-cmd]").forEach((el) => {
      el.addEventListener("click", () => {
        const msg = { type: el.getAttribute("data-cmd") };
        const harness = el.getAttribute("data-harness");
        if (harness) msg.harness = harness;
        api.postMessage(msg);
      });
    });
    const saveBtn = document.getElementById("save");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => {
        api.postMessage({
          type: "saveSettings",
          coreUrl: document.getElementById("coreUrl").value,
          cloudUrl: document.getElementById("cloudUrl").value,
          preferredTarget: document.getElementById("preferredTarget").value,
          pollIntervalMs: Number(document.getElementById("pollIntervalMs").value),
        });
      });
    }
  </script>
</body>
</html>`;
}

function escape(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
