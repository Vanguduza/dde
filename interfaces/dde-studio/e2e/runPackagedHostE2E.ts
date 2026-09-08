import { randomUUID } from "node:crypto";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { chromium, type Browser, type Frame, type Locator, type Page } from "playwright";
import {
  downloadAndUnzipVSCode,
  resolveCliArgsFromVSCodeExecutablePath,
} from "@vscode/test-electron";

const extensionRoot = path.resolve(__dirname, "../..");
const repoRoot = path.resolve(extensionRoot, "../..");
const python = path.join(repoRoot, ".venv", "bin", "python");
const version = "1.95.3";
let gatewayPort = 0;
let cdpPort = 0;
const dbName = `dde_vscode_e2e_${process.pid}_${randomUUID().slice(0, 8).replaceAll("-", "")}`;
const adminDsn = "postgresql://dde:dde@127.0.0.1:55432/dde";
const databaseUrl = `postgresql+asyncpg://dde:dde@127.0.0.1:55432/${dbName}`;
const tempRoot = mkdtempSync(path.join(tmpdir(), "dde-vscode-e2e-"));
const fixtureFile = path.join(tempRoot, "fixture.json");
const fixtureRepo = path.join(tempRoot, "fixture-repo");
const userData = path.join(tempRoot, "user-data");
const extensionsDir = path.join(tempRoot, "extensions");
let server: ChildProcess | undefined;
let vscodeProcess: ChildProcess | undefined;
let browser: Browser | undefined;
let fixtureEnv: NodeJS.ProcessEnv | undefined;

function run(
  command: string,
  args: readonly string[],
  env: NodeJS.ProcessEnv = process.env,
): void {
  const result = spawnSync(command, [...args], {
    cwd: repoRoot,
    env,
    stdio: "inherit",
  });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed (${result.status})`);
  }
}

async function freePort(): Promise<number> {
  return await new Promise<number>((resolve, reject) => {
    const socket = createServer();
    socket.once("error", reject);
    socket.listen(0, "127.0.0.1", () => {
      const address = socket.address();
      if (!address || typeof address === "string") {
        socket.close();
        reject(new Error("could not allocate a local TCP port"));
        return;
      }
      const port = address.port;
      socket.close((error) => (error ? reject(error) : resolve(port)));
    });
  });
}

function databaseScript(sql: string): void {
  const code = [
    "import asyncio, asyncpg, os",
    "async def main():",
    "    c=await asyncpg.connect(os.environ['DDE_E2E_ADMIN_DSN'])",
    "    try:",
    `        await c.execute(${JSON.stringify(sql)})`,
    "    finally:",
    "        await c.close()",
    "asyncio.run(main())",
  ].join("\n");
  run(python, ["-c", code], {
    ...process.env,
    DDE_E2E_ADMIN_DSN: adminDsn,
  });
}

async function waitForFixture(): Promise<Record<string, string>> {
  const deadline = Date.now() + 40_000;
  while (Date.now() < deadline) {
    if (existsSync(fixtureFile)) {
      try {
        const response = await fetch(`http://127.0.0.1:${gatewayPort}/readyz`);
        if (response.ok) {
          return JSON.parse(readFileSync(fixtureFile, "utf8")) as Record<string, string>;
        }
      } catch {
        // Gateway may still be binding after fixture creation.
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("packaged-host fixture/Gateway did not become ready");
}

async function waitForCdp(): Promise<void> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${cdpPort}/json/version`);
      if (response.ok) return;
    } catch {
      // VS Code is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("VS Code CDP endpoint did not become ready");
}


async function waitForProcessExit(
  process: ChildProcess,
  label: string,
  timeoutMs = 10_000,
): Promise<void> {
  if (process.exitCode !== null) return;
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      process.kill("SIGKILL");
      reject(new Error(`${label} did not exit after cleanup within ${timeoutMs}ms`));
    }, timeoutMs);
    process.once("exit", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

async function workbenchPage(): Promise<Page> {
  browser = await chromium.connectOverCDP(`http://127.0.0.1:${cdpPort}`);
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const pages = browser.contexts().flatMap((context) => context.pages());
    const page = pages.find((item) => item.url().includes("workbench")) ?? pages[0];
    if (page) return page;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("VS Code workbench page did not appear");
}

