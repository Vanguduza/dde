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
