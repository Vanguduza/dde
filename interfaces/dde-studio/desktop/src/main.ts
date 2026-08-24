import {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  shell as electronShell,
  clipboard,
  safeStorage,
} from "electron";
import * as fs from "node:fs";
import * as path from "node:path";
import { spawn } from "node:child_process";
import { HealthClient, type ProbeState } from "../../shared/healthClient";
import {
  ConnectionConfigError,
  readConnection,
  type PreferredTarget,
  type StudioConnection,
} from "../../shared/settings";
import {
  HARNESS_PROFILES,
  PendingGatewayClient,
  type HarnessId,
} from "../../shared/stubGateway";
import { StudioGatewayService } from "../../shared/studioGateway";
import { MODULE_REGISTRY, SIDEBAR_STUB_MODULES } from "../../shared/registry";
import type { AuthState } from "../../shared/authTypes";
import {
  CLAUDE_CODE_DOCS_AUTH,
  claudeCodeAuthStatusLabel,
  extractClaudeOAuthToken,
  isClaudeOAuthToken,
  resolveClaudeCodeAuthState,
  type ClaudeCodeAuthState,
} from "../../shared/claudeAuth";
import {
  findClaudeExecutable,
  queryClaudeAuthStatus,
  startClaudeAuthLogin,
  startClaudeSetupToken,
} from "../../shared/claudeCli";
import {
  connectionHtml,
  harnessHtml,
  modulePanelHtml,
  morningReviewHtml,
  overviewHtml,
  settingsFormHtml,
} from "../../shared/ui/html";
import { buildShellHtml, type NavId } from "./shell";

interface StoredSettings {
  coreUrl: string;
  cloudUrl: string;
  preferredTarget: PreferredTarget;
  pollIntervalMs: number;
  /** User dismissed first-run wizard prompt for this install. */
  firstRunPromptDismissed?: boolean;
  /** DDE principal UUID for Gateway session (Settings paste / capture). */
  principalId?: string;
  /** DDE project UUID addressed by project-scoped commands. */
  projectId?: string;
}

const DEFAULT_SETTINGS: StoredSettings = {
  coreUrl: "http://127.0.0.1:8000",
  cloudUrl: "",
  preferredTarget: "local",
  pollIntervalMs: 5000,
  firstRunPromptDismissed: false,
  principalId: "",
  projectId: "",
};

const health = new HealthClient();
let mainWindow: BrowserWindow | undefined;
let settings: StoredSettings = { ...DEFAULT_SETTINGS };
let probe: ProbeState = { kind: "idle" };
let auth: AuthState = { kind: "unauthenticated" };
let claudeAuth: ClaudeCodeAuthState = { kind: "none" };
let claudePendingSource: "claude_auth_login" | "claude_setup_token" | undefined;
let opensandboxCapture: {
  fingerprint?: string;
  last4?: string;
  domain?: string;
  captured: boolean;
  statusText?: string;
} = { captured: false };

function refreshAuth(): void {
  auth = loadAuthState();
}

async function refreshClaudeAuth(): Promise<void> {
  const cliFound = Boolean(findClaudeExecutable());
  const stored = readClaudeOAuthToken();
  const hasStoredSetupToken = isClaudeOAuthToken(stored);
  let statusJson;
  if (cliFound) {
    try {
      const probed = await queryClaudeAuthStatus();
      statusJson = probed.status;
    } catch {
      // offline resolution
    }
  }
  claudeAuth = resolveClaudeCodeAuthState({
    cliFound,
    statusJson,
    hasStoredSetupToken,
    tokenRef: hasStoredSetupToken ? "electron_safe_storage" : undefined,
    pendingSource: claudePendingSource,
  });
}
let currentNav: NavId = "overview";
let applianceStatus = "Not checked yet.";
let pollTimer: ReturnType<typeof setInterval> | undefined;
let contentCache = "";

function settingsPath(): string {
  return path.join(app.getPath("userData"), "dde-code-settings.json");
}

function sessionTokenPath(): string {
  return path.join(app.getPath("userData"), "session.token");
}

