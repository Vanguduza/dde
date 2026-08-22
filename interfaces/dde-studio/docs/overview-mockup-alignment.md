# Mission Overview — mockup alignment

Source of visual truth: [`dde-mission-overview-mockup.png`](./dde-mission-overview-mockup.png)

Live UI: `shared/ui/overview.ts` (consumed by the VS Code webview and Electron desktop shell).

Visual regression: `npm run test:visual` (DOM/class fingerprint in `shared/overviewVisual.test.ts`; also runs under `npm test`).

## Matched intentionally

- Header title **DDE Code — Mission Overview**, `main dashboard` + `Gateway pending` pills, Settings + Docs + menu chrome
- Slim Core status strip (ready/local/URL) above operator actions
- Operator action bar with outlined Start / Pause / Resume / Cancel / Refresh
- Horizontal manufacturing spine (Truth → Evidence) with dashed step boxes
- Three-column body: Missions + Work in flight | Fleet + Approvals/Verification/Integration + Attention | Unified activity
- Fleet cards (Hermes / Claude Code / DeepSeek) with idle/pending and Open fleet room
- Empty markers only (no fabricated missions, runs, or events; no instructional essays)

## Remaining intentional diffs (not pixel-perfect)

- Docs / overflow menu stay disabled (no docs surface / overflow actions yet)
- Inline SVG icons instead of the mockup’s exact icon set / brand marks
- System strip expands warn/err tones when Core is not ready (mockup shows the happy path)
- Approve / Reject remain present but compact; mockup emphasizes empty copy only
- Responsive single-column collapse below ~960px (mockup is desktop-width)
