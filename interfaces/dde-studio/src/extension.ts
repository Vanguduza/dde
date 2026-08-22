import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import {
  CLAUDE_CODE_DOCS_AUTH,
  claudeCodeAuthStatusLabel,
  type ClaudeCodeAuthState,
} from "../shared/claudeAuth";
import { findClaudeExecutable } from "../shared/claudeCli";
import { AuthService, type AuthState } from "./connection/authService";
import { ClaudeCodeAuthService } from "./connection/claudeCodeAuthService";
import { StudioGatewayService } from "./connection/studioGateway";
import { HealthClient, type ProbeState } from "./connection/healthClient";
import {
  ConnectionConfigError,
  readConnection,
  type StudioConnection,
} from "./connection/settings";
import {
  HARNESS_PROFILES,
  PendingGatewayClient,
  type HarnessId,
} from "./connection/stubGateway";
import { SIDEBAR_STUB_MODULES } from "./modules/registry";
import { CoreStatusBar } from "./status/statusBar";
import {
  ConnectionViewProvider,
  HarnessPanel,
  HarnessViewProvider,
  ModuleStubViewProvider,
  MorningReviewPanel,
  OverviewViewProvider,
  type StudioMessage,
} from "./webviews/providers";

const CONFIG_SECTION = "dde.studio";