function claudeOAuthTokenPath(): string {
  return path.join(app.getPath("userData"), "claude-oauth.token");
}

function writeSecretFile(filePath: string, plaintext: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  if (safeStorage.isEncryptionAvailable()) {
    const enc = safeStorage.encryptString(plaintext);
    fs.writeFileSync(filePath, enc);
  } else {
    fs.writeFileSync(filePath, plaintext, { encoding: "utf8", mode: 0o600 });
  }
}

function readSecretFile(filePath: string): string | undefined {
  try {
    const buf = fs.readFileSync(filePath);
    if (safeStorage.isEncryptionAvailable()) {
      try {
        return safeStorage.decryptString(buf).trim();
      } catch {
        // Fall back to legacy plaintext migration.
        return buf.toString("utf8").trim();
      }
    }
    return buf.toString("utf8").trim();
  } catch {
    return undefined;
  }
}

function loadAuthState(): AuthState {
  const raw = readSecretFile(sessionTokenPath());
  if (raw) {
    return { kind: "session", hasToken: true };
  }
  return { kind: "unauthenticated" };
}

function setSessionToken(token: string): void {
  const trimmed = token.trim();
  if (!trimmed) {
    clearSessionToken();
    return;
  }
  writeSecretFile(sessionTokenPath(), trimmed);
}

function clearSessionToken(): void {
  try {
    fs.unlinkSync(sessionTokenPath());
  } catch {
    // already absent
  }
}

function readClaudeOAuthToken(): string | undefined {
  return readSecretFile(claudeOAuthTokenPath());
}

function storeClaudeOAuthToken(token: string): boolean {
  if (!isClaudeOAuthToken(token)) {
    return false;
  }
  writeSecretFile(claudeOAuthTokenPath(), token.trim());
  return true;
}

function loadSettings(): void {
  try {
    const raw = fs.readFileSync(settingsPath(), "utf8");
    settings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    settings = { ...DEFAULT_SETTINGS };
  }
}

function saveSettings(next: StoredSettings): void {
  settings = next;
  fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
  fs.writeFileSync(settingsPath(), JSON.stringify(settings, null, 2), "utf8");
}

/** Program Files\DDE when installed via DDE-Complete-Setup; exe lives in dde-code\. */
function installRoot(): string {
  const exeDir = path.dirname(process.execPath);
  const parent = path.dirname(exeDir);
  if (
    path.basename(exeDir).toLowerCase() === "dde-code" &&
    fs.existsSync(path.join(parent, "scripts", "Start-DdeLocal.ps1"))
  ) {
    return parent;
  }
  return path.join(process.env.ProgramFiles ?? "C:\\Program Files", "DDE");
}

function dataRoot(): string {
  return path.join(process.env.ProgramData ?? "C:\\ProgramData", "DDE");
}

function wizardExePath(): string {
  return path.join(installRoot(), "DdeSetupWizard.exe");
}

function applianceConfigured(): boolean {
  const root = dataRoot();
  return (
    fs.existsSync(path.join(root, "config.toml")) ||
    fs.existsSync(path.join(root, ".env"))
  );
}

function resolveConnection(): {
  connection?: StudioConnection;
  error?: string;
} {
  try {
    const connection = readConnection((key) => {
      switch (key) {
        case "coreUrl":
          return settings.coreUrl;
        case "cloudUrl":
          return settings.cloudUrl;
        case "preferredTarget":
          return settings.preferredTarget;
        case "pollIntervalMs":
          return settings.pollIntervalMs;
        default:
          return undefined;
      }
    });
    return { connection };
  } catch (err) {
    const message =
      err instanceof ConnectionConfigError
        ? err.message
        : err instanceof Error
          ? err.message
          : String(err);
    return { error: message };
  }
}

function statusLabel(): string {
  switch (probe.kind) {
    case "ok":
      return probe.readyz.status === "ready" ? "Core: ready" : "Core: not ready";
    case "checking":
      return "Core: checking…";
    case "unreachable":
      return "Core: down";
    case "misconfigured":
      return "Core: config";
    default:
      return "Core: idle";
  }
}

