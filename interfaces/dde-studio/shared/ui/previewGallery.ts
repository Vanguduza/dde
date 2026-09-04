/**
 * Prototype Gallery (dde.studio.preview) — live view over the workspace's
 * prototypes/ directory while an authoring mission runs (playbook §5.0 P2,
 * §5.3 sandbox law, §7.6).
 *
 * Read-only: screens render inside a sandboxed iframe via srcdoc — never
 * file:// URLs into the webview. The iframe CSP/sandbox constants below are
 * the §5.3 strings; the host applies them before content reaches the frame,
 * so the guarantees never depend on client script correctness.
 */

import { escapeHtml, messageBridgeScript, sharedStyles } from "./base";
import { ICONS, overviewStyles } from "./overview";
import { tokenCssRoot } from "./tokens";

/** Exact §5.3 sandbox policy: scripts only, no same-origin, ever. */
export const GALLERY_IFRAME_SANDBOX = "allow-scripts";

/** Inner-document CSP for prototype previews (§5.3). No network sources. */
export const GALLERY_PREVIEW_CSP =
  "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:";

const FORCE_REDUCED_MOTION_CSS =
  "* { animation: none !important; transition: none !important; }";

export interface GalleryScreen {
  /** Path relative to prototypes/, e.g. "screens/overview.ready.html". */
  relPath: string;
  /** Screen name before the state suffix, e.g. "overview". */
  name: string;
  /** State suffix, e.g. "ready"; undefined when the file name has none. */
  state?: string;
}

export interface GalleryFlowStep {
  from: string;
  on: string;
  to: string;
}

export interface GalleryFlow {
  id: string;
  entry: string;
  steps: GalleryFlowStep[];
}

export interface GalleryModel {
  rootLabel?: string;
  screens: GalleryScreen[];
  flows: GalleryFlow[];
}

export type GalleryEmptyReason = "no-directory" | "empty-directory";

/**
 * Splits "screens/overview.ready.html" into name + state suffix. A leading
 * dot (dotfiles) or no dot yields no state.
 */
export function galleryScreenFromRelPath(
  relPath: string,
): Omit<GalleryScreen, never> {
  const base = relPath.split(/[\\/]/).pop() ?? relPath;
  const stem = base.replace(/\.html$/i, "");
  const dot = stem.lastIndexOf(".");
  if (dot <= 0) {
    return { relPath, name: stem };
  }
  return { relPath, name: stem.slice(0, dot), state: stem.slice(dot + 1) };
}

/**
 * Parses flows.json per playbook §5.1b. Returns [] on parse or shape
 * problems — the manifest is optional and must never block the gallery.
 */
export function parseFlowsManifest(text: string): GalleryFlow[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return [];
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return [];
  }
  const flowsRaw = (parsed as Record<string, unknown>)["flows"];
  if (!Array.isArray(flowsRaw)) {
    return [];
  }
  const flows: GalleryFlow[] = [];
  for (const flow of flowsRaw) {
    if (!flow || typeof flow !== "object" || Array.isArray(flow)) {
      continue;
    }
    const rec = flow as Record<string, unknown>;
    const id = typeof rec["id"] === "string" ? rec["id"] : "";
    const entry = typeof rec["entry"] === "string" ? rec["entry"] : "";
    if (!id || !entry) {
      continue;
    }
    const steps: GalleryFlowStep[] = [];
    if (Array.isArray(rec["steps"])) {
      for (const step of rec["steps"]) {
        if (!step || typeof step !== "object" || Array.isArray(step)) {
          continue;
        }
        const s = step as Record<string, unknown>;
        if (
          typeof s["from"] === "string" &&
          typeof s["on"] === "string" &&
          typeof s["to"] === "string"
        ) {
          steps.push({ from: s["from"], on: s["on"], to: s["to"] });
        }
      }
    }
    flows.push({ id, entry, steps });
  }
  return flows;
}

/**
 * Builds the gallery model from a directory listing. Only screens/*.html
 * counts toward emptiness; a lone valid flows.json still renders a gallery.
 */
export function buildGalleryModel(input: {
  exists: boolean;
  entries: { relPath: string; content: string }[];
}): GalleryModel | GalleryEmptyReason {
  if (!input.exists) {
    return "no-directory";
  }
  const screens = input.entries
    .filter((e) => /(^|[\\/])screens[\\/][^\\/]+\.html$/i.test(e.relPath))
    .map((e) => galleryScreenFromRelPath(e.relPath));
  const flowsEntry = input.entries.find((e) => e.relPath === "flows.json");
  if (screens.length === 0 && !flowsEntry) {
    return "empty-directory";
  }
  return {
    screens,
    flows: flowsEntry ? parseFlowsManifest(flowsEntry.content) : [],
  };
}

