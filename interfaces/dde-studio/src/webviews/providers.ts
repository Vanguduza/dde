import * as vscode from "vscode";
import type { AuthState } from "../connection/authService";
import type { ProbeState } from "../connection/healthClient";
import type { StudioConnection } from "../connection/settings";
import {
  type HarnessId,
  type MissionSummary,
  type RunSummary,
} from "../connection/stubGateway";
import type { ModuleDescriptor } from "../modules/registry";
import type { ClaudeCodeAuthState } from "../../shared/claudeAuth";
import {
  connectionHtml,
  harnessHtml,
  modulePanelHtml,
  morningReviewHtml,
  overviewHtml,
} from "./html";
import {
  frontendStudioHtml,
  type FrontendStudioView,
} from "../../shared/ui/frontendStudio";

export type StudioMessage =
  | { type: "refresh" }
  | { type: "openSettings" }
  | { type: "useLocal" }
  | { type: "useCloud" }
  | { type: "openPanel" }
  | { type: "setSessionToken" }
  | { type: "clearSessionToken" }
  | { type: "openMorningReview" }
  | { type: "openApprovals" }
  | { type: "openOverview" }
  | { type: "openMission" }
  | { type: "openVerification" }
  | { type: "openIntegration" }
  | { type: "openHermes" }
  | { type: "openClaudeCode" }
  | { type: "openDeepSeek" }
  | { type: "openClaudeCodeSignIn" }
  | { type: "installClaudeCodeCli" }
  | { type: "verifyClaudeCodeAuth" }
  | { type: "storeClaudeCodeSetupToken" }
  | { type: "openClaudeCodeApiKeyBackup" }
  | { type: "startMission" }
  | { type: "pauseMission" }
  | { type: "resumeMission" }
  | { type: "cancelMission" }
  | { type: "approve" }
  | { type: "reject" }
  | { type: "batchApprove"; ids?: string[] }
  | {
      type: "frontendCommand";
      missionId: string;
      commandType: string;
      parameters: Record<string, unknown>;
    };

export class FrontendStudioViewProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;
  private status = "";

  constructor(
    public readonly viewType: string,
    private readonly studioView: FrontendStudioView,
    private readonly onMessage: (msg: StudioMessage) => void,
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((msg: StudioMessage) => this.onMessage(msg));
    this.render();
  }

  setStatus(status: string): void {
    this.status = status;
    this.render();
  }

  private render(): void {
    if (this.view) this.view.webview.html = frontendStudioHtml(this.studioView, this.status);
  }
}

export class OverviewViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "dde.studio.overview";

  private view?: vscode.WebviewView;
  private connection?: StudioConnection;
  private state: ProbeState = { kind: "idle" };
  private configError?: string;

  constructor(private readonly onMessage: (msg: StudioMessage) => void) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((msg: StudioMessage) => {
      this.onMessage(msg);
    });
    this.render();
  }

  setSnapshot(
    connection: StudioConnection | undefined,
    state: ProbeState,
    configError?: string,
  ): void {
    this.connection = connection;
    this.state = state;
    this.configError = configError;
    this.render();
  }

  private render(): void {
    if (!this.view) {
      return;
    }
    this.view.webview.html = overviewHtml(
      this.connection,
      this.state,
      this.configError,
    );
  }
}

export class ConnectionViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "dde.studio.connection";

  private view?: vscode.WebviewView;
  private connection?: StudioConnection;
  private state: ProbeState = { kind: "idle" };
  private auth: AuthState = { kind: "unauthenticated" };
  private claudeAuth: ClaudeCodeAuthState = { kind: "none" };
  private configError?: string;

  constructor(private readonly onMessage: (msg: StudioMessage) => void) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((msg: StudioMessage) => {
      this.onMessage(msg);
    });
    this.render();
  }

  setSnapshot(
    connection: StudioConnection | undefined,
    state: ProbeState,
    auth: AuthState,
    configError?: string,
    claudeAuth?: ClaudeCodeAuthState,
  ): void {
    this.connection = connection;
    this.state = state;
    this.auth = auth;
    this.configError = configError;
    if (claudeAuth) {
      this.claudeAuth = claudeAuth;
    }
    this.render();
  }

  private render(): void {
    if (!this.view) {
      return;
    }
    this.view.webview.html = connectionHtml(
      this.connection,
      this.state,
      this.auth,
      this.configError,
      { claudeAuth: this.claudeAuth },
    );
  }
}

