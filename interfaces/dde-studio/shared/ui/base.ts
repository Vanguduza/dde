import type { ProbeState } from "../healthClient";
import { tokenCssRoot } from "./tokens";

/** Injected into every page so VS Code webviews and Electron share one UI. */
export function messageBridgeScript(): string {
  return `
    const api = (typeof acquireVsCodeApi === "function")
      ? acquireVsCodeApi()
      : (window.ddeDesktop || {
          postMessage: (m) => window.parent.postMessage(m, "*")
        });
    document.querySelectorAll("[data-cmd]").forEach((el) => {
      el.addEventListener("click", () => {
        const msg = { type: el.getAttribute("data-cmd") };
        const harness = el.getAttribute("data-harness");
        if (harness) msg.harness = harness;
        api.postMessage(msg);
      });
    });
  `;
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function sharedStyles(): string {
  return `
    ${tokenCssRoot()}
    :root {
      color-scheme: light dark;
      --vscode-sideBar-background: var(--bg);
      --vscode-foreground: var(--fg);
      --vscode-descriptionForeground: var(--muted);
      --vscode-panel-border: var(--border);
      --vscode-button-background: var(--accent);
      --vscode-button-foreground: var(--accent-fg);
      --vscode-editor-background: var(--card);
      --vscode-testing-iconPassed: var(--ok);
      --vscode-editorWarning-foreground: var(--warn);
      --vscode-editorError-foreground: var(--err);
      --vscode-font-family: var(--type-font-family-body);
      --vscode-font-size: var(--type-body);
      --vscode-editor-font-family: var(--type-font-family-mono);
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 12px 14px 20px;
      background: var(--bg);
      color: var(--fg);
      line-height: 1.45;
    }
    .skip-link {
      position: absolute;
      left: -9999px;
      top: 0;
      background: var(--accent);
      color: var(--accent-fg);
      padding: 8px 12px;
      z-index: 100;
    }
    .skip-link:focus { left: 8px; top: 8px; }
    :focus-visible {
      outline: 2px solid var(--focus);
      outline-offset: 2px;
    }
    button:focus-visible,
    input:focus-visible,
    select:focus-visible,
    textarea:focus-visible,
    a:focus-visible {
      outline: 2px solid var(--focus);
      outline-offset: 2px;
    }
    h1 {
      font-size: 1.1rem;
      font-weight: 600;
      margin: 0 0 4px;
    }
    h2 {
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin: 18px 0 8px;
      font-weight: 600;
    }
    p, li { line-height: 1.45; }
    .muted { color: var(--muted); }
    .meta-row { margin: 6px 0 8px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
    .banner {
      border: 1px solid var(--border);
      background: var(--card);
      border-radius: 6px;
      padding: 10px 12px;
      margin: 10px 0;
    }
    .banner.empty { border-style: dashed; }
    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      border: 1px solid var(--border);
      font-size: 0.75rem;
      margin-right: 4px;
    }
    .pill.ok { border-color: var(--ok); color: var(--ok); }
    .pill.warn { border-color: var(--warn); color: var(--warn); }
    .pill.err { border-color: var(--err); color: var(--err); }
    .row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    button {
      background: var(--accent);
      color: var(--accent-fg);
      border: none;
      border-radius: 4px;
      padding: 6px 12px;
      cursor: pointer;
      font: inherit;
      min-height: 28px;
    }
    button.secondary {
      background: transparent;
      color: var(--fg);
      border: 1px solid var(--border);
    }
    button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    th, td {
      text-align: left;
      padding: 6px 4px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 500; }
    code {
      font-family: var(--vscode-editor-font-family);
      font-size: 0.85em;
    }
    ul.compact { padding-left: 1.1rem; margin: 8px 0; }
    label.field {
      display: block;
      margin: 8px 0 4px;
      color: var(--muted);
      font-size: 0.8rem;
    }
    input, select, textarea {
      width: 100%;
      box-sizing: border-box;
      background: var(--card);
      color: var(--fg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 6px 8px;
      font: inherit;
    }
    input:hover, select:hover, textarea:hover {
      border-color: var(--border-hover);
    }
    textarea { resize: vertical; min-height: 56px; }
    .chat-shell .chat-thread {
      min-height: 120px;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 4px;
      margin-bottom: 0;
    }
    .lifecycle-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 6px;
      margin: 8px 0;
      font-size: 0.8rem;
    }
    .lifecycle-grid span {
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 4px 6px;
      color: var(--muted);
      text-align: center;
    }
  `;
}

export function renderProbeHtml(state: ProbeState): string {
  switch (state.kind) {
    case "idle":
      return `<span class="pill">idle</span>`;
    case "checking":
      return `<span class="pill">checking</span> <code>${escapeHtml(state.url)}</code>`;
    case "ok": {
      const ready = state.readyz.status === "ready";
      const pill = ready
        ? `<span class="pill ok">ready</span>`
        : `<span class="pill warn">not_ready</span>`;
      return `
        ${pill}
        <div style="margin-top:8px">
          <div><strong>URL</strong> <code>${escapeHtml(state.url)}</code></div>
          <div><strong>healthz</strong> ${escapeHtml(state.healthz.status)}</div>
          <div><strong>database</strong> ${state.readyz.database ? "ok" : "down"} ·
               <strong>redis</strong> ${state.readyz.redis ? "ok" : "down"} ·
               <strong>migrations</strong> ${escapeHtml(state.readyz.migrations)}</div>
          <div class="muted">${escapeHtml(state.checkedAt)}</div>
        </div>`;
    }
    case "unreachable":
      return `
        <span class="pill err">unreachable</span>
        <div style="margin-top:8px">
          <div><code>${escapeHtml(state.url)}</code></div>
          <div class="muted">${escapeHtml(state.error)}</div>
          <div class="muted">${escapeHtml(state.checkedAt)}</div>
        </div>`;
    case "misconfigured":
      return `
        <span class="pill warn">misconfigured</span>
        <div class="muted" style="margin-top:8px">${escapeHtml(state.error)}</div>`;
  }
}
