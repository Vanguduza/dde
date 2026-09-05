import { expect, test } from "@playwright/test";

const FIXTURE = "/visual/live-loop.html";

test.describe("DDE-069 code-backed workbench loop", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FIXTURE);
    await expect(page.getByTestId("dde-shell")).toBeVisible();
  });

  test("fresh candidate requires explicit READY source selection when ambiguous", async ({
    page,
  }) => {
    await page.goto(`${FIXTURE}?fresh=1`);
    const start = page.getByTestId("start-preview");
    await expect(start).toBeDisabled();
    const source = page.getByTestId("source-workspace-select");
    await expect(source).toBeVisible();
    await expect(source).toHaveValue("");
    await source.selectOption("00000000-0000-0000-0000-000000000042");
    await expect(start).toBeEnabled();
    await start.click();
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    const parameters = await page.evaluate(() => {
      const bridge = (
        window as unknown as {
          __ddeTestBridge: {
            sentCommands: Array<{
              commandType: string;
              parameters: Record<string, unknown>;
            }>;
          };
        }
      ).__ddeTestBridge;
      return bridge.sentCommands.find(
        (command) => command.commandType === "frontend.preview.start",
      )?.parameters;
    });
    expect(parameters?.source_workspace_id).toBe(
      "00000000-0000-0000-0000-000000000042",
    );
  });

  test("browser handshake is required before LIVE is shown", async ({ page }) => {
    const badge = page.getByTestId("preview-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("LIVE");
    await expect(badge).toHaveAttribute("data-state", "LIVE");
    await expect(page.getByTestId("live-preview-surface")).toBeVisible();
  });

  test("verification evidence is visible in QA and never inferred from request state", async ({
    page,
  }) => {
    const candidate = page.getByTestId(
      "candidate-verification-00000000-0000-0000-0000-000000000020",
    );
    await expect(candidate).toHaveText("VERIFY PASSED");
    await page.getByTestId("mode-qa").click();
    await expect(page.getByTestId("qa-mode")).toBeVisible();
    await expect(page.getByTestId("qa-check-silhouette")).toContainText("PASSED");
    await expect(page.getByTestId("qa-check-visual_critique")).toContainText("PASSED");
    await expect(page.getByTestId("qa-mode")).toContainText("Evidence: 2");
  });

  test("Screen Audit matrix, QA and architecture modes render one current projection", async ({ page }) => {
    await page.getByTestId("mode-coverage").click();
    await expect(page.getByTestId("audit-screen-matrix")).toContainText("screens/checkout");
    await expect(page.getByTestId("audit-summary")).toContainText("1 blocking");
    await expect(page.getByTestId("audit-screen-screens/checkout")).toContainText("FAIL");

    await page.getByTestId("mode-qa").click();
    await expect(page.getByTestId("audit-findings")).toContainText("MISSING_ERROR_STATE");
    await expect(page.getByTestId("audit-findings")).toContainText("Checkout has no payment-error state");

    await page.getByTestId("mode-architecture").click();
    await expect(page.getByTestId("architecture-audit-mode")).toBeVisible();
    await expect(page.getByTestId("architecture-audit-mode")).toContainText("REQUIRED_VIEWPORT_UNVERIFIED");
  });

  test("stable pxg selection resolves a real Inspector descriptor", async ({ page }) => {
    const frame = page.frameLocator("iframe.dde-preview-frame");
    const hero = frame.locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await expect(hero).toContainText("Hero space2");
    await hero.click();

    const outline = page.getByTestId("selection-outline");
    await expect(outline).toBeVisible();
    await expect(outline).toHaveAttribute("data-pxg-key", "screens/checkout#hero");

    const spacing = page.getByTestId("inspector-property-spacing");
    await expect(spacing).toBeVisible();
    await expect(spacing).toHaveAttribute("data-writable", "true");
    await expect(spacing.locator("select")).toHaveValue("space2");
    await expect(page.getByTestId("inspector-verification-evidence")).toContainText(
      "Current screen evidence: PASSED",
    );
    await expect(page.getByTestId("inspector-verification-evidence")).toContainText(
      "visual_critique · PASSED",
    );
    await expect(page.getByTestId("inspector-audit")).toContainText("PARTIAL");
    await expect(page.getByTestId("inspector-audit")).toContainText("2 unresolved finding");
  });

  test("View source resolves the descriptor source through the host bridge", async ({ page }) => {
    const hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();
    await page.getByRole("button", { name: "View source" }).click();
    const revealed = await page.evaluate(() => {
      const bridge = (
        window as unknown as {
          __ddeTestBridge: { revealedFiles: Array<{ path: string }> };
        }
      ).__ddeTestBridge;
      return bridge.revealedFiles;
    });
    expect(revealed).toEqual([{ path: "prototypes/screens/checkout.html" }]);
  });

  test("Frontend Chat is permanent and exposes live scope context", async ({ page }) => {
    const chat = page.getByTestId("dde-chat");
    await expect(chat).toBeVisible();
    await expect(page.getByTestId("chat-input")).toBeVisible();
    const chrome = await chat.evaluate((element) => {
      const style = getComputedStyle(element);
      return { position: style.position, borderRadius: style.borderRadius };
    });
    const shellLayer = await page.getByTestId("dde-chat-layer").evaluate((element) => {
      const style = getComputedStyle(element);
      return { position: style.position, pointerEvents: style.pointerEvents };
    });
    expect(chrome).toEqual({ position: "relative", borderRadius: "12px" });
    expect(shellLayer).toEqual({ position: "fixed", pointerEvents: "none" });
    await expect(page.getByTestId("chat-context-chips")).toContainText("Checkout");
    await expect(page.getByTestId("chat-context-chips")).toContainText("Desktop 1440");

    const hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();
    await expect(page.getByTestId("chat-selection-chip")).toContainText("hero");

    await page.getByTestId("chat-settings").click();
    const settings = page.getByTestId("chat-context-settings");
    await expect(settings).toContainText("Checkout spacing refinement");
    await expect(settings).toContainText("Desktop 1440");
    await expect(settings).toContainText("/design checks certified provider availability");
  });

  test("deterministic Chat edit uses governed mutation then rerenders and reverifies", async ({
    page,
  }) => {
    const hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();
    await page.getByRole("button", { name: "Show DDE AI Chat" }).click();
    await page.getByTestId("chat-new").click();
    await page.getByTestId("chat-mode-execute").click();
    await page.getByTestId("chat-input").fill("set the spacing to space4");
    await page.getByTestId("chat-send").click();

    await expect(
      page
        .frameLocator("iframe.dde-preview-frame")
        .locator('[data-dde-pxg-key="screens/checkout#hero"]'),
    ).toContainText("Hero space4");
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    await expect(
      page.getByTestId(
        "candidate-verification-00000000-0000-0000-0000-000000000020",
      ),
    ).toHaveText("VERIFY PASSED");
    await expect(page.getByTestId("chat-thread")).toContainText(
      "set the spacing to space4",
    );
    await expect(page.getByTestId("chat-thread")).toContainText("applied 1 change(s)");
    await expect(page.getByTestId("chat-thread")).toContainText("MUTATE_DETERMINISTIC");

    const commands = await page.evaluate(() => {
      const bridge = (
        window as unknown as {
          __ddeTestBridge: { sentCommands: Array<{ commandType: string }> };
        }
      ).__ddeTestBridge;
      return bridge.sentCommands.map((item) => item.commandType);
    });
    expect(commands).toContain("frontend.chat.open");
    expect(commands).toContain("frontend.chat.set_context");
    expect(commands).toContain("frontend.chat.send");
    expect(commands).toContain("frontend.preview.start");
    expect(commands).toContain("frontend.verification.run");
    expect(commands).not.toContain("frontend.design.request");
  });

  test("removing the selection chip changes Chat scope without changing Canvas selection", async ({
    page,
  }) => {
    const hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();
    await expect(page.getByTestId("selection-outline")).toBeVisible();
    await page
      .getByRole("button", { name: "Remove selected element from Chat scope" })
      .click();
    await expect(page.getByTestId("chat-selection-excluded")).toBeVisible();
    await expect(page.getByTestId("selection-outline")).toBeVisible();

    await page.getByTestId("chat-input").fill("set the spacing to space4");
    await page.getByTestId("chat-send").click();
    await expect(page.getByTestId("chat-thread")).toContainText("AMBIGUOUS_REFERENCE");
    await expect(hero).toContainText("Hero space2");
  });

  test("read-only Chat questions answer from current project evidence", async ({ page }) => {
    await page.getByTestId("chat-input").fill("how much coverage do we have?");
    await page.getByTestId("chat-send").click();
    const thread = page.getByTestId("chat-thread");
    await expect(thread).toContainText("COVERAGE_QUERY");
    await expect(thread).toContainText(
      "Coverage PARTIAL: percentage unavailable; blocking findings=0",
    );

    await page.getByTestId("chat-input").fill("show me the QA findings");
    await page.getByTestId("chat-send").click();
    await expect(thread).toContainText("QA_QUERY");
    await expect(thread).toContainText("run=PASSED");
    await expect(thread).toContainText("evidence=2");
  });

  test("/design remains in the same Chat and fails honestly without a certified provider", async ({
    page,
  }) => {
    const hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();
    await page.getByRole("button", { name: "Show DDE AI Chat" }).click();
    await page.getByTestId("chat-new").click();
    await page.getByTestId("chat-mode-execute").click();
    await page.getByTestId("chat-input").fill("/design two hero alternatives");
    await page.getByTestId("chat-send").click();

    const thread = page.getByTestId("chat-thread");
    await expect(thread).toContainText("DESIGN_DIVERGENT");
    await expect(thread).toContainText("CAPABILITY_UNAVAILABLE");
    await expect(thread).toContainText("no certified design provider transport");
    await expect(hero).toContainText("Hero space2");
  });

  test("Chat undo creates a governed compensating edit and reverifies it", async ({ page }) => {
    let hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();
    await page.getByRole("button", { name: "Show DDE AI Chat" }).click();
    await page.getByTestId("chat-new").click();
    await page.getByTestId("chat-mode-execute").click();
    await page.getByTestId("chat-input").fill("set the spacing to space4");
    await page.getByTestId("chat-send").click();
    hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await expect(hero).toContainText("Hero space4");
    await expect(
      page.getByTestId(
        "candidate-verification-00000000-0000-0000-0000-000000000020",
      ),
    ).toHaveText("VERIFY PASSED");

    await page.getByTestId("chat-input").fill("undo");
    await page.getByTestId("chat-send").click();
    hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await expect(hero).toContainText("Hero space2");
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    await expect(
      page.getByTestId(
        "candidate-verification-00000000-0000-0000-0000-000000000020",
      ),
    ).toHaveText("VERIFY PASSED");
    await expect(page.getByTestId("chat-thread")).toContainText("UNDO_REVERT");
    await expect(page.getByTestId("chat-thread")).toContainText("reverted mutation 1");
  });

  test("Inspector mutation invalidates and rerenders the candidate", async ({ page }) => {
    const frame = page.frameLocator("iframe.dde-preview-frame");
    const hero = frame.locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();

    const spacing = page.getByTestId("inspector-property-spacing");
    await spacing.locator("select").selectOption("space4");
    await page.getByTestId("apply-spacing").click();

    await expect(
      page.frameLocator("iframe.dde-preview-frame").locator('[data-dde-pxg-key="screens/checkout#hero"]'),
    ).toContainText("Hero space4");
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    await expect(
      page.getByTestId(
        "candidate-verification-00000000-0000-0000-0000-000000000020",
      ),
    ).toHaveText("VERIFY PASSED");

    const commands = await page.evaluate(() => {
      const bridge = (
        window as unknown as {
          __ddeTestBridge: { sentCommands: Array<{ commandType: string }> };
        }
      ).__ddeTestBridge;
      return bridge.sentCommands.map((item) => item.commandType);
    });
    expect(commands).toContain("frontend.mutation.apply");
    expect(commands).toContain("frontend.preview.start");
    expect(
      commands.filter((item) => item === "frontend.preview.set_state").length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      commands.filter((item) => item === "frontend.verification.run").length,
    ).toBeGreaterThanOrEqual(2);
  });
});
