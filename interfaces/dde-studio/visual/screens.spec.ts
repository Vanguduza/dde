/**
 * Visual gate (EDR-0008): Playwright + axe-core over the Prototype Gallery
 * rendering path.
 *
 * Every fixture screen is served through the same wrapScreenSrcdoc CSP
 * wrapper the webview uses (visual/server.cjs), then captured at
 * {light, dark} × {320, 900, 1280}. axe scans tags wcag2a, wcag2aa,
 * wcag22aa; critical/serious violations fail the run. Screens with CSS
 * animations also get a prefers-reduced-motion pass. Baselines live under
 * visual/__screenshots__/ (see README.md).
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import path from "node:path";

// Playwright loads this spec as CommonJS (the studio package has no
// "type": "module"), so import.meta is unavailable here.
declare const __dirname: string;

const here = __dirname;
const fixturesRoot = path.join(here, "fixtures");

function listScreens(): string[] {
  return readFileSync(path.join(fixturesRoot, ".screens.txt"), "utf8")
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function animatedScreens(): Set<string> {
  try {
    return new Set(
      readFileSync(path.join(fixturesRoot, ".animated.txt"), "utf8")
        .split(/\r?\n/)
        .map((s) => s.trim())
        .filter(Boolean),
    );
  } catch {
    return new Set();
  }
}

const SCREENS = listScreens();
const ANIMATED = animatedScreens();

const WIDTHS = [320, 900, 1280] as const;

test.describe.configure({ mode: "parallel" });

for (const relPath of SCREENS) {
  const slug = relPath.replace(/\.html$/i, "").replace(/[^a-z0-9]+/gi, "-");

  if (ANIMATED.has(relPath)) {
    test(`reduced motion ${relPath}`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.emulateMedia({ colorScheme: "dark" });
      await page.setViewportSize({ width: 900, height: 720 });
      await page.goto(`/screen/${encodeURI(relPath)}`);
      await expect(
        page,
      ).toHaveScreenshot(`${slug}-900-dark-reduced-motion.png`, {
        fullPage: true,
        animations: "disabled",
        maxDiffPixelRatio: 0.02,
      });
    });

    // DDE-068 residual (gap-closure-record.md §6.5): "reduced-motion
    // blocking assertions" -- the screenshot test above only proves a
    // pixel golden is stable; Playwright's own `animations: "disabled"`
    // screenshot option force-freezes every golden regardless of
    // prefers-reduced-motion, so it cannot tell a real fix from no fix at
    // all. This test instead reads the browser's actually-computed
    // animation-duration on every animated element, with the emulated
    // media feature as the only variable, so it fails if the product's
    // CSS ever stops truly degrading motion.
    test(`reduced motion semantics ${relPath}`, async ({ page }) => {
      await page.setViewportSize({ width: 900, height: 720 });

      const animationDurations = async (): Promise<string[]> =>
        page.evaluate(() => {
          const durations: string[] = [];
          for (const el of Array.from(document.querySelectorAll("*"))) {
            const style = getComputedStyle(el);
            if (style.animationName !== "none") {
              durations.push(style.animationDuration);
            }
          }
          return durations;
        });

      await page.goto(`/screen/${encodeURI(relPath)}`);
      const normal = await animationDurations();
      expect(
        normal.length,
        `${relPath} is on the animated-screens manifest but no element ` +
          `has a computed animation-name`,
      ).toBeGreaterThan(0);
      expect(
        normal.some((duration) => duration !== "0s"),
        `${relPath}: expected a nonzero animation-duration without ` +
          `reduced motion (got ${JSON.stringify(normal)}) -- otherwise ` +
          `this screen has nothing for reduced motion to degrade`,
      ).toBe(true);

      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.reload();
      const reduced = await animationDurations();
      expect(
        reduced.length,
        `${relPath}: animated elements disappeared under reduced motion`,
      ).toBe(normal.length);
      for (const duration of reduced) {
        expect(
          duration,
          `${relPath}: animation-duration did not degrade to 0s under ` +
            `prefers-reduced-motion: reduce (got ${duration})`,
        ).toBe("0s");
      }
    });
  }

  for (const scheme of ["light", "dark"] as const) {
    test.describe(`${relPath} · ${scheme}`, () => {
      test.use({ colorScheme: scheme });

      for (const width of WIDTHS) {
        test(`golden ${width}px`, async ({ page }) => {
          await page.goto(`/screen/${encodeURI(relPath)}`);
          await expect(page).toHaveScreenshot(`${slug}-${width}-${scheme}.png`, {
            fullPage: true,
            animations: "disabled",
            maxDiffPixelRatio: 0.02,
          });
        });
      }

      test(`axe scan`, async ({ page }) => {
        await page.goto(`/screen/${encodeURI(relPath)}`);
        const results = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
          .analyze();
        const blocking = results.violations.filter((v) =>
          ["critical", "serious"].includes(v.impact ?? ""),
        );
        test.info().annotations.push({
          type: "axe",
          description:
            `${relPath}: ${blocking.length} blocking violation(s), ` +
            `${results.violations.length} total`,
        });
        expect(blocking).toEqual([]);
      });
    });
  }
}
