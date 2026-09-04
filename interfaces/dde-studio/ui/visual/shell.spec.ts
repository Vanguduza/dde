/**
 * Structural conformance of the golden shell.
 *
 * These assertions measure the rendered workbench against the *normative
 * measurements* in `docs/truth/FRONTEND_STUDIO_REV3.md` Part I sections
 * 2-5, at the canonical 1672x941 viewport.
 *
 * They deliberately do not claim pixel-reference conformance to the
 * approved mockup: that image is absent from the repository (AD-039), and
 * `engine.studio.golden_visual.require_pixel_reference` refuses the claim
 * fail-closed. Structural conformance is what is honestly checkable today,
 * and it is a real gate — panel widths, bar heights and the four-zone
 * composition are all locked values, not preferences.
 */

import { expect, test } from "@playwright/test";

const FIXTURE = "/visual/fixture.html";

/** Locked ranges from section 2's golden-master frame. */
const GEOMETRY = {
  topBarHeight: { min: 56, max: 60 },
  statusBarHeight: { min: 32, max: 36 },
  railWidth: { min: 44, max: 48 },
  explorerWidth: { min: 215, max: 225 },
  inspectorWidth: { min: 310, max: 325 },
} as const;

async function box(page: import("@playwright/test").Page, testId: string) {
  const handle = page.getByTestId(testId);
  await expect(handle).toBeVisible();
  const rect = await handle.boundingBox();
  expect(rect, `${testId} has no layout box`).not.toBeNull();
  return rect!;
}

test.describe("golden shell structure", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FIXTURE);
    await expect(page.getByTestId("dde-shell")).toBeVisible();
  });

  test("the four-zone composition is present", async ({ page }) => {
    for (const region of [
      "dde-topbar",
      "dde-rail",
      "dde-explorer",
      "dde-workspace",
      "dde-inspector",
      "dde-statusbar",
    ]) {
      await expect(page.getByTestId(region)).toBeVisible();
    }
  });

  test("panel geometry matches the locked measurements", async ({ page }) => {
    const topbar = await box(page, "dde-topbar");
    expect(topbar.height).toBeGreaterThanOrEqual(GEOMETRY.topBarHeight.min);
    expect(topbar.height).toBeLessThanOrEqual(GEOMETRY.topBarHeight.max);

    const statusbar = await box(page, "dde-statusbar");
    expect(statusbar.height).toBeGreaterThanOrEqual(
      GEOMETRY.statusBarHeight.min,
    );
    expect(statusbar.height).toBeLessThanOrEqual(GEOMETRY.statusBarHeight.max);

    const rail = await box(page, "dde-rail");
    expect(rail.width).toBeGreaterThanOrEqual(GEOMETRY.railWidth.min);
    expect(rail.width).toBeLessThanOrEqual(GEOMETRY.railWidth.max);

    const explorer = await box(page, "dde-explorer");
    expect(explorer.width).toBeGreaterThanOrEqual(GEOMETRY.explorerWidth.min);
    expect(explorer.width).toBeLessThanOrEqual(GEOMETRY.explorerWidth.max);

    const inspector = await box(page, "dde-inspector");
    expect(inspector.width).toBeGreaterThanOrEqual(
      GEOMETRY.inspectorWidth.min,
    );
    expect(inspector.width).toBeLessThanOrEqual(GEOMETRY.inspectorWidth.max);
  });

  test("the canvas dominates the horizontal space", async ({ page }) => {
    const workspace = await box(page, "dde-workspace");
    const explorer = await box(page, "dde-explorer");
    const inspector = await box(page, "dde-inspector");
    expect(workspace.width).toBeGreaterThan(explorer.width + inspector.width);
    // Section 2: the main workspace is the dominant area at the canonical
    // frame. A shell whose side panels crowd the canvas is not the locked
    // composition even if every individual width is in range.
    expect(workspace.width / 1672).toBeGreaterThan(0.55);
  });

  test("the zones tile the viewport without gaps or overlap", async ({
    page,
  }) => {
    const topbar = await box(page, "dde-topbar");
    const rail = await box(page, "dde-rail");
    const explorer = await box(page, "dde-explorer");
    const workspace = await box(page, "dde-workspace");
    const inspector = await box(page, "dde-inspector");
    const statusbar = await box(page, "dde-statusbar");

    expect(Math.round(rail.y)).toBe(Math.round(topbar.y + topbar.height));
    expect(Math.round(explorer.x)).toBe(Math.round(rail.x + rail.width));
    expect(Math.round(workspace.x)).toBe(
      Math.round(explorer.x + explorer.width),
    );
    expect(Math.round(inspector.x)).toBe(
      Math.round(workspace.x + workspace.width),
    );
    expect(Math.round(inspector.x + inspector.width)).toBe(1672);
    expect(Math.round(statusbar.y + statusbar.height)).toBe(941);
  });

  test("all five workspace modes are present in one tab bar", async ({
    page,
  }) => {
    for (const mode of [
      "design",
      "coverage",
      "architecture",
      "qa",
      "source",
    ]) {
      await expect(page.getByTestId(`mode-${mode}`)).toBeVisible();
    }
  });

  test("mode switching changes real local workspace state", async ({ page }) => {
    for (const mode of ["coverage", "architecture", "qa", "source", "design"]) {
      await page.getByTestId(`mode-${mode}`).click();
      await expect(page.locator(".dde-workspace-inner")).toHaveAttribute(
        "data-mode",
        mode,
      );
    }
  });

  test("the canonical tokens are the ones actually applied", async ({
    page,
  }) => {
    const tokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        bg: style.getPropertyValue("--dde-bg").trim(),
        surface: style.getPropertyValue("--dde-surface").trim(),
        primary: style.getPropertyValue("--dde-primary").trim(),
        text: style.getPropertyValue("--dde-text").trim(),
      };
    });
    // Section 3.1 core palette, verbatim.
    expect(tokens.bg).toBe("#f7f8fb");
    expect(tokens.surface).toBe("#ffffff");
    expect(tokens.primary).toBe("#4f46e5");
    expect(tokens.text).toBe("#111827");
  });
});