function displaySlug(slug: string): string {
  return slug
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

async function waitForText(
  locator: Locator,
  expected: string,
  label: string,
): Promise<void> {
  const deadline = Date.now() + 20_000;
  let observed = "";
  while (Date.now() < deadline) {
    observed = (await locator.textContent()) ?? "";
    if (observed.includes(expected)) return;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`${label} did not contain ${expected}; observed ${observed}`);
}


async function waitForAttribute(
  locator: Locator,
  name: string,
  expected: string,
  label: string,
): Promise<void> {
  const deadline = Date.now() + 20_000;
  let observed: string | null = null;
  while (Date.now() < deadline) {
    observed = await locator.getAttribute(name);
    if (observed === expected) return;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`${label} did not bind ${name}=${expected}; observed ${observed}`);
}

async function waitForInputValue(
  locator: Locator,
  expected: string,
  label: string,
): Promise<void> {
  const deadline = Date.now() + 20_000;
  let observed = "";
  while (Date.now() < deadline) {
    observed = await locator.inputValue();
    if (observed === expected) return;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`${label} did not bind ${expected}; observed ${observed}`);
}

async function ddeFrame(page: Page): Promise<Frame> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    for (const frame of page.frames()) {
      if (await frame.getByTestId("dde-shell").count()) return frame;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("DDE Frontend Studio webview did not expose the DDE shell");
}

async function projectFrame(page: Page, expectedProjectId: string): Promise<Frame> {
  const deadline = Date.now() + 30_000;
  let observed: Array<Record<string, string>> = [];
  while (Date.now() < deadline) {
    observed = [];
    for (const frame of page.frames()) {
      try {
        const shell = frame.getByTestId("dde-shell");
        const project = frame.getByTestId("project-selector");
        if ((await shell.count()) && (await project.count())) {
          const projectId = await project.inputValue();
          const screen = frame.getByTestId("screen-select");
          const screenKey = (await screen.count()) ? await screen.inputValue() : "";
          const error = frame.getByTestId("project-switch-error");
          const errorText = (await error.count()) ? (await error.textContent()) ?? "" : "";
          observed.push({ projectId, screenKey, errorText });
          if (projectId === expectedProjectId) return frame;
        }
      } catch {
        // A prior webview frame may detach while switchFrontendMission reloads it.
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`DDE webview did not switch to project ${expectedProjectId}; observed ${JSON.stringify(observed)}`);
}

async function main(): Promise<void> {
  gatewayPort = await freePort();
  do {
    cdpPort = await freePort();
  } while (cdpPort === gatewayPort);
  databaseScript(`CREATE DATABASE ${dbName}`);
  const env = {
    ...process.env,
    DDE_DATABASE_URL: databaseUrl,
    DDE_REDIS_URL: "redis://127.0.0.1:56379/0",
    DDE_PACKAGED_E2E_FIXTURE_FILE: fixtureFile,
    DDE_PACKAGED_E2E_FIXTURE_REPO: fixtureRepo,
    DDE_PACKAGED_E2E_GATEWAY_PORT: String(gatewayPort),
  };
  fixtureEnv = env;
  run(python, ["-m", "alembic", "upgrade", "head"], env);
  server = spawn(
    python,
    [path.join(extensionRoot, "e2e", "fixture_server.py")],
    { cwd: repoRoot, env, stdio: ["ignore", "inherit", "inherit"] },
  );
  const fixture = await waitForFixture();

  mkdirSync(path.join(userData, "User"), { recursive: true });
  mkdirSync(extensionsDir, { recursive: true });
  writeFileSync(
    path.join(userData, "User", "settings.json"),
    JSON.stringify({
      "dde.studio.coreUrl": `http://127.0.0.1:${gatewayPort}`,
      "dde.studio.preferredTarget": "local",
      "dde.studio.principalId": fixture.principal_id,
      "dde.studio.frontendMissionId": fixture.mission_id,
      "security.workspace.trust.enabled": false,
      "workbench.startupEditor": "none",
    }),
    "utf8",
  );

  const executable = await downloadAndUnzipVSCode(version);
  if (process.env.DDE_PACKAGED_E2E_REUSE_VSIX !== "1") {
    run("npm", ["--prefix", extensionRoot, "run", "package"]);
  }
  const vsixName = readdirSync(extensionRoot).find((name) => name.endsWith(".vsix"));
  if (!vsixName) throw new Error("VSIX package was not produced");
  const vsixPath = path.join(extensionRoot, vsixName);
  const [cli, ...cliArgs] = resolveCliArgsFromVSCodeExecutablePath(executable);
  run(cli, [
    ...cliArgs,
    "--install-extension",
    vsixPath,
    "--extensions-dir",
    extensionsDir,
    "--force",
  ]);
  vscodeProcess = spawn(
    executable,
    [
      fixtureRepo,
      "--no-sandbox",
      "--disable-gpu-sandbox",
      "--disable-updates",
      "--no-cached-data",
      `--user-data-dir=${userData}`,
      `--extensions-dir=${extensionsDir}`,
      "--skip-welcome",
      "--skip-release-notes",
      "--disable-workspace-trust",
      "--disable-gpu",
      `--remote-debugging-port=${cdpPort}`,
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["ignore", "inherit", "inherit"],
    },
  );

  await waitForCdp();
  const page = await workbenchPage();
  await page.waitForTimeout(1_500);
  await page.keyboard.press("Control+Shift+P");
  const commandInput = page.locator(".quick-input-widget:visible .quick-input-box input").first();
  await commandInput.waitFor({ state: "visible", timeout: 20_000 });
  console.log("PACKAGED_HOST_PALETTE_BEFORE", JSON.stringify(await commandInput.inputValue()));
  await commandInput.fill("");
  await commandInput.pressSequentially(">Open Frontend Studio Workbench", { delay: 8 });
  console.log("PACKAGED_HOST_PALETTE_AFTER", JSON.stringify(await commandInput.inputValue()));
  const paletteRows = page.locator(
    ".quick-input-widget:visible .quick-input-list .monaco-list-row",
  );
  await paletteRows.first().waitFor({ state: "visible", timeout: 20_000 });
  const rowTexts = await paletteRows.allTextContents();
  console.log("PACKAGED_HOST_PALETTE_ROWS", JSON.stringify(rowTexts.slice(0, 10)));
  const ddeCommand = paletteRows.filter({ hasText: "Open Frontend Studio Workbench" }).first();
  if ((await ddeCommand.count()) === 0) {
    throw new Error(`DDE Frontend Studio command row not found: ${JSON.stringify(rowTexts)}`);
  }
  await ddeCommand.click();

  const frame = await ddeFrame(page);
  await frame.getByTestId("dde-shell").waitFor({ state: "visible", timeout: 20_000 });
  const project = frame.getByTestId("project-selector");
  await project.waitFor({ state: "visible", timeout: 20_000 });
  await waitForInputValue(project, fixture.project_id, "project selector");
  const screen = frame.getByTestId("screen-select");
  await screen.waitFor({ state: "visible", timeout: 20_000 });
  await waitForInputValue(screen, fixture.screen_key, "screen selector");

  // Packaged-host read projection batch: these assertions prove the installed
  // extension/webview is consuming real Gateway/PostgreSQL state, not just
  // rendering the host-neutral fixture successfully.
  const projectDisplay = displaySlug(fixture.project_slug);
  await waitForText(
    frame.getByTestId("explorer-project-heading"),
    projectDisplay,
    "Explorer project heading",
  );
  await frame.getByTestId("explorer-project-menu").click();
  const projectMenu = frame.getByTestId("explorer-project-menu-popover");
  await projectMenu.waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(projectMenu, fixture.project_id, "Explorer project menu project id");
  await waitForText(projectMenu, "PXG revision 1", "Explorer project menu PXG revision");
  await frame.getByTestId("explorer-project-menu").click();

  await frame.getByTestId("explorer-search").click();
  const explorerSearch = frame.getByTestId("explorer-search-input");
  await explorerSearch.waitFor({ state: "visible", timeout: 20_000 });
  await explorerSearch.fill("screens");
  const screensGroup = frame.getByTestId("explorer-group-screens");
  await screensGroup.waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(screensGroup.locator(".dde-count"), "1", "Screens group count");
  if ((await frame.getByTestId("explorer-group-journeys").count()) !== 0) {
    throw new Error("Explorer search did not filter Journeys for the screens query");
  }
  if ((await frame.getByTestId("explorer-group-components").count()) !== 0) {
    throw new Error("Explorer search did not filter Components for the screens query");
  }
  await explorerSearch.fill("");

  for (const [kind, label] of [
    ["style", "Style Locks"],
    ["section", "Section Locks"],
    ["component", "Component Locks"],
    ["behaviour", "Behaviour Locks"],
  ] as const) {
    const lockRow = frame.getByTestId(`explorer-group-lock:${kind}`);
    await lockRow.waitFor({ state: "visible", timeout: 20_000 });
    await waitForText(lockRow, label, `${label} row`);
    await waitForText(lockRow.locator(".dde-count"), "0", `${label} count`);
  }

  const buildVersion = frame.getByTestId("build-version");
  await buildVersion.waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(buildVersion, "0.1.0", "installed DDE build version");
  await waitForText(buildVersion, "PXG r1", "packaged-host PXG revision");

  // Universal DDE Chat is exercised through the installed extension with a
  // deterministic project-evidence query, so this proof does not depend on
  // any external model/provider.
  const chatInput = frame.getByTestId("chat-input");
  await chatInput.waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(frame.getByTestId("chat-context-chips"), "checkout", "Chat screen context");
  await waitForText(frame.getByTestId("chat-context-chips"), "Desktop 1440", "Chat viewport context");
  await frame.getByTestId("chat-settings").click();
  const chatSettings = frame.getByTestId("chat-context-settings");
  await chatSettings.waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(chatSettings, "checkout", "Chat context settings screen");
  await waitForText(chatSettings, "Desktop 1440", "Chat context settings viewport");
  await frame.getByTestId("chat-settings").click();
  await chatInput.fill("how much coverage do we have?");
  await frame.getByTestId("chat-send").click();
  const chatThread = frame.getByTestId("chat-thread");
  await waitForText(chatThread, "COVERAGE_QUERY", "Chat persisted intent");
  await waitForText(chatThread, "Coverage UNASSESSED", "Chat project-evidence response");
  await waitForText(chatThread, "percentage unavailable", "Chat honest coverage state");

  // READY candidate / code-backed preview / Inspector proof. The candidate
  // and workspace are persisted through production services by fixture_server.py.
  const candidateCard = frame.getByTestId(`candidate-${fixture.candidate_id}`);
  await candidateCard.waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(candidateCard, "Packaged Direction A", "candidate title");
  await waitForText(candidateCard, "READY", "candidate state");
  await waitForText(candidateCard, "0 changes", "candidate change count");
  const candidateScore = frame.getByTestId(`candidate-score-${fixture.candidate_id}`);
  await waitForText(candidateScore, "UNSCORED", "candidate score classification");
  await candidateScore.click();
  await waitForText(
    frame.getByTestId(`candidate-score-explanation-${fixture.candidate_id}`),
    "No complete score dimensions are available",
    "candidate score explanation",
  );
  const candidateThumbnail = frame.getByTestId(`candidate-thumbnail-${fixture.candidate_id}`);
  await candidateThumbnail.waitFor({ state: "visible", timeout: 20_000 });
  await waitForAttribute(candidateThumbnail, "data-state", "NOT_RENDERED", "candidate thumbnail before Try Live");

  await frame.getByTestId(`candidate-try-live-${fixture.candidate_id}`).click();
  const previewBadge = frame.getByTestId("preview-badge");
  await waitForText(previewBadge, "LIVE", "candidate Try Live preview state");
  await waitForAttribute(candidateThumbnail, "data-state", "RENDERED", "candidate thumbnail after Try Live");

  const previewFrame = frame.locator("iframe.dde-preview-frame").contentFrame();
  const hero = previewFrame.locator('[data-dde-pxg-key="screens/checkout#hero"]');
  await hero.waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(hero, "Hero space2", "instrumented code-backed hero");
  await frame.evaluate(() => {
    const host = globalThis as any;
    host.__ddePackagedPreviewMessages = [];
    host.addEventListener("message", (event: any) => {
      const data = event.data as { type?: unknown };
      if (data?.type === "dde.preview") host.__ddePackagedPreviewMessages.push(data);
    });
  });
  await hero.evaluate((element: any) => {
    const child = globalThis as any;
    child.__ddePackagedClickTargets = [];
    element.ownerDocument.addEventListener("click", (event: any) => {
      const target = event.target?.closest?.("[data-dde-pxg-key]") ?? null;
      child.__ddePackagedClickTargets.push(target?.getAttribute?.("data-dde-pxg-key") ?? "NONE");
    }, true);
  });
  await hero.click();
  const physicalClickTargets = await hero.evaluate(
    () => (globalThis as any).__ddePackagedClickTargets ?? [],
  );
  if (physicalClickTargets.length === 0) {
    // VS Code's CDP target does not route Playwright's physical click into a
    // nested srcdoc frame on this headless host. Host-neutral Playwright
    // separately proves real click delivery; dispatch the same production
    // click event here so the installed-VSIX runtime/postMessage/React
    // path is still exercised without a test-only application bypass.
    await hero.dispatchEvent("click", { bubbles: true, composed: true });
  }

  const selectionOutline = frame.getByTestId("selection-outline");
  try {
    await selectionOutline.waitFor({ state: "visible", timeout: 20_000 });
  } catch (error) {
    console.error("PACKAGED_HOST_SELECTION_DEBUG", JSON.stringify({
      clickTargets: await hero.evaluate(() => (globalThis as any).__ddePackagedClickTargets ?? []),
      previewMessages: await frame.evaluate(() => (globalThis as any).__ddePackagedPreviewMessages ?? []),
    }));
    throw error;
  }
  await waitForAttribute(
    selectionOutline,
    "data-pxg-key",
    "screens/checkout#hero",
    "stable PXG selection",
  );
  const breadcrumb = frame.getByTestId("breadcrumb");
  await waitForText(breadcrumb, projectDisplay, "selection breadcrumb project");
  await waitForText(breadcrumb, "Checkout", "selection breadcrumb screen");
  await waitForText(breadcrumb, "Checkout hero", "selection breadcrumb node");

  const inspector = frame.getByTestId("inspector");
  await waitForText(inspector, "Checkout hero", "Inspector selected-node title");
  await waitForText(inspector, "region", "Inspector selected-node kind");
  await waitForText(inspector, "source verified", "Inspector source mapping");
  for (const [property, value] of [
    ["layout_type", "stack"],
    ["direction", "vertical"],
    ["gap", "space2"],
    ["padding", "space2"],
  ] as const) {
    await waitForText(
      frame.getByTestId(`inspector-property-${property}`),
      value,
      `Inspector ${property}`,
    );
  }
  await waitForText(
    frame.getByTestId("inspector-property-gap"),
    "space2 · 8px",
    "Inspector gap token and computed pixels",
  );

  await frame.getByTestId("inspector-tab-style").click();
  await frame.getByTestId("inspector-panel-style").waitFor({ state: "visible", timeout: 20_000 });

  await frame.getByTestId("inspector-tab-lock").click();
  await frame.getByTestId("create-style-lock").click();
  await frame.getByTestId("selection-style-lock").waitFor({ state: "visible", timeout: 20_000 });
  await frame.getByTestId("create-section-lock").click();
  await frame.getByTestId("selection-section-lock").waitFor({ state: "visible", timeout: 20_000 });
  await waitForText(frame.getByTestId("candidate-current"), "Current (Locked)", "accepted lock state");

  await frame.getByTestId("inspector-tab-source").click();
  await waitForText(
    frame.getByTestId("inspector-source-code"),
    "prototypes/screens/checkout.html",
    "Inspector source path",
  );
  await waitForText(
    frame.getByTestId("inspector-provenance"),
    "No attributable external/source provenance",
    "Inspector project-native provenance state",
  );
  await waitForText(
    frame.getByTestId("inspector-accessibility"),
    "Not evaluated",
    "Inspector accessibility evidence state",
  );

  // Responsive preview starts a new session and intentionally clears stale
  // selection geometry. Exercise it last while the selected-node Inspector is
  // still authoritative, then require the replacement session to reach LIVE.
  await frame.getByTestId("inspector-tab-responsive").click();
  await frame.getByTestId("inspector-breakpoint-390").click();
  await waitForInputValue(frame.getByTestId("viewport-select"), "390", "responsive viewport selector");
  await waitForText(previewBadge, "LIVE", "responsive code-backed preview state");

  await project.selectOption(fixture.second_project_id);
  const secondFrame = await projectFrame(page, fixture.second_project_id);
  const secondScreen = secondFrame.getByTestId("screen-select");
  await secondScreen.waitFor({ state: "visible", timeout: 20_000 });
  await waitForInputValue(
    secondScreen,
    fixture.second_screen_key,
    "second project screen selector",
  );
  const secondProject = secondFrame.getByTestId("project-selector");
  await secondProject.selectOption(fixture.project_id);
  const returnedFrame = await projectFrame(page, fixture.project_id);
  await waitForInputValue(
    returnedFrame.getByTestId("screen-select"),
    fixture.screen_key,
    "returned project screen selector",
  );

  const response = await fetch(`http://127.0.0.1:${gatewayPort}/readyz`);
  const ready = (await response.json()) as {
    status?: string;
    database?: boolean;
    migrations?: string;
  };
  if (
    !response.ok ||
    ready.status !== "ready" ||
    ready.database !== true ||
    ready.migrations !== "head"
  ) {
    throw new Error(`Gateway readiness mismatch: ${JSON.stringify(ready)}`);
  }
  console.log(
    `PACKAGED_HOST_E2E_PASS ${JSON.stringify({
      host: "vscode",
      vscodeVersion: version,
      projectId: fixture.project_id,
      missionId: fixture.mission_id,
      screenKey: fixture.screen_key,
      switchedProjectId: fixture.second_project_id,
      switchedScreenKey: fixture.second_screen_key,
      returnedProjectId: fixture.project_id,
      verifiedControls: [
        "EX-02",
        "EX-03",
        "EX-04",
        "EX-16",
        "EX-17",
        "EX-18",
        "EX-19",
        "ST-06",
        "CH-01",
        "CH-03",
        "CH-04",
        "CT-01",
        "CV-01",
        "CV-02",
        "CV-04",
        "CV-06",
        "CV-07",
        "CA-01",
        "CA-02",
        "CA-03",
        "CA-04",
        "CA-05",
        "CA-06",
        "IN-01",
        "IN-06",
        "IN-07",
        "IN-13",
        "IN-15",
        "IN-16",
        "ST-01",
      ],
      database: ready.database,
      migrations: ready.migrations,
    })}`,
  );
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    if (browser) await browser.close().catch(() => undefined);
    if (vscodeProcess && vscodeProcess.exitCode === null) vscodeProcess.kill("SIGTERM");
    if (fixtureEnv && existsSync(fixtureFile)) {
      try {
        run(python, [path.join(extensionRoot, "e2e", "fixture_server.py"), "--cleanup-only"], fixtureEnv);
      } catch (error) {
        console.error("packaged-host fixture workspace cleanup failed", error);
        process.exitCode = 1;
      }
    }
    if (server && server.exitCode === null) {
      server.kill("SIGTERM");
      try {
        await waitForProcessExit(server, "packaged-host Gateway fixture");
      } catch (error) {
        console.error(error);
        process.exitCode = 1;
      }
    }
    try {
      databaseScript(`DROP DATABASE IF EXISTS ${dbName} WITH (FORCE)`);
    } catch (error) {
      console.error("scratch database cleanup failed", error);
      process.exitCode = 1;
    }
    rmSync(tempRoot, { recursive: true, force: true });
  });
