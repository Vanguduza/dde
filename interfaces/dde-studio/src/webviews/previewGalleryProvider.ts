/**
 * Host-side provider for the Prototype Gallery (dde.studio.preview).
 *
 * Playbook §5.0 P2: while an authoring mission runs, this view live-streams
 * the workspace's prototypes/ directory — screens appear and refresh as the
 * worker writes them. Read-only by law: prototype HTML reaches the webview
 * only as sandboxed iframe srcdoc (§5.3), never as file:// resources.
 */

import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import {
  buildGalleryModel,
  previewGalleryChrome,
  previewGalleryPage,
  wrapScreenSrcdoc,
  type GalleryEmptyReason,
  type GalleryModel,
} from "../../shared/ui/previewGallery";

const CONFIG_SECTION = "dde.studio";
const PROTOTYPES_PATH_SETTING = "prototypesPath";
const WATCH_DEBOUNCE_MS = 300;

interface GalleryMessage {
  type: string;
  screen?: string;
}

type GalleryModelOrEmpty = GalleryModel | GalleryEmptyReason;

/** Resolves relPath strictly inside root; undefined when it escapes. */
function contained(root: string, relPath: string): string | undefined {
  const full = path.resolve(root, relPath);
  const rel = path.relative(path.resolve(root), full);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    return undefined;
  }
  return full;
}

export class PreviewGalleryProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;
  private watchers: vscode.Disposable[] = [];
  private debounce?: ReturnType<typeof setTimeout>;
  private selected?: string;

  constructor(public readonly viewType: string) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((msg: GalleryMessage) => {
      if (msg.type === "galleryReady") {
        // Client just (re)loaded; its in-memory state is gone.
        this.pushModel();
        return;
      }
      if (msg.type !== "openScreen" || typeof msg.screen !== "string") {
        return;
      }
      // The path comes from our own rendered chrome; containment is still
      // enforced so a tampered message cannot read outside prototypes/.
      const root = this.prototypesRoot();
      if (!root || !contained(root, msg.screen)) {
        return;
      }
      this.selected = msg.screen;
      this.pushScreenContent(msg.screen);
      this.pushModel();
    });
    webviewView.onDidDispose(() => {
      this.view = undefined;
      this.selected = undefined;
      this.clearWatchers();
    });
    this.renderFull();
    this.startWatcher();
    this.pushModel();
  }

  /** Re-reads everything after configuration or workspace changes. */
  refresh(): void {
    if (!this.view) {
      return;
    }
    this.renderFull();
    this.startWatcher();
    this.pushModel();
  }

  private prototypesRoot(): string | undefined {
    const roots = vscode.workspace.workspaceFolders ?? [];
    if (roots.length === 0) {
      return undefined;
    }
    const rel = vscode.workspace
      .getConfiguration(CONFIG_SECTION)
      .get<string>(PROTOTYPES_PATH_SETTING, "prototypes");
    return path.join(roots[0].uri.fsPath, rel);
  }

  private readPrototypes(): GalleryModelOrEmpty {
    const root = this.prototypesRoot();
    if (!root || !fs.existsSync(root)) {
      return "no-directory";
    }
    const entries: { relPath: string; content: string }[] = [];
    const flowsPath = path.join(root, "flows.json");
    if (fs.existsSync(flowsPath) && fs.statSync(flowsPath).isFile()) {
      entries.push({
        relPath: "flows.json",
        content: fs.readFileSync(flowsPath, "utf8"),
      });
    }
    const screensDir = path.join(root, "screens");
    if (fs.existsSync(screensDir) && fs.statSync(screensDir).isDirectory()) {
      for (const dirent of fs.readdirSync(screensDir, { withFileTypes: true })) {
        if (dirent.isFile() && dirent.name.toLowerCase().endsWith(".html")) {
          entries.push({
            relPath: `screens/${dirent.name}`,
            content: fs.readFileSync(path.join(screensDir, dirent.name), "utf8"),
          });
        }
      }
    }
    return buildGalleryModel({ exists: true, entries });
  }

  private renderFull(): void {
    if (!this.view) {
      return;
    }
    this.view.webview.html = previewGalleryPage(this.readPrototypes());
  }

  /**
   * Incremental update path for file watches: swaps the chrome list and the
   * selected screen's srcdoc without rebuilding the page, so client state
   * (reduced-motion toggle, current selection) survives.
   */
  private pushModel(): void {
    if (!this.view) {
      return;
    }
    const model = this.readPrototypes();
    let selected: string | undefined;
    if (typeof model !== "string" && model.screens.length > 0) {
      selected =
        this.selected && model.screens.some((s) => s.relPath === this.selected)
          ? this.selected
          : model.screens[0].relPath;
    }
    void this.view.webview.postMessage({
      type: "galleryState",
      chromeHtml: previewGalleryChrome(model, selected),
    });
    if (selected) {
      this.pushScreenContent(selected);
    }
  }

  private pushScreenContent(relPath: string): void {
    const root = this.prototypesRoot();
    if (!root || !this.view) {
      return;
    }
    const full = contained(root, relPath);
    if (!full || !fs.existsSync(full)) {
      return;
    }
    void this.view.webview.postMessage({
      type: "screenContent",
      srcdoc: wrapScreenSrcdoc(fs.readFileSync(full, "utf8")),
    });
  }

  private startWatcher(): void {
    this.clearWatchers();
    const roots = vscode.workspace.workspaceFolders ?? [];
    if (roots.length === 0) {
      return;
    }
    const rel = vscode.workspace
      .getConfiguration(CONFIG_SECTION)
      .get<string>(PROTOTYPES_PATH_SETTING, "prototypes");
    const pattern = new vscode.RelativePattern(roots[0], `${rel}/**`);
    // One debounced re-read per burst: workers write screens in flurries.
    const schedule = (): void => {
      if (this.debounce) {
        clearTimeout(this.debounce);
      }
      this.debounce = setTimeout(() => this.pushModel(), WATCH_DEBOUNCE_MS);
    };
    const watcher = vscode.workspace.createFileSystemWatcher(pattern);
    this.watchers = [
      watcher.onDidChange(schedule),
      watcher.onDidCreate(schedule),
      watcher.onDidDelete(schedule),
      watcher,
    ];
  }

  private clearWatchers(): void {
    if (this.debounce) {
      clearTimeout(this.debounce);
      this.debounce = undefined;
    }
    for (const d of this.watchers) {
      d.dispose();
    }
    this.watchers = [];
  }

  dispose(): void {
    this.clearWatchers();
  }
}
