# Visual gate (EDR-0008)

Playwright + axe-core over the Prototype Gallery rendering path.

Every fixture screen under `fixtures/screens/` is served through the same
`wrapScreenSrcdoc` CSP wrapper the webview applies inside its sandboxed
iframe (`shared/ui/previewGallery.ts`), so goldens capture what production
renders — not a parallel path. `server.cjs` (Node stdlib http only) serves:

- `/` — gallery chrome rendered via `previewGalleryPage()`
- `/screen/screens/<name>.html` — screen wrapped via `wrapScreenSrcdoc()`
- `/index.json` — screen + animated-screen manifest

Fixture screens use only token variables copied from `tokenCssRoot()`
(`--bg`, `--surface-card`, `--border-default`, `--space-*`, `--type-*`,
`--status-ok`, ...). Sample data is marked `data-sample="demo"` and lives
here only; production honesty law is unchanged.

## What runs

Per screen × {light, dark} × width {320, 900, 1280}: `toHaveScreenshot()`
golden. Per screen × scheme: axe scan with tags `wcag2a,wcag2aa,wcag22aa`;
critical or serious violations fail the run. Screens whose CSS declares
`@keyframes` also get a `prefers-reduced-motion: reduce` pass at 900px dark.

## Commands

```bash
npm run test:visual                              # compile + fingerprints + Playwright gate
npx playwright install chromium                  # one-time browser download
npm run test:visual -- --update-snapshots        # regenerate baselines (see below)
```

Note: because the studio `test:visual` script already chains tsc + the DOM
fingerprint test before Playwright, extra CLI args must be passed after `--`.

## Baselines

Goldens live in `__screenshots__/`. They were generated **locally on Windows**
(chromium 151.0.7922.34 headless shell) and are committed. Regenerate them
only in the PR that intentionally changes visuals:

1. `npx playwright install chromium`
2. `npm run test:visual -- --update-snapshots`
3. Review diffs; commit only intended changes.

CI never updates baselines. `.github/workflows/dde-studio.yml` has a step
named "Generate baselines on first run" that runs with `--update-snapshots`
only on a cache miss, so a missing baseline degrades to generate-on-first-run
instead of failing CI; committed baselines make it a no-op. The Playwright
browser cache key hashes `package-lock.json`, so it rotates with the
`@playwright/test` version (EDR-0008 consequence note).

## Layout

- `playwright.config.ts` — compiles shared TS if needed, writes the fixture
  manifest, starts `server.cjs` as webServer.
- `screens.spec.ts` — golden + axe + reduced-motion specs.
- `server.cjs` — static preview server over compiled `out/shared` modules.
- `fixtures/` — screens + `flows.json`; `.screens.txt` / `.animated.txt` are
  generated manifests (do not hand-edit).
- `__screenshots__/` — committed baselines.