function screenRow(screen: GalleryScreen, selected?: string): string {
  const label = screen.state
    ? `${screen.name} · ${screen.state}`
    : screen.name;
  const currentAttr = selected === screen.relPath ? ' aria-current="true"' : "";
  return `
      <li class="pg-item">
        <button type="button"${currentAttr} class="pg-open secondary" data-screen="${escapeHtml(screen.relPath)}">
          ${escapeHtml(label)}
          <span class="pg-state">${escapeHtml(screen.state ?? "—")}</span>
        </button>
        <span class="pg-file muted">${escapeHtml(screen.relPath)}</span>
      </li>`;
}

function flowsBlock(flows: GalleryFlow[]): string {
  if (flows.length === 0) {
    return "";
  }
  const rows = flows
    .map(
      (f) => `
          <tr>
            <td><code>${escapeHtml(f.id)}</code></td>
            <td><code>${escapeHtml(f.entry)}</code></td>
            <td>${f.steps.length}</td>
          </tr>`,
    )
    .join("");
  return `
    <section class="pg-flows">
      <table aria-label="Flows manifest">
        <thead><tr><th>Flow</th><th>Entry</th><th>Steps</th></tr></thead>
        <tbody>${rows}
        </tbody>
      </table>
    </section>`;
}

export function previewGalleryChrome(
  model: GalleryModel | GalleryEmptyReason,
  selected?: string,
): string {
  if (typeof model === "string") {
    const title = model === "no-directory" ? "No prototypes yet" : "No screens yet";
    return `
  <h1>Preview</h1>
  <div class="banner empty pg-empty" role="status" data-gallery-state="empty">
    <span class="pg-empty-icon" aria-hidden="true">${ICONS.doc}</span>
    <span class="ov-empty-title">${title}</span>
  </div>`;
  }

  const list =
    model.screens.length > 0
      ? `<ul class="pg-list" aria-label="Prototype screens">${model.screens
          .map((s) => screenRow(s, selected))
          .join("")}
      </ul>`
      : `<p class="muted" role="status">No screens yet</p>`;
  const rootLine = model.rootLabel
    ? `<p class="muted pg-root"><code>${escapeHtml(model.rootLabel)}</code></p>`
    : "";

  return `
  <h1>Preview</h1>
  ${rootLine}
  <div class="meta-row" role="group" aria-label="Gallery controls">
    <label class="pg-motion-toggle">
      <input type="checkbox" id="pg-reduced-motion" />
      Reduce motion
    </label>
  </div>
  <div data-gallery-state="live">${list}${flowsBlock(model.flows)}</div>
  <section class="pg-stage" aria-label="Screen preview">
    <iframe id="pg-frame" title="Prototype screen preview"
      sandbox="${GALLERY_IFRAME_SANDBOX}" srcdoc=""></iframe>
  </section>`;
}

export function previewGalleryPage(
  model: GalleryModel | GalleryEmptyReason,
): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;" />
  <style>${sharedStyles()}${overviewStyles()}${previewGalleryStyles()}</style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <main id="main" data-surface="preview-gallery">
  ${previewGalleryChrome(model)}
  </main>

  <script>${messageBridgeScript()}</script>
  <script>${previewGalleryScript()}</script>