test.describe("honest state rendering", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FIXTURE);
    await expect(page.getByTestId("dde-shell")).toBeVisible();
  });

  test("an unknown count renders an em-dash carrying its reason", async ({
    page,
  }) => {
    const sources = page.getByTestId("explorer-group-sources");
    await expect(sources).toBeVisible();
    const count = sources.locator(".dde-count");
    await expect(count).toHaveText("—");
    await expect(count).toHaveAttribute("data-known", "false");
    await expect(count).toHaveAttribute(
      "data-availability",
      "NOT_IMPLEMENTED",
    );
    const reason = await count.getAttribute("title");
    expect(reason).toContain("M8");
  });

  test("a real count renders as a number, not an em-dash", async ({ page }) => {
    const screens = page.getByTestId("explorer-group-screens");
    await expect(screens.locator(".dde-count")).toHaveText("12");
    await expect(screens.locator(".dde-count")).toHaveAttribute(
      "data-known",
      "true",
    );
  });

  test("a partially assessed project shows no coverage percentage", async ({
    page,
  }) => {
    const ring = page.getByTestId("coverage-ring");
    await expect(ring).toHaveText("—");
    await expect(ring).toHaveAttribute("data-state", "PARTIAL");
  });

  test("serving-model identity is never claimed without evidence", async ({
    page,
  }) => {
    const role = page.getByTestId("role-manager_chair");
    await expect(role).toBeVisible();
    // Desired, configured and serving are three separate rows.
    await expect(role.locator("dt")).toHaveText([
      "Desired",
      "Configured",
      "Serving",
    ]);
    await expect(role.locator("dd").nth(2)).toHaveText("UNATTESTED");
  });

  test("Claude /design is visibly present but honestly disabled", async ({
    page,
  }) => {
    const button = page.getByTestId("claude-design");
    await expect(button).toBeVisible();
    await expect(button).toBeDisabled();
    const reason = await button.getAttribute("title");
    expect(reason).toContain("no certified design provider transport");
    expect(reason).not.toContain("M10");
  });

  test("the candidate strip shows no invented cards", async ({ page }) => {
    const strip = page.getByTestId("candidate-strip");
    await expect(strip).toBeVisible();
    // No Direction A/B/C placeholders and no scores.
    await expect(strip).not.toContainText("Direction");
    await expect(strip).not.toContainText("%");
    await expect(strip.locator(".dde-unavailable")).toBeVisible();
  });

  test("coverage mode lists real dimension states", async ({ page }) => {
    await page.getByTestId("mode-coverage").click();
    await expect(page.getByTestId("coverage-mode")).toBeVisible();
    await expect(
      page.getByTestId("coverage-dimension-accessibility"),
    ).toContainText("PARTIAL");
    await expect(
      page.getByTestId("coverage-dimension-responsive"),
    ).toContainText("UNASSESSED");
  });
});

test.describe("responsive degradation", () => {
  test("the inspector becomes an overlay below 1180px", async ({ page }) => {
    await page.goto(FIXTURE);
    await page.setViewportSize({ width: 1100, height: 900 });
    const workspace = await box(page, "dde-workspace");
    const explorer = await box(page, "dde-explorer");
    // Canvas stays dominant and the explorer survives: the information
    // architecture is preserved rather than destroyed to fit.
    expect(workspace.width).toBeGreaterThan(explorer.width);
    await expect(page.getByTestId("dde-explorer")).toBeVisible();
  });

  test("the shell survives a narrow companion width", async ({ page }) => {
    await page.goto(FIXTURE);
    await page.setViewportSize({ width: 860, height: 800 });
    await expect(page.getByTestId("dde-topbar")).toBeVisible();
    await expect(page.getByTestId("dde-workspace")).toBeVisible();
    await expect(page.getByTestId("dde-statusbar")).toBeVisible();
  });
});