async function refreshProbe(): Promise<void> {
  const { connection, error } = resolveConnection();
  if (!connection) {
    probe = {
      kind: "misconfigured",
      error: error ?? "No connection",
      checkedAt: new Date().toISOString(),
    };
    return;
  }
  probe = { kind: "checking", url: connection.effectiveUrl };
  pushShell();
  probe = await health.probe(connection.effectiveUrl);
}

function restartPoll(): void {
  if (pollTimer) {
    clearInterval(pollTimer);
  }
  pollTimer = setInterval(() => {
    void (async () => {
      await refreshProbe();
      await renderContent();
      pushShell();
    })();
  }, settings.pollIntervalMs);
}

async function renderContent(): Promise<string> {
  const { connection, error } = resolveConnection();

  if (currentNav === "settings") {
    contentCache = settingsFormHtml(
      {
        coreUrl: settings.coreUrl,
        cloudUrl: settings.cloudUrl,
        preferredTarget: settings.preferredTarget,
        pollIntervalMs: settings.pollIntervalMs,
        effectiveUrl: connection?.effectiveUrl ?? settings.coreUrl,
      },
      {
        domain: opensandboxCapture.domain ?? "",
        fingerprint: opensandboxCapture.fingerprint,
        last4: opensandboxCapture.last4,
        captured: opensandboxCapture.captured,
        statusText: opensandboxCapture.statusText,
        principalId: settings.principalId ?? "",
        projectId: settings.projectId ?? "",
      },
    );
    return contentCache;
  }

  if (currentNav === "connection") {
    contentCache = connectionHtml(connection, probe, auth, error, {
      desktop: true,
      applianceStatus,
      unifiedInstall: true,
      claudeAuth,
    });
    return contentCache;
  }

  if (currentNav === "overview") {
    contentCache = overviewHtml(connection, probe, error);
    return contentCache;
  }

  const harnessMap: Record<string, HarnessId> = {
    hermes: "hermes",
    "claude-code": "claude-code",
    deepseek: "deepseek",
  };
  if (currentNav in harnessMap) {
    const harness = harnessMap[currentNav];
    const gateway = new PendingGatewayClient(connection?.effectiveUrl ?? "");
    const missions = await gateway.listMissions(harness);
    const runs = await gateway.listRuns(harness);
    contentCache = harnessHtml({
      harness,
      missions,
      runs,
      panel: true,
      claudeAuth: harness === "claude-code" ? claudeAuth : undefined,
    });
    return contentCache;
  }

  if (currentNav === "morning-review") {
    contentCache = morningReviewHtml();
    return contentCache;
  }

  const byNav: Record<string, string> = {
    mission: "dde-mission",
    integration: "dde-integration",
    context: "dde-context",
    routing: "dde-routing",
    verification: "dde-verification",
    approvals: "dde-approvals",
    chat: "dde-chat",
    donor: "dde-donor",
    knowledge: "dde-knowledge",
    evaluation: "dde-evaluation",
    debug: "dde-debug",
    preview: "product-environment",
  };
  const moduleId = byNav[currentNav];
  const module =
    MODULE_REGISTRY.find((m) => m.id === moduleId) ??
    SIDEBAR_STUB_MODULES[0];
  contentCache = modulePanelHtml(module);
  return contentCache;
}

function shellFilePath(): string {
  return path.join(app.getPath("userData"), "shell.html");
}

function pushShell(): void {
  if (!mainWindow) {
    return;
  }
  const html = buildShellHtml({
    active: currentNav,
    statusText: statusLabel(),
    contentHtml: contentCache,
    harnessTitles: {
      hermes: HARNESS_PROFILES.hermes.title,
      "claude-code": HARNESS_PROFILES["claude-code"].title,
      deepseek: HARNESS_PROFILES.deepseek.title,
    },
  });
  fs.writeFileSync(shellFilePath(), html, "utf8");
  void mainWindow.loadFile(shellFilePath());
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    title: "DDE Code",
    backgroundColor: "#1e1e1e",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.on("closed", () => {
    mainWindow = undefined;
  });
}

