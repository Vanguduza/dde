import { expect, test } from "@playwright/test";

const FIXTURE = "/visual/live-loop.html";
const PXG_KEY = "screens/checkout#hero";

async function selectHero(page: import("@playwright/test").Page) {
  const hero = page
    .frameLocator("iframe.dde-preview-frame")
    .locator(`[data-dde-pxg-key="${PXG_KEY}"]`);
  await expect(hero).toBeVisible();
  await hero.click();
  await expect(page.getByTestId("inspector")).toContainText("Checkout hero");
}

test.describe("DDE-069 Inspector golden closure", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FIXTURE);
    await expect(page.getByTestId("dde-shell")).toBeVisible();
    await selectHero(page);
  });

  test("renders the six canonical Inspector tabs", async ({ page }) => {
    for (const [id, label] of [
      ["layout", "Layout"],
      ["style", "Style"],
      ["behaviour", "Behaviour"],
      ["responsive", "Responsive"],
      ["lock", "Lock"],
      ["source", "Source/code"],
    ] as const) {
      const tab = page.getByTestId(`inspector-tab-${id}`);
      await expect(tab).toBeVisible();
      await expect(tab).toHaveText(label);
    }
  });

  test("Layout exposes semantic identity and computed values", async ({ page }) => {
    await expect(page.getByTestId("inspector-property-layout_type")).toContainText("Type");
    await expect(page.getByTestId("inspector-property-layout_type")).toContainText("stack");
    await expect(page.getByTestId("inspector-property-direction")).toContainText("vertical");
    await expect(page.getByTestId("inspector-property-gap")).toContainText("space6 · 24px");
    await expect(page.getByTestId("inspector-property-padding")).toContainText("space8 · 40px");
  });

  test("Layout writes only the semantic token through governed mutation", async ({ page }) => {
    const gap = page.getByTestId("inspector-property-gap");
    await gap.locator("select").selectOption("space4");
    await page.getByTestId("apply-gap").click();
    const mutation = await page.evaluate(() => {
      const bridge = (window as unknown as { __ddeTestBridge: { sentCommands: Array<{ commandType: string; parameters: Record<string, unknown> }> } }).__ddeTestBridge;
      return bridge.sentCommands.filter((item) => item.commandType === "frontend.mutation.apply").at(-1);
    });
    const mutations = mutation?.parameters.mutations as Array<Record<string, unknown>>;
    const payload = mutations?.[0]?.payload as Record<string, unknown>;
    expect(payload).toEqual({ property: "gap", value: "space4" });
    await expect(page.frameLocator("iframe.dde-preview-frame").locator(`[data-dde-pxg-key="${PXG_KEY}"]`)).toHaveAttribute("data-gap", "space4");
  });

  test("Behaviour stays tokenized and never invents an animation preset", async ({ page }) => {
    await page.getByTestId("inspector-tab-behaviour").click();
    const panel = page.getByTestId("inspector-panel-behaviour");
    await expect(panel).toContainText("Tokenized duration and easing only");
    await expect(page.getByTestId("inspector-property-duration")).toContainText("Not set");
    await expect(page.getByTestId("inspector-property-easing")).toContainText("Not set");
    await expect(panel).not.toContainText("Fade In");
  });

  test("Responsive breakpoint starts an exact code-backed viewport preview", async ({ page }) => {
    await page.getByTestId("inspector-tab-responsive").click();
    await page.getByTestId("inspector-breakpoint-390").click();
    await expect(page.getByTestId("viewport-select")).toHaveValue("390");
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    const viewport = await page.evaluate(() => {
      const bridge = (window as unknown as { __ddeTestBridge: { sentCommands: Array<{ commandType: string; parameters: Record<string, unknown> }> } }).__ddeTestBridge;
      return bridge.sentCommands.filter((item) => item.commandType === "frontend.preview.start").at(-1)?.parameters.viewport;
    });
    expect(viewport).toBe("390");
  });

  test("Style Lock is real, visible, counted and reversible", async ({ page }) => {
    await page.getByTestId("inspector-tab-lock").click();
    await expect(page.getByTestId("inspector-locks")).toContainText("No effective lock");
    const lockChildren = page.getByTestId("explorer-children-locks");
    await expect(lockChildren).toContainText("Style Locks");
    await expect(lockChildren).toContainText("Section Locks");
    await expect(lockChildren).toContainText("Component Locks");
    await expect(lockChildren).toContainText("Behaviour Locks");
    await expect(page.getByTestId("explorer-group-lock:style").locator(".dde-count")).toHaveText("0");
    await page.getByTestId("create-style-lock").click();
    await expect(page.getByTestId("inspector-locks")).toContainText("STYLE");
    await expect(page.getByTestId("explorer-group-locks")).toContainText("1");
    await expect(page.getByTestId("explorer-group-lock:style").locator(".dde-count")).toHaveText("1");
    await expect(page.getByTestId("candidate-current")).toContainText("Current (Locked)");
    await expect(page.getByTestId("candidate-current-lock-state")).toHaveText("1 ACTIVE LOCK");

    await page.getByTestId("inspector-tab-layout").click();
    await expect(page.getByTestId("inspector-property-gap")).toHaveAttribute("data-writable", "false");

    await page.getByTestId("inspector-tab-lock").click();
    await page.getByRole("button", { name: "Release" }).click();
    await expect(page.getByTestId("inspector-locks")).toContainText("No effective lock");
    await expect(page.getByTestId("explorer-group-locks")).toContainText("0");
    await expect(page.getByTestId("explorer-group-lock:style").locator(".dde-count")).toHaveText("0");
    await expect(page.getByTestId("candidate-current-lock-state")).toHaveText("NO ACTIVE LOCKS");
  });

  test("Source/code reveals mapped source and keeps accessibility honest", async ({ page }) => {
    await page.getByTestId("inspector-tab-source").click();
    await expect(page.getByTestId("inspector-source-code")).toContainText("prototypes/screens/checkout.html");
    await page.getByTestId("inspector-view-source").click();
    const revealed = await page.evaluate(() => (window as unknown as { __ddeTestBridge: { revealedFiles: Array<{ path: string }> } }).__ddeTestBridge.revealedFiles);
    expect(revealed.at(-1)).toEqual({ path: "prototypes/screens/checkout.html" });
    await expect(page.getByTestId("inspector-accessibility")).toContainText("Not evaluated");
    await expect(page.getByTestId("inspector-accessibility")).not.toContainText("AA · No current audit issues");
  });
});
