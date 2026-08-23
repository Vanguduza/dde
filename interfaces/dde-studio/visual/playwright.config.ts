/**
 * Playwright project for the DDE-Studio visual gate (EDR-0008).
 *
 * The webServer step first compiles the studio (tsc) and emits
 * fixtures/.screens.txt + .animated.txt, then starts visual/server.cjs,
 * which serves every fixture screen through the production
 * wrapScreenSrcdoc CSP wrapper.
 */
import { defineConfig, devices } from "@playwright/test";
import { execSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

// Playwright loads this config as CommonJS (the studio package has no
// "type": "module"), so import.meta is unavailable here.
declare const __dirname: string;

const here = __dirname;
const studioRoot = path.resolve(here, "..");
const outDir = path.join(studioRoot, "out", "shared", "ui", "previewGallery.js");

/** Compile shared TS (same tsc invocation npm run check uses) once. */
function ensureCompiled(): void {
  if (!existsSync(outDir)) {
    execSync("npx tsc -p ./", { cwd: studioRoot, stdio: "inherit" });
  }
}

/**
 * Snapshot the fixture screen list so specs need no directory walking;
 * mark screens containing @keyframes as reduced-motion subjects.
 */
function writeScreenManifest(): void {
  const fixturesRoot = path.join(here, "fixtures");
  const screens: string[] = [];
  const animated: string[] = [];
  const walk = (dir: string): void => {
    if (!existsSync(dir)) {
      return;
    }
    for (const name of readdirSync(dir)) {
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) {
        walk(full);
      } else if (/\.html$/i.test(name)) {
        const relPath = path
          .relative(fixturesRoot, full)
          .split(path.sep)
          .join("/");
        screens.push(relPath);
        if (/@keyframes/i.test(readFileSync(full, "utf8"))) {
          animated.push(relPath);
        }
      }
    }
  };
  walk(fixturesRoot);
  screens.sort();
  writeFileSync(
    path.join(fixturesRoot, ".screens.txt"),
    `${screens.join("\n")}\n`,
  );
  writeFileSync(
    path.join(fixturesRoot, ".animated.txt"),
    `${animated.join("\n")}\n`,
  );
}

ensureCompiled();
writeScreenManifest();

export default defineConfig({
  testDir: here,
  outputDir: path.join(here, ".test-results"),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}{ext}",
  use: {
    baseURL: `http://127.0.0.1:${process.env.VISUAL_PORT ?? 4173}`,
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: "node server.cjs",
    cwd: here,
    url: `http://127.0.0.1:${process.env.VISUAL_PORT ?? 4173}/index.json`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: {
      VISUAL_PORT: String(process.env.VISUAL_PORT ?? 4173),
    },
  },
});
