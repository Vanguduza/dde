# DDE-069 — dependency admission for the host-neutral workbench

AGENTS.md requires a stated licence, maintenance signal and reason the
standard library is insufficient for every new dependency. This records
that for the four packages DDE-069 M3 introduces into
`interfaces/dde-studio/ui`.

The DDE shell's own styling stays hand-authored CSS over DDE tokens
(`FRONTEND_STUDIO_REV3.md` §2.4). No CSS framework, component kit or
state-management library is admitted: the golden shell is a specific
locked design, and a kit would fight it.

## Runtime

| Package | Version | Licence | Maintenance signal | Why the stdlib is insufficient |
|---|---|---|---|---|
| `react` | 19.2.8 | MIT | Meta-maintained; weekly releases; the framework the Rev 3 target decomposition names explicitly (§5.1) | The workbench is a stateful, deeply nested, incrementally updating application. FS-GAP-001 records that the DDE-067 string-template renderer already could not sustain its state and panel complexity. Hand-rolled DOM diffing would be a worse React. |
| `react-dom` | 19.2.8 | MIT | Released in lockstep with `react` | The DOM renderer for the above. Not separable. |

Bundle cost, measured on the committed build: **207 KB raw / 65 KB
gzipped** for the whole workbench including application code. This is a
desktop developer tool loaded once per session inside VS Code or Electron,
not a landing page.

## Build and test only

| Package | Version | Licence | Maintenance signal | Why |
|---|---|---|---|---|
| `vite` + `@vitejs/plugin-react` | 7.x / 5.x | MIT | Vite is the reference React build tool; the Rev 3 target names it | TypeScript + JSX must be compiled and bundled for a webview. `tsc` alone emits no bundle, and the repo has no other bundler. |
| `@types/react`, `@types/react-dom`, `@types/node` | — | MIT | DefinitelyTyped | Type definitions only; no runtime code. |
| `@playwright/test` | ^1.62.1 | Apache-2.0 | Already admitted and in use at `interfaces/dde-studio/visual` and behind `capability.browser` | Structural conformance of the golden shell must be measured in a real browser at 1672x941. Reuses the existing admission rather than adding a second browser driver. |

## Not admitted, deliberately

- **Tailwind / shadcn** — barred for DDE's own chrome by the global plan and
  by `FRONTEND_STUDIO_REV3.md` §2.4. A *target project* DDE is designing
  may use them; they enter through the Design System Compiler, never into
  the DDE shell.
- **A component kit (MUI, Radix, Chakra)** — the golden shell is a locked
  design with specific measurements. A kit would have to be fought at every
  panel, and "generic kit appearance" is explicitly forbidden (§2.3).
- **A state library (Redux, Zustand, TanStack Query)** — the workbench's
  state is projections from the bridge plus local view state. React's own
  hooks cover it. Revisit only if a real caching or invalidation problem
  appears, not pre-emptively.
- **An icon package** — the rail uses text glyphs today. Icons are a visual
  fidelity item for the golden-shell pass, and inline SVG in the repo
  avoids a dependency for what is ultimately a handful of paths.

## Supply-chain note

All six packages are top-level, pinned or caret-pinned in
`interfaces/dde-studio/ui/package.json`, and `package-lock.json` is
committed. `just studio-check` runs `npm ci` against that lockfile, so a
transitive change cannot land silently.
