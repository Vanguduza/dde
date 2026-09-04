import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

/**
 * This sandbox ships a Chromium build older than the pinned Playwright
 * package expects, so the launcher is pointed at the installed binary
 * directly rather than at the version-stamped directory it would derive.
 * Environment-only: no production code accommodates it, and CI (which
 * installs a matching browser) leaves DDE_CHROMIUM unset and uses the
 * default resolution.
 */
const executablePath = process.env.DDE_CHROMIUM;
const uiRoot = fileURLToPath(new URL("..", import.meta.url));

/**
 * The canonical viewport is 1672x941 (FRONTEND_STUDIO_REV3 Part I section
 * 2). Structural conformance is asserted at exactly that size, because the
 * locked measurements are stated for that frame.
 */
export default defineConfig({
  testDir: ".",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false,
  reporter: process.env.CI ? "line" : "list",
  use: {
    viewport: { width: 1672, height: 941 },
    baseURL: "http://127.0.0.1:4319",
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  webServer: {
    command: "npx vite --port 4319 --strictPort",
    cwd: uiRoot,
    url: "http://127.0.0.1:4319/visual/fixture.html",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