function detectAppliance(): string {
  const root = installRoot();
  const start = path.join(root, "scripts", "Start-DdeLocal.ps1");
  const stop = path.join(root, "scripts", "Stop-DdeLocal.ps1");
  const wizard = wizardExePath();
  if (!fs.existsSync(start)) {
    return `Appliance not found at ${root}. Install DDE-Complete-Setup (dist/windows/DDE-Complete-Setup-*.exe).`;
  }
  if (!fs.existsSync(stop)) {
    return `Start script found; stop script missing at ${stop}.`;
  }
  const configured = applianceConfigured()
    ? "First-run config present."
    : "First-run not completed — run Setup wizard.";
  const wizardBit = fs.existsSync(wizard)
    ? "Wizard available."
    : "Wizard EXE missing.";
  return `Appliance at ${root}. ${configured} ${wizardBit}`;
}

function runApplianceScript(
  which: "start" | "stop",
): Promise<{ ok: boolean; message: string }> {
  const root = installRoot();
  const script = path.join(
    root,
    "scripts",
    which === "start" ? "Start-DdeLocal.ps1" : "Stop-DdeLocal.ps1",
  );
  if (!fs.existsSync(script)) {
    return Promise.resolve({
      ok: false,
      message: `Missing ${script}. Install DDE-Complete-Setup first.`,
    });
  }
  return new Promise((resolve) => {
    const child = spawn(
      "powershell.exe",
      ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
      { windowsHide: true },
    );
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => {
      stdout += String(d);
    });
    child.stderr.on("data", (d) => {
      stderr += String(d);
    });
    child.on("close", (code) => {
      if (code === 0) {
        resolve({
          ok: true,
          message: stdout.trim() || `${which} completed.`,
        });
      } else {
        resolve({
          ok: false,
          message: stderr.trim() || stdout.trim() || `${which} failed (${code}).`,
        });
      }
    });
  });
}

/** Run Ensure-ClaudeCli.ps1 (official native installer + User PATH). */
function ensureClaudeCodeCli(): Promise<{ ok: boolean; message: string }> {
  const script = path.join(installRoot(), "scripts", "Ensure-ClaudeCli.ps1");
  if (!fs.existsSync(script)) {
    return Promise.resolve({
      ok: false,
      message:
        `Missing ${script}. Install DDE-Complete-Setup, or install Claude Code manually: https://code.claude.com/docs/en/installation`,
    });
  }
  return new Promise((resolve) => {
    const child = spawn(
      "powershell.exe",
      [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script,
        "-NonInteractive",
        "-Method",
        "Auto",
      ],
      { windowsHide: false },
    );
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => {
      stdout += String(d);
    });
    child.stderr.on("data", (d) => {
      stderr += String(d);
    });
    child.on("close", (code) => {
      const detail = (stdout.trim() || stderr.trim()).slice(-800);
      if (code === 0 && findClaudeExecutable()) {
        resolve({
          ok: true,
          message:
            detail ||
            "Claude Code CLI is on PATH. Sign in next — this does not mean you are signed in.",
        });
      } else {
        resolve({
          ok: false,
          message:
            detail ||
            `Ensure-ClaudeCli failed (${code}). Docs: https://code.claude.com/docs/en/installation`,
        });
      }
    });
  });
}

function launchSetupWizard(): { ok: boolean; message: string } {
  const wizard = wizardExePath();
  if (!fs.existsSync(wizard)) {
    return {
      ok: false,
      message: `Missing ${wizard}. Reinstall DDE-Complete-Setup.`,
    };
  }
  spawn(wizard, [], {
    cwd: installRoot(),
    detached: true,
    stdio: "ignore",
  }).unref();
  return {
    ok: true,
    message: "Setup wizard launched. Complete Docker, credentials, Claude Code sign-in, then return here.",
  };
}

