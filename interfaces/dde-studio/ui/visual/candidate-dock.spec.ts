import { expect, test } from "@playwright/test";

const FIXTURE = "/visual/live-loop.html";
const PRIMARY = "00000000-0000-0000-0000-000000000020";
const SECONDARY = "00000000-0000-0000-0000-000000000021";

test.describe("DDE-069 golden candidate dock", () => {
  test("renders accepted-current truth, real thumbnail, change count and explainable score", async ({ page }) => {
    await page.goto(FIXTURE);
    await expect(page.getByTestId("candidate-current")).toContainText("Accepted revision · PXG r4");
    await expect(page.getByTestId("candidate-current-lock-state")).toHaveText("LOCK STATE —");

    const thumbnail = page.getByTestId(`candidate-thumbnail-${PRIMARY}`);
    await expect(thumbnail).toHaveAttribute("data-state", "RENDERED");
    await expect(page.getByTestId(`candidate-${PRIMARY}`)).toContainText("0 changes");

    const score = page.getByTestId(`candidate-score-${PRIMARY}`);
    await expect(score).toContainText("GOOD");
    await score.click();
    const explanation = page.getByTestId(`candidate-score-explanation-${PRIMARY}`);
    await expect(explanation).toBeVisible();
    await expect(explanation).toContainText("product_fit: 88%");
    await expect(explanation).toContainText("Score evidence");
  });

  test("Try Live opens the exact existing code-backed candidate preview", async ({ page }) => {
    await page.goto(FIXTURE);
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    await page.getByTestId(`candidate-try-live-${PRIMARY}`).click();
    await expect(page.getByTestId("live-preview-surface")).toBeVisible();
    await expect(
      page.frameLocator("iframe.dde-preview-frame").locator('[data-dde-pxg-key="screens/checkout#hero"]'),
    ).toContainText("Hero space2");
  });

  test("Compare shows two real LIVE preview documents side by side", async ({ page }) => {
    await page.goto(`${FIXTURE}?compare=1`);
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    const compare = page.getByTestId(`candidate-compare-${SECONDARY}`);
    await expect(compare).toBeEnabled();
    await compare.click();
    const mode = page.getByTestId("candidate-compare-mode");
    await expect(mode).toBeVisible();
    await expect(mode).toContainText("Checkout spacing refinement");
    await expect(mode).toContainText("Checkout alternate");
    await expect(mode.getByTestId(`candidate-thumbnail-${PRIMARY}`)).toHaveAttribute("data-state", "RENDERED");
    await expect(mode.getByTestId(`candidate-thumbnail-${SECONDARY}`)).toHaveAttribute("data-state", "RENDERED");
  });

  test("Promote is explicit, governed and refreshes the accepted revision", async ({ page }) => {
    await page.goto(`${FIXTURE}?promotable=1`);
    const promote = page.getByTestId(`candidate-promote-${PRIMARY}`);
    await expect(promote).toBeEnabled();
    await promote.click();
    await expect(page.getByTestId("candidate-current")).toContainText("PXG r5");
    await expect(page.getByTestId(`candidate-${PRIMARY}`)).toContainText("PROMOTED");
    const commands = await page.evaluate(() => (
      window as unknown as { __ddeTestBridge: { sentCommands: Array<{ commandType: string }> } }
    ).__ddeTestBridge.sentCommands.map((item) => item.commandType));
    expect(commands).toContain("frontend.candidate.promote");
  });

  test("hard score failures are visible and cannot be averaged into promotion", async ({ page }) => {
    await page.goto(`${FIXTURE}?hardfail=1`);
    await expect(page.getByTestId(`candidate-hard-failure-${PRIMARY}`)).toContainText("LICENSE_INCOMPATIBLE");
    await expect(page.getByTestId(`candidate-score-${PRIMARY}`)).toContainText("BLOCKED");
    await expect(page.getByTestId(`candidate-promote-${PRIMARY}`)).toBeDisabled();
  });
});