export class ModuleStubViewProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;

  constructor(
    public readonly viewType: string,
    private readonly module: ModuleDescriptor,
    private readonly onMessage: (msg: StudioMessage) => void,
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((msg: StudioMessage) => {
      this.onMessage(msg);
    });
    this.render();
  }

  refresh(): void {
    this.render();
  }

  private render(): void {
    if (!this.view) {
      return;
    }
    this.view.webview.html = modulePanelHtml(this.module);
  }
}

export class HarnessViewProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;
  private missions: MissionSummary[] = [];
  private runs: RunSummary[] = [];
  private claudeAuth: ClaudeCodeAuthState = { kind: "none" };

  constructor(
    public readonly viewType: string,
    public readonly harness: HarnessId,
    private readonly onMessage: (msg: StudioMessage) => void,
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((msg: StudioMessage) => {
      this.onMessage(msg);
    });
    this.render();
  }

  setClaudeAuth(state: ClaudeCodeAuthState): void {
    this.claudeAuth = state;
    this.render();
  }

  setData(missions: MissionSummary[], runs: RunSummary[]): void {
    this.missions = missions;
    this.runs = runs;
    this.render();
  }

  private render(): void {
    if (!this.view) {
      return;
    }
    this.view.webview.html = harnessHtml({
      harness: this.harness,
      missions: this.missions,
      runs: this.runs,
      claudeAuth: this.harness === "claude-code" ? this.claudeAuth : undefined,
    });
  }
}

export class HarnessPanel {
  private panel: vscode.WebviewPanel;
  private missions: MissionSummary[] = [];
  private runs: RunSummary[] = [];
  private claudeAuth: ClaudeCodeAuthState = { kind: "none" };

  constructor(
    public readonly harness: HarnessId,
    title: string,
    private readonly onMessage: (msg: StudioMessage) => void,
    private readonly onDispose: () => void,
  ) {
    this.panel = vscode.window.createWebviewPanel(
      `dde.studio.panel.${harness}`,
      title,
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true },
    );
    this.panel.onDidDispose(() => this.onDispose());
    this.panel.webview.onDidReceiveMessage((msg: StudioMessage) => {
      this.onMessage(msg);
    });
    this.render();
  }

  reveal(): void {
    this.panel.reveal(vscode.ViewColumn.One);
  }

  setClaudeAuth(state: ClaudeCodeAuthState): void {
    this.claudeAuth = state;
    this.render();
  }

  setData(missions: MissionSummary[], runs: RunSummary[]): void {
    this.missions = missions;
    this.runs = runs;
    this.render();
  }

  private render(): void {
    this.panel.webview.html = harnessHtml({
      harness: this.harness,
      missions: this.missions,
      runs: this.runs,
      panel: true,
      claudeAuth: this.harness === "claude-code" ? this.claudeAuth : undefined,
    });
  }
}

/** Morning Review editor panel — shell only until DDE-026. */
export class MorningReviewPanel {
  private static current?: MorningReviewPanel;
  private panel: vscode.WebviewPanel;

  private constructor(private readonly onMessage: (msg: StudioMessage) => void) {
    this.panel = vscode.window.createWebviewPanel(
      "dde.studio.morningReview",
      "DDE · Morning Review",
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true },
    );
    this.panel.onDidDispose(() => {
      if (MorningReviewPanel.current === this) {
        MorningReviewPanel.current = undefined;
      }
    });
    this.panel.webview.onDidReceiveMessage((msg: StudioMessage) => {
      this.onMessage(msg);
    });
    this.render();
  }

  static show(onMessage: (msg: StudioMessage) => void): MorningReviewPanel {
    if (MorningReviewPanel.current) {
      MorningReviewPanel.current.panel.reveal(vscode.ViewColumn.One);
      return MorningReviewPanel.current;
    }
    const created = new MorningReviewPanel(onMessage);
    MorningReviewPanel.current = created;
    return created;
  }

  private render(): void {
    this.panel.webview.html = morningReviewHtml();
  }
}