async function maybeOfferFirstRun(): Promise<void> {
  if (settings.firstRunPromptDismissed) {
    return;
  }
  if (applianceConfigured()) {
    return;
  }
  if (!fs.existsSync(wizardExePath())) {
    return;
  }
  // Only prompt when local Core is not already healthy.
  if (probe.kind === "ok" && probe.readyz.status === "ready") {
    return;
  }

  const result = await dialog.showMessageBox(mainWindow!, {
    type: "info",
    title: "Set up local DDE Core",
    message: "Local Core is not configured yet.",
    detail:
      "Run the setup wizard to install/start Docker Desktop if needed, enter credentials, sign in to Claude Code (subscription), load the Core image, migrate, and start the stack. After it finishes, use Start local Core or Refresh health.",
    buttons: ["Run setup wizard", "Start local Core", "Not now"],
    defaultId: 0,
    cancelId: 2,
    noLink: true,
  });

  if (result.response === 0) {
    const launched = launchSetupWizard();
    applianceStatus = launched.message;
    await renderContent();
    pushShell();
  } else if (result.response === 1) {
    applianceStatus = "Starting local Core…";
    await renderContent();
    pushShell();
    const startResult = await runApplianceScript("start");
    applianceStatus = startResult.message;
    await refreshProbe();
    await renderContent();
    pushShell();
    if (!startResult.ok) {
      dialog.showErrorBox("Start local Core", startResult.message);
    }
  } else {
    saveSettings({ ...settings, firstRunPromptDismissed: true });
  }
}