export function activate(context: vscode.ExtensionContext): void {
  const health = new HealthClient();
  const auth = new AuthService(context.secrets);
  const claudeCodeAuth = new ClaudeCodeAuthService(context.secrets);
  const statusBar = new CoreStatusBar();

  let connection: StudioConnection | undefined;
  let configError: string | undefined;
  let probe: ProbeState = { kind: "idle" };
  let authState: AuthState = { kind: "unauthenticated" };
  let claudeAuthState: ClaudeCodeAuthState = { kind: "none" };
  let pollTimer: ReturnType<typeof setInterval> | undefined;
  const panels = new Map<HarnessId, HarnessPanel>();
  let gatewayService: StudioGatewayService | undefined;

  const overviewView = new OverviewViewProvider((msg) =>
    void handleMessage(msg),
  );
  const connectionView = new ConnectionViewProvider((msg) =>
    void handleMessage(msg),
  );
  const stubViews = SIDEBAR_STUB_MODULES.filter((m) => m.viewId).map(
    (m) =>
      new ModuleStubViewProvider(m.viewId!, m, (msg) => void handleMessage(msg)),
  );
  const hermesView = new HarnessViewProvider(
    "dde.studio.hermes",
    "hermes",
    (msg) => void handleMessage(msg, "hermes"),
  );
  const claudeView = new HarnessViewProvider(
    "dde.studio.claudeCode",
    "claude-code",
    (msg) => void handleMessage(msg, "claude-code"),
  );
  const deepSeekView = new HarnessViewProvider(
    "dde.studio.deepSeek",
    "deepseek",
    (msg) => void handleMessage(msg, "deepseek"),
  );

  context.subscriptions.push(
    statusBar,
    vscode.window.registerWebviewViewProvider(
      OverviewViewProvider.viewType,
      overviewView,
    ),
    vscode.window.registerWebviewViewProvider(
      ConnectionViewProvider.viewType,
      connectionView,
    ),
    ...stubViews.map((v) =>
      vscode.window.registerWebviewViewProvider(v.viewType, v),
    ),
    vscode.window.registerWebviewViewProvider(hermesView.viewType, hermesView),
    vscode.window.registerWebviewViewProvider(claudeView.viewType, claudeView),
    vscode.window.registerWebviewViewProvider(
      deepSeekView.viewType,
      deepSeekView,
    ),
    vscode.commands.registerCommand("dde.studio.refreshHealth", () =>
      refreshAll(),
    ),
    vscode.commands.registerCommand("dde.studio.openOverview", async () => {
      await vscode.commands.executeCommand(
        "workbench.view.extension.dde-studio",
      );
      await vscode.commands.executeCommand("dde.studio.overview.focus");
    }),
    vscode.commands.registerCommand("dde.studio.openConnection", async () => {
      await vscode.commands.executeCommand(
        "workbench.view.extension.dde-studio",
      );
      await vscode.commands.executeCommand("dde.studio.connection.focus");
    }),
    vscode.commands.registerCommand("dde.studio.openHermesDashboard", () =>
      openPanel("hermes"),
    ),
    vscode.commands.registerCommand(
      "dde.studio.openClaudeCodeDashboard",
      () => openPanel("claude-code"),
    ),
    vscode.commands.registerCommand("dde.studio.openDeepSeekDashboard", () =>
      openPanel("deepseek"),
    ),
    vscode.commands.registerCommand("dde.studio.morningReview", () =>
      openMorningReview(),
    ),
    vscode.commands.registerCommand("dde.studio.openChat", async () => {
      await vscode.commands.executeCommand("dde.studio.chat.focus");
    }),
    vscode.commands.registerCommand("dde.studio.setLocalTarget", async () => {
      await vscode.workspace
        .getConfiguration(CONFIG_SECTION)
        .update("preferredTarget", "local", vscode.ConfigurationTarget.Global);
      await refreshAll();
    }),
    vscode.commands.registerCommand("dde.studio.setCloudTarget", async () => {
      await vscode.workspace
        .getConfiguration(CONFIG_SECTION)
        .update("preferredTarget", "cloud", vscode.ConfigurationTarget.Global);
      await refreshAll();
    }),
    vscode.commands.registerCommand("dde.studio.setSessionToken", () =>
      promptSetSessionToken(),
    ),
    vscode.commands.registerCommand("dde.studio.clearSessionToken", () =>
      clearSessionToken(),
    ),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration(CONFIG_SECTION)) {
        void refreshAll();
      }
    }),
    {
      dispose: () => {
        if (pollTimer) {
          clearInterval(pollTimer);
        }
      },
    },
  );

  tryRegisterChatParticipantPlaceholder();

  function loadConnection(): boolean {
    try {
      const cfg = vscode.workspace.getConfiguration(CONFIG_SECTION);
      connection = readConnection((key) => cfg.get(key));
      configError = undefined;
      return true;
    } catch (err) {
      connection = undefined;
      configError =
        err instanceof ConnectionConfigError
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err);
      probe = {
        kind: "misconfigured",
        error: configError,
        checkedAt: new Date().toISOString(),
      };
      return false;
    }
  }

  async function refreshAll(): Promise<void> {
    authState = await auth.getState();
    claudeAuthState = await claudeCodeAuth.getState();

    if (!loadConnection() || !connection) {
      pushUi();
      restartPoll(5000);
      return;
    }

    probe = { kind: "checking", url: connection.effectiveUrl };
    pushUi();

    probe = await health.probe(connection.effectiveUrl);
    const principalId = String(
      vscode.workspace.getConfiguration(CONFIG_SECTION).get("principalId") ?? "",
    );
    if (
      !gatewayService ||
      gatewayService.baseUrl !== connection.effectiveUrl ||
      gatewayService.getPrincipalId() !== principalId
    ) {
      gatewayService = new StudioGatewayService(
        connection.effectiveUrl,
        principalId,
      );
    }
    pushUi();
    restartPoll(connection.pollIntervalMs);
  }

  function pushUi(): void {
    statusBar.update(probe);
    overviewView.setSnapshot(connection, probe, configError);
    connectionView.setSnapshot(
      connection,
      probe,
      authState,
      configError,
      claudeAuthState,
    );
    claudeView.setClaudeAuth(claudeAuthState);
    panels.get("claude-code")?.setClaudeAuth(claudeAuthState);

    const gateway = new PendingGatewayClient(connection?.effectiveUrl ?? "");
    for (const [harness, view] of [
      ["hermes", hermesView],
      ["claude-code", claudeView],
      ["deepseek", deepSeekView],
    ] as const) {
      void (async () => {
        const missions = await gateway.listMissions(harness);
        const runs = await gateway.listRuns(harness);
        view.setData(missions, runs);
        panels.get(harness)?.setData(missions, runs);
      })();
    }
  }

  function restartPoll(intervalMs: number): void {
    if (pollTimer) {
      clearInterval(pollTimer);
    }
    pollTimer = setInterval(() => {
      void refreshAll();
    }, intervalMs);
  }

  async function promptSetSessionToken(): Promise<void> {
    const token = await vscode.window.showInputBox({
      title: "DDE Gateway session token",
      prompt:
        "Stored in VS Code SecretStorage only. Not used for /healthz today; reserved for S3 Bearer auth.",
      password: true,
      ignoreFocusOut: true,
      placeHolder: "Paste token (never stored in settings.json)",
    });
    if (token === undefined) {
      return;
    }
    await auth.setSessionToken(token);
    authState = await auth.getState();
    pushUi();
    void vscode.window.showInformationMessage(
      token.trim()
        ? "DDE session token stored securely."
        : "DDE session token cleared.",
    );
  }

  async function clearSessionToken(): Promise<void> {
    await auth.clearSession();
    authState = await auth.getState();
    pushUi();
    void vscode.window.showInformationMessage("DDE session token cleared.");
  }

  function openMorningReview(): void {
    MorningReviewPanel.show((msg) => void handleMessage(msg));
  }

  async function handleMessage(
    msg: StudioMessage,
    harness?: HarnessId,
  ): Promise<void> {
    switch (msg.type) {
      case "refresh":
        await refreshAll();
        break;
      case "openSettings":
        await vscode.commands.executeCommand(
          "workbench.action.openSettings",
          "dde.studio",
        );
        break;
      case "useLocal":
        await vscode.commands.executeCommand("dde.studio.setLocalTarget");
        break;
      case "useCloud":
        await vscode.commands.executeCommand("dde.studio.setCloudTarget");
        break;
      case "setSessionToken":
        await promptSetSessionToken();
        break;
      case "clearSessionToken":
        await clearSessionToken();
        break;
      case "openPanel":
        if (harness) {
          openPanel(harness);
        }
        break;
      case "openHermes":
        openPanel("hermes");
        break;
      case "openClaudeCode":
        openPanel("claude-code");
        break;
      case "openClaudeCodeSignIn": {
        if (!findClaudeExecutable()) {
          const choice = await vscode.window.showWarningMessage(
            "Claude Code CLI not found on PATH. Install the official CLI to sign in with a subscription.",
            "Install Claude Code CLI",
            "Open docs",
          );
          if (choice === "Install Claude Code CLI") {
            await handleMessage({ type: "installClaudeCodeCli" }, harness);
          } else if (choice === "Open docs") {
            await vscode.env.openExternal(
              vscode.Uri.parse("https://code.claude.com/docs/en/installation"),
            );
          }
          break;
        }
        const result = await claudeCodeAuth.startLogin();
        claudeAuthState = await claudeCodeAuth.getState();
        pushUi();
        void vscode.window.showInformationMessage(
          result.message + (result.ok ? ` Docs: ${CLAUDE_CODE_DOCS_AUTH}` : ""),
        );
        break;
      }
      case "installClaudeCodeCli": {
        const programFiles =
          process.env.ProgramFiles ?? "C:\\Program Files";
        const script = path.join(
          programFiles,
          "DDE",
          "scripts",
          "Ensure-ClaudeCli.ps1",
        );
        if (!fs.existsSync(script)) {
          const open = await vscode.window.showWarningMessage(
            `Ensure-ClaudeCli.ps1 not found at ${script}. Install DDE-Complete-Setup or install Claude Code manually.`,
            "Open install docs",
          );
          if (open) {
            await vscode.env.openExternal(
              vscode.Uri.parse("https://code.claude.com/docs/en/installation"),
            );
          }
          break;
        }
        const term = vscode.window.createTerminal({
          name: "Install Claude Code CLI",
        });
        term.show();
        term.sendText(
          `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "${script}" -NonInteractive -Method Auto`,
        );
        void vscode.window.showInformationMessage(
          "Installing Claude Code CLI in a terminal. When it finishes, click Verify (CLI installed ≠ signed in).",
        );
        // Re-detect after a short delay so UI can update if install is fast.
        setTimeout(() => {
          void (async () => {
            claudeAuthState = await claudeCodeAuth.getState();
            pushUi();
          })();
        }, 8000);
        break;
      }
      case "verifyClaudeCodeAuth": {
        claudeAuthState = await claudeCodeAuth.verify();
        pushUi();
        void vscode.window.setStatusBarMessage(
          `Claude Code: ${claudeCodeAuthStatusLabel(claudeAuthState)}`,
          5000,
        );
        break;
      }
      case "storeClaudeCodeSetupToken": {
        const pasted = await vscode.window.showInputBox({
          title: "Claude Code setup-token",
          prompt:
            "Paste the sk-ant-oat01-… token from `claude setup-token` (stored in SecretStorage only).",
          password: true,
          ignoreFocusOut: true,
        });
        if (pasted === undefined) {
          break;
        }
        const stored = await claudeCodeAuth.storeSetupToken(pasted);
        claudeAuthState = await claudeCodeAuth.getState();
        pushUi();
        void vscode.window.showInformationMessage(stored.message);
        break;
      }
      case "openClaudeCodeApiKeyBackup":
        void vscode.window.setStatusBarMessage(
          "Claude Code: API key backup — use setup wizard Backup / advanced (auth_mode=api_key_backup).",
          5000,
        );
        break;
      case "openDeepSeek":
        openPanel("deepseek");
        break;
      case "openMorningReview":
        openMorningReview();
        break;
      case "openOverview":
        await vscode.commands.executeCommand("dde.studio.openOverview");
        break;
      case "openApprovals":
        await vscode.commands.executeCommand("dde.studio.approvals.focus");
        break;
      case "openMission":
        await vscode.commands.executeCommand("dde.studio.mission.focus");
        break;
      case "openVerification":
        await vscode.commands.executeCommand("dde.studio.verification.focus");
        break;
      case "openIntegration":
        await vscode.commands.executeCommand("dde.studio.integration.focus");
        break;
      case "startMission":
      case "pauseMission":
      case "resumeMission":
      case "cancelMission":
      case "approve":
      case "reject":
        // Disabled in UI until Gateway/CLI; ignore stray posts.
        break;
    }
  }

  function openPanel(harness: HarnessId): void {
    const existing = panels.get(harness);
    if (existing) {
      existing.reveal();
      return;
    }
    const profile = HARNESS_PROFILES[harness];
    const panel = new HarnessPanel(
      harness,
      `DDE · ${profile.title}`,
      (msg) => void handleMessage(msg, harness),
      () => panels.delete(harness),
    );
    panels.set(harness, panel);
    void (async () => {
      const gateway = new PendingGatewayClient(connection?.effectiveUrl ?? "");
      const missions = await gateway.listMissions(harness);
      const runs = await gateway.listRuns(harness);
      panel.setData(missions, runs);
      // Live /v1 read for any tracked mission (real Gateway session).
      if (
        gatewayService &&
        probe.kind === "ok" &&
        gatewayService.trackedMissionIds.length > 0
      ) {
        const first = gatewayService.trackedMissionIds[0];
        const result = await gatewayService.readMission(first);
        if (result.ok && result.mission) {
          panel.setData(
            [
              {
                missionId: result.mission.mission_id,
                title: result.mission.title,
                state: result.mission.status,
                note: result.mission.intent,
              },
            ],
            runs,
          );
        }
      }
    })();
  }

  void refreshAll();
}

/**
 * Placeholder for future dde-chat. Intentionally empty so activation never
 * depends on vscode.chat.createChatParticipant (Cursor partial impl, §3.3).
 * Primary chat surface is the webview shell (dde.studio.chat).
 */
function tryRegisterChatParticipantPlaceholder(): void {
  try {
    const chatApi = (
      vscode as unknown as {
        chat?: { createChatParticipant?: unknown };
      }
    ).chat;
    if (chatApi && typeof chatApi.createChatParticipant === "function") {
      // Do not register yet — webview-first chat is the primary path (§3.3).
    }
  } catch {
    // Chat API must never prevent the rest of the extension from loading.
  }
}

export function deactivate(): void {
  // disposables handled via context.subscriptions
}