</body>
</html>`;
}

/**
 * Wraps raw prototype HTML for embedding as the iframe's srcdoc value.
 * Guarantees the §5.3 CSP even when the source page omits it; the sandbox
 * attribute lives on the iframe element and cannot be overridden here.
 *
 * DDE-068 fix (gap-closure-record.md §6.5): prototype screens are authored
 * against DDE's `--bg`/`--fg`/`--space-*`/`--motion-duration-*`/etc. custom
 * properties (schemas/design/tokens.json), but nothing previously defined
 * those properties inside the sandboxed srcdoc document -- every `var(...)`
 * reference in a fixture was silently unresolved (invalid at computed-value
 * time), so screens rendered with browser-default colors/spacing/motion
 * instead of DDE's tokens. This affected both the real Prototype Gallery
 * webview and the visual regression harness (visual/server.cjs reuses this
 * same function), which is why the "dark" golden screenshots under
 * visual/__screenshots__/ show a plain white browser-default background
 * rather than the token palette's dark background. Injecting the token
 * :root block here, once, at the single shared wrap point, fixes both
 * call sites at once.
 */
export function wrapScreenSrcdoc(rawHtml: string): string {
  const cspMeta = `<meta http-equiv="Content-Security-Policy" content="${GALLERY_PREVIEW_CSP}" />`;
  const tokenStyle = `<style id="dde-token-root">${tokenCssRoot()}</style>`;
  if (/<html[\s>]/i.test(rawHtml)) {
    let out = rawHtml;
    if (!/http-equiv=["']?Content-Security-Policy/i.test(out)) {
      if (/<head[^>]*>/i.test(out)) {
        out = out.replace(/<head([^>]*)>/i, `<head$1>\n  ${cspMeta}`);
      } else {
        out = `${cspMeta}\n${out}`;
      }
    }
    if (!/id=["']?dde-token-root["']?/i.test(out)) {
      if (/<head[^>]*>/i.test(out)) {
        out = out.replace(/<head([^>]*)>/i, `<head$1>\n  ${tokenStyle}`);
      } else {
        out = `${tokenStyle}\n${out}`;
      }
    }
    return out;
  }
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
${cspMeta}
${tokenStyle}
</head>
<body>
${rawHtml}
</body>
</html>`;
}

export function previewGalleryStyles(): string {
  return `
    .pg-empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      padding: 18px 10px;
      color: var(--text-muted);
    }
    .pg-empty-icon svg { width: 36px; height: 36px; opacity: 0.45; }
    .pg-root { font-size: var(--type-xs); margin: 0 0 6px; }
    .pg-list {
      list-style: none;
      padding: 0;
      margin: 8px 0;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .pg-item {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pg-open {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: var(--type-body);
    }
    .pg-open[aria-current="true"] {
      border-color: var(--accent-primary);
      color: var(--accent-primary);
    }
    .pg-state {
      font-size: var(--type-xs);
      padding: 1px 6px;
      border-radius: var(--radius-md);
      border: 1px solid var(--border-default);
      color: var(--text-muted);
    }
    .pg-file { font-size: var(--type-xs); }
    .pg-stage { margin-top: 12px; }
    .pg-stage iframe {
      width: 100%;
      height: 60vh;
      min-height: 320px;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-lg);
      background: var(--surface-base);
    }
  `;
}

/**
 * Client script for the gallery chrome. Event delegation lives on document
 * so listeners survive the innerHTML chrome swaps triggered by file watches.
 * Reduced-motion state is held in memory only — nothing persisted.
 */
export function previewGalleryScript(): string {
  const forceCss = JSON.stringify(FORCE_REDUCED_MOTION_CSS);
  return `
    (() => {
      const FORCE_CSS = ${forceCss};
      let currentSrcdoc = null;
      let reduceMotion = false;

      function frameEl() {
        return document.getElementById("pg-frame");
      }

      function injectReduced(html) {
        const tag = '<style id="pg-force-reduced-motion">' + FORCE_CSS + '</style>';
        if (/<\\/head>/i.test(html)) {
          return html.replace(/<\\/head>/i, tag + "</head>");
        }
        if (/<body[^>]*>/i.test(html)) {
          return html.replace(/<body([^>]*)>/i, "<body$1>" + tag);
        }
        return tag + html;
      }

      function renderFrame() {
        const frame = frameEl();
        if (!frame || currentSrcdoc === null) return;
        const html = reduceMotion ? injectReduced(currentSrcdoc) : currentSrcdoc;
        frame.setAttribute("srcdoc", html);
      }

      window.addEventListener("message", (event) => {
        const msg = event.data || {};
        if (msg.type === "galleryState" && typeof msg.chromeHtml === "string") {
          const main = document.getElementById("main");
          if (main) {
            main.innerHTML = msg.chromeHtml;
            const toggle = document.getElementById("pg-reduced-motion");
            if (toggle && reduceMotion) {
              toggle.checked = true;
            }
          }
        } else if (msg.type === "screenContent" && typeof msg.srcdoc === "string") {
          currentSrcdoc = msg.srcdoc;
          renderFrame();
        }
      });

      api.postMessage({ type: "galleryReady" });

      document.addEventListener("click", (event) => {
        const el = event.target instanceof Element
          ? event.target.closest("[data-screen]")
          : null;
        if (el) {
          api.postMessage({
            type: "openScreen",
            screen: el.getAttribute("data-screen"),
          });
        }
      });

      document.addEventListener("change", (event) => {
        if (
          event.target &&
          event.target.id === "pg-reduced-motion"
        ) {
          reduceMotion = event.target.checked;
          renderFrame();
        }
      });
    })();
  `;
}