function wireIpc(): void {
  ipcMain.handle("dde:navigate", async (_e, nav: NavId) => {
    currentNav = nav;
    await renderContent();
    pushShell();
  });

  ipcMain.handle("dde:message", async (_e, msg: Record<string, unknown>) => {
    const type = String(msg.type ?? "");
    switch (type) {
      case "refresh":
        await refreshProbe();
        applianceStatus = detectAppliance();
        await renderContent();
        pushShell();
        break;
      case "useLocal":
        saveSettings({ ...settings, preferredTarget: "local" });
        await refreshProbe();
        await renderContent();
        pushShell();
        restartPoll();
        break;
      case "useCloud":
        saveSettings({ ...settings, preferredTarget: "cloud" });
        await refreshProbe();
        await renderContent();
        pushShell();
        restartPoll();
        break;
      case "openSettings":
        currentNav = "settings";
        await renderContent();
        pushShell();
        break;
      case "saveSettings":
        saveSettings({
          coreUrl: String(msg.coreUrl ?? settings.coreUrl),
          cloudUrl: String(msg.cloudUrl ?? ""),
          preferredTarget:
            msg.preferredTarget === "cloud" ? "cloud" : "local",
          pollIntervalMs: Number(msg.pollIntervalMs ?? 5000),
          firstRunPromptDismissed: settings.firstRunPromptDismissed,
          principalId: String(msg.principalId ?? settings.principalId ?? ""),
          projectId: String(msg.projectId ?? settings.projectId ?? ""),
        });
        currentNav = "connection";
        await refreshProbe();
        await renderContent();
        pushShell();
        restartPoll();
        break;
      case "captureOpensandboxKey": {
        const apiKey = String(msg.apiKey ?? "");
        const domain = String(msg.domain ?? "");
        const { connection: conn } = resolveConnection();
        const baseUrl = conn?.effectiveUrl ?? settings.coreUrl;
        const gateway = new StudioGatewayService(
          baseUrl,
          settings.principalId ?? "",
          "human",
        );
        const result = await gateway.captureOpensandboxKey(
          settings.projectId ?? "",
          apiKey,
          domain || undefined,
        );
        if (result.ok && result.acceptance) {
          const payload = result.acceptance.payload;
          opensandboxCapture = {
            captured: Boolean(payload.captured),
            fingerprint:
              typeof payload.fingerprint === "string"
                ? payload.fingerprint
                : undefined,
            last4: typeof payload.last4 === "string" ? payload.last4 : undefined,
            domain: typeof payload.domain === "string" ? payload.domain : domain,
            statusText: undefined,
          };
        } else {
          opensandboxCapture = {
            ...opensandboxCapture,
            statusText: result.reason ?? "Capture failed",
          };
          dialog.showErrorBox(
            "OpenSandbox capture",
            result.reason ?? "Capture failed",
          );
        }
        await renderContent();
        pushShell();
        break;
      }
      case "runSetupWizard": {
        const launched = launchSetupWizard();
        applianceStatus = launched.message;
        await renderContent();
        pushShell();
        if (!launched.ok) {
          dialog.showErrorBox("Setup wizard", launched.message);
        }
        break;
      }
      case "startLocalCore": {
        applianceStatus = "Starting local Core…";
        await renderContent();
        pushShell();
        const result = await runApplianceScript("start");
        applianceStatus = result.message;
        await refreshProbe();
        await renderContent();
        pushShell();
        if (!result.ok) {
          dialog.showErrorBox("Start local Core", result.message);
        }
        break;
      }
      case "stopLocalCore": {
        applianceStatus = "Stopping local Core…";
        await renderContent();
        pushShell();
        const result = await runApplianceScript("stop");
        applianceStatus = result.message;
        await refreshProbe();
        await renderContent();
        pushShell();
        break;
      }
      case "openPanel":
        // Already full-panel in desktop shell.
        break;
      case "openHermes":
        currentNav = "hermes";
        await renderContent();
        pushShell();
        break;
      case "openClaudeCode":
        currentNav = "claude-code";
        await renderContent();
        pushShell();
        break;
      case "openClaudeCodeSignIn": {
        if (!findClaudeExecutable()) {
          const ask = await dialog.showMessageBox({
            type: "warning",
            buttons: ["Install Claude Code CLI", "Cancel"],
            defaultId: 0,
            cancelId: 1,
            title: "Claude Code CLI missing",
            message: "claude was not found on PATH.",
            detail:
              "Install the official CLI (native installer + User PATH), then Sign in. This does not sign you in by itself.",
          });
          if (ask.response === 0) {
            applianceStatus = "Installing Claude Code CLI…";
            await renderContent();
            pushShell();
            const installed = await ensureClaudeCodeCli();
            applianceStatus = installed.message;
            await refreshClaudeAuth();
            await renderContent();
            pushShell();
            if (!installed.ok) {
              dialog.showErrorBox("Install Claude Code CLI", installed.message);
            }
          }
          break;
        }
        const result = startClaudeAuthLogin();
        if (!result.ok) {
          applianceStatus = result.error ?? `Claude CLI missing. ${CLAUDE_CODE_DOCS_AUTH}`;
        } else {
          claudePendingSource = "claude_auth_login";
          applianceStatus =
            "Claude Code CLI login started — complete browser OAuth, then Verify.";
        }
        await refreshClaudeAuth();
        await renderContent();
        pushShell();
        break;
      }
      case "installClaudeCodeCli": {
        const ask = await dialog.showMessageBox({
          type: "question",
          buttons: ["Install", "Open docs", "Cancel"],
          defaultId: 0,
          cancelId: 2,
          title: "Install Claude Code CLI",
          message: "Install the official Claude Code CLI?",
          detail:
            "Uses Anthropic's native Windows installer (https://claude.ai/install.ps1) with winget fallback, and adds %USERPROFILE%\\.local\\bin to User PATH. Does not sign you in.",
        });
        if (ask.response === 1) {
          await electronShell.openExternal(
            "https://code.claude.com/docs/en/installation",
          );
          break;
        }
        if (ask.response !== 0) {
          break;
        }
        applianceStatus = "Installing Claude Code CLI…";
        await renderContent();
        pushShell();
        const installed = await ensureClaudeCodeCli();
        applianceStatus = installed.message;
        await refreshClaudeAuth();
        await renderContent();
        pushShell();
        if (!installed.ok) {
          dialog.showErrorBox("Install Claude Code CLI", installed.message);
        }
        break;
      }
      case "verifyClaudeCodeAuth": {
        await refreshClaudeAuth();
        applianceStatus = `Claude Code: ${claudeCodeAuthStatusLabel(claudeAuth)}`;
        await renderContent();
        pushShell();
        break;
      }
      case "storeClaudeCodeSetupToken": {
        const { response, checkboxChecked } = await dialog.showMessageBox({
          type: "question",
          buttons: ["Paste from clipboard", "Cancel"],
          defaultId: 0,
          cancelId: 1,
          title: "Store Claude Code setup-token",
          message:
            "Copy the sk-ant-oat01-… token from `claude setup-token`, then paste from clipboard. Stored via Electron safeStorage.",
          checkboxLabel: "Also launch claude setup-token now",
          checkboxChecked: false,
        });
        if (checkboxChecked) {
          const started = startClaudeSetupToken();
          if (started.ok) {
            claudePendingSource = "claude_setup_token";
          }
        }
        if (response !== 0) {
          await refreshClaudeAuth();
          await renderContent();
          pushShell();
          break;
        }
        const pasted = clipboard.readText();
        const token = extractClaudeOAuthToken(pasted) ?? pasted.trim();
        if (!storeClaudeOAuthToken(token)) {
          applianceStatus =
            "Invalid token — expected sk-ant-oat01-… from claude setup-token.";
        } else {
          claudePendingSource = undefined;
          applianceStatus = "Claude Code setup-token stored in safeStorage.";
        }
        await refreshClaudeAuth();
        await renderContent();
        pushShell();
        break;
      }
      case "openClaudeCodeApiKeyBackup":
        applianceStatus =
          "Claude Code: API key backup — use setup wizard Backup / advanced (auth_mode=api_key_backup).";
        await renderContent();
        pushShell();
        break;
      case "openDeepSeek":
        currentNav = "deepseek";
        await renderContent();
        pushShell();
        break;
      case "openMorningReview":
        currentNav = "morning-review";
        await renderContent();
        pushShell();
        break;
      case "openOverview":
        currentNav = "overview";
        await renderContent();
        pushShell();
        break;
      case "openApprovals":
        currentNav = "approvals";
        await renderContent();
        pushShell();
        break;
      case "openMission":
        currentNav = "mission";
        await renderContent();
        pushShell();
        break;
      case "openVerification":
        currentNav = "verification";
        await renderContent();
        pushShell();
        break;
      case "openIntegration":
        currentNav = "integration";
        await renderContent();
        pushShell();
        break;
      case "startMission":
      case "pauseMission":
      case "resumeMission":
      case "cancelMission":
      case "approve":
      case "reject":
        // Disabled in UI until Gateway/CLI; ignore stray posts.
        break;
      case "setSessionToken": {
        const result = await dialog.showMessageBox(mainWindow!, {
          type: "question",
          title: "Session token",
          message: "Store a Gateway session token?",
          detail:
            "Paste is via a follow-up prompt. Token is written only under userData (never settings.json). Not used for /healthz today.",
          buttons: ["Continue", "Cancel"],
          cancelId: 1,
          noLink: true,
        });
        if (result.response === 0) {
          // Electron has no password InputBox; use a simple prompt dialog via clipboard paste instruction.
          const { response, checkboxChecked } = await dialog.showMessageBox(
            mainWindow!,
            {
              type: "info",
              title: "Paste token",
              message:
                "Copy your token to the clipboard, then click Store clipboard token.",
              buttons: ["Store clipboard token", "Cancel"],
              cancelId: 1,
              noLink: true,
              checkboxLabel: "I understand the token stays on this machine only",
              checkboxChecked: false,
            },
          );
          if (response === 0 && checkboxChecked) {
            setSessionToken(clipboard.readText());
            refreshAuth();
          }
        }
        await renderContent();
        pushShell();
        break;
      }
      case "clearSessionToken":
        clearSessionToken();
        refreshAuth();
        await renderContent();
        pushShell();
        break;
      default:
        break;
    }
  });

  ipcMain.handle("dde:openExternal", async (_e, url: string) => {
    await electronShell.openExternal(url);
  });
}

app.whenReady().then(async () => {
  loadSettings();
  refreshAuth();
  await refreshClaudeAuth();
  applianceStatus = detectAppliance();
  wireIpc();
  createWindow();
  await refreshProbe();
  await renderContent();
  pushShell();
  restartPoll();
  await maybeOfferFirstRun();
  applianceStatus = detectAppliance();
  await renderContent();
  pushShell();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
      void renderContent().then(pushShell);
    }
  });
});

app.on("window-all-closed", () => {
  if (pollTimer) {
    clearInterval(pollTimer);
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});
