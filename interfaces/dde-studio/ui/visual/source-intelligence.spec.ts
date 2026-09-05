import { expect, test } from "@playwright/test";

const FIXTURE = "/visual/live-loop.html";
const ARTIFACT = "00000000-0000-0000-0000-000000000111";
const CANDIDATE = "00000000-0000-0000-0000-000000000020";

test.describe("DDE-069 M8 Source Intelligence", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FIXTURE);
    await expect(page.getByTestId("dde-shell")).toBeVisible();
    await page.getByTestId("mode-source").click();
    await expect(page.getByTestId("source-mode")).toBeVisible();
  });

  test("source inventory is real and provider degradation stays visible", async ({ page }) => {
    await expect(page.getByTestId("source-provider-project-native")).toContainText("AVAILABLE");
    await expect(page.getByTestId("source-provider-project-native")).toContainText("3 item(s)");
    await expect(page.getByTestId("source-provider-dde-library")).toContainText("0 item(s)");
    await expect(page.getByTestId("source-provider-donors")).toContainText("1 item(s)");
    await expect(page.getByTestId("source-provider-21st")).toContainText("NOT_CONFIGURED");
    await expect(page.getByTestId("source-provider-21st")).toContainText(
      "21st MCP/provider transport is not configured",
    );
    await expect(page.getByTestId("explorer-children-sources")).toContainText("Internal Components");
    await expect(page.getByTestId("explorer-children-sources")).toContainText("21st MCP");
  });

  test("search inspect fetch and admission are explicit governed stages", async ({ page }) => {
    await page.getByTestId("source-search-input").fill("checkout");
    await page.getByTestId("source-search").click();
    const artifact = page.getByTestId(`source-artifact-${ARTIFACT}`);
    await expect(artifact).toContainText("Checkout Hero");
    await expect(artifact).toContainText("INDEXED");

    await page.getByTestId(`source-inspect-${ARTIFACT}`).click();
    await expect(artifact).toContainText("INSPECTED");
    await page.getByTestId(`source-fetch-${ARTIFACT}`).click();
    await expect(artifact).toContainText("FETCHED");
    await expect(artifact).toContainText("bytes LOCAL · 128");
    await page.getByTestId(`source-admit-${ARTIFACT}`).click();
    await expect(artifact).toContainText("ADMITTED");

    const commands = await page.evaluate(() =>
      (window as unknown as { __ddeTestBridge: { sentCommands: Array<{ commandType: string }> } })
        .__ddeTestBridge.sentCommands.map((item) => item.commandType),
    );
    expect(commands).toEqual(expect.arrayContaining([
      "frontend.source.search",
      "frontend.source.inspect",
      "frontend.source.fetch",
      "frontend.source.admit",
    ]));
  });

  test("template recommendations never hide missing admission", async ({ page }) => {
    await page.getByTestId("source-search-input").fill("checkout");
    await page.getByTestId("source-search").click();
    await page.getByTestId("source-recommend-templates").click();
    await expect(page.getByTestId("source-templates")).toContainText("Checkout Hero Foundation");
    await expect(page.getByTestId("source-templates")).toContainText("UNAVAILABLE");
    await expect(page.getByTestId("source-templates")).toContainText("SOURCE_ADMISSION_REQUIRED");

    await page.getByTestId(`source-inspect-${ARTIFACT}`).click();
    await page.getByTestId(`source-fetch-${ARTIFACT}`).click();
    await page.getByTestId(`source-admit-${ARTIFACT}`).click();
    await page.getByTestId("source-recommend-templates").click();
    await expect(page.getByTestId("source-templates")).toContainText("RECOMMENDED");
  });

  test("candidate score is evidence backed and never a fabricated percentage", async ({ page }) => {
    const score = page.getByTestId(`candidate-score-${CANDIDATE}`);
    await expect(score).toContainText("88% · GOOD");
    await expect(score).toContainText("2 evidence");
  });

  test("target blend is future preference and does not rewrite actual attribution", async ({ page }) => {
    const apply = page.getByTestId("source-blend-apply");
    await expect(page.getByTestId("source-blend-unsaved")).toBeVisible();
    await expect(apply).toBeDisabled();
    await page.getByTestId("source-blend-project-native").fill("70");
    await page.getByTestId("source-blend-donors").fill("30");
    await expect(page.getByTestId("source-blend-total")).toHaveText("Total 100%");
    await expect(apply).toBeEnabled();
    await apply.click();
    await expect(page.getByTestId("source-blend-saved")).toContainText("Saved");
    await expect(page.getByTestId("source-attribution")).toContainText(
      "No attributable source provenance for the current selection.",
    );
    const command = await page.evaluate(() =>
      (window as unknown as {
        __ddeTestBridge: {
          sentCommands: Array<{ commandType: string; parameters: Record<string, unknown> }>;
        };
      }).__ddeTestBridge.sentCommands.find(
        (item) => item.commandType === "frontend.source.target_blend.set",
      ),
    );
    expect(command?.parameters.weights).toEqual({
      "project-native": 0.7,
      "dde-library": 0,
      "21st": 0,
      donors: 0.3,
    });
  });
  test("accepted provenance drives Source attribution and Inspector provenance", async ({ page }) => {
    await page.goto(`${FIXTURE}?provenance=1`);
    await expect(page.getByTestId("dde-shell")).toBeVisible();
    const hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await hero.click();
    await expect(page.getByTestId("inspector-provenance")).toContainText("REUSED");
    await expect(page.getByTestId("inspector-provenance")).toContainText("OPEN_REUSE");
    await page.getByTestId("mode-source").click();
    await expect(page.getByTestId("source-attribution")).toContainText("REUSED");
    await expect(page.getByTestId("source-attribution")).toContainText("100%");
  });

  test("universal DDE Chat searches governed sources and reports provider degradation", async ({ page }) => {
    await page.getByTestId("chat-input").fill("find checkout components");
    await page.getByTestId("chat-send").click();
    const thread = page.getByTestId("chat-thread");
    await expect(thread).toContainText("SEARCH_SOURCE");
    await expect(thread).toContainText("Checkout Hero");
    await expect(thread).toContainText("degraded providers: 21st");
    await page.getByTestId("mode-source").click();
    await expect(page.getByTestId(`source-artifact-${ARTIFACT}`)).toContainText("INDEXED");
  });

});
