# DDE-069 Packaged VS Code Host E2E

Date: 2026-09-08
State: packaged-host baseline **PROVEN**; project switching, read projections, Universal Chat, and the READY-candidate/preview/Inspector batch are row-specific **PROVEN**; unexercised actions remain evidence-gated.

## Scope

This proof closes the environment-level gap between the host-neutral React/browser tests and a real installed editor host. It does not mass-promote golden controls whose own commands/actions were not exercised in this run.

The harness `interfaces/dde-studio/e2e/runPackagedHostE2E.ts`:

- allocates isolated local Gateway/CDP ports dynamically;
- creates a throwaway PostgreSQL database and runs Alembic to current head;
- seeds two authorized projects/missions with PXG `screens/checkout` and `screens/alternate` through production services;
- starts the real FastAPI Gateway against that database and the DDE-local Redis;
- builds the production React UI and a real `dde-studio-0.1.0.vsix`;
- installs the VSIX into an isolated VS Code 1.95.3 profile through VS Code's own CLI;
- opens the real `DDE Code: Open Frontend Studio Workbench` command from VS Code's command palette;
- attaches Playwright over Chromium CDP to the actual VS Code workbench/webview; and
- requires the React project/screen selectors to resolve the first project, switch through the governed `frontend.project.switch` path to the second project/screen, and return to the original project/screen.

## Passing certification

Command:

```text
npm --prefix interfaces/dde-studio run test:host-e2e
```

The passing run emitted:

```text
PACKAGED_HOST_PALETTE_BEFORE ">"
PACKAGED_HOST_PALETTE_AFTER ">Open Frontend Studio Workbench"
PACKAGED_HOST_PALETTE_ROWS ["DDE Code: Open Frontend Studio Workbench","DDE Code: Set Frontend Studio Missionsimilar commands"]
PACKAGED_HOST_E2E_PASS {"host":"vscode","vscodeVersion":"1.95.3","projectId":"<throwaway-project>","missionId":"<throwaway-mission>","screenKey":"screens/checkout","switchedProjectId":"<throwaway-second-project>","switchedScreenKey":"screens/alternate","returnedProjectId":"<throwaway-project>","database":true,"migrations":"head"}
```

Process exit code: `0`.

The UUIDs are intentionally throwaway fixture identities. Success depends on exact agreement between those freshly persisted identities and the values rendered by the installed extension's production webview.

## Production defect discovered by the host gate

The first database-backed host run exposed a real schema drift: runtime Source Intelligence queried `frontend_templates.content_object_ref`, `content_object_backend` and `content_size_bytes`, while the authoritative `frontend_template.json` / regenerated Stage-1 SQL omitted those columns. Migration `0034` then returned early on fresh databases because its marker table already existed.

The repair is feature-preserving:

- `schemas/objects/frontend_template.json` now owns the three nullable object-storage fields;
- generated `FrontendTemplate` and Stage-1 SQL were regenerated from that schema;
- migration `0037_frontend_template_object_columns` idempotently repairs databases already at the affected schema; and
- the historical `0034` boundary remains authoritative, so `0037` downgrade is intentionally a no-op and `0034` downgrade removes the table at the correct boundary.

Migration proof completed on throwaway PostgreSQL databases:

- fresh `upgrade head` contains all four content columns (`content_hash` plus the three object-store columns);
- a simulated affected `0036` database is repaired by `0037`; and
- complete `head -> base -> head` remains green without `CASCADE`.

## Row-specific project-switch closure

The expanded host run found a second production-only defect: the host deep-camelizes Gateway acceptances, so the returned `payload.mission_id` becomes `payload.missionId`. React was still reading `mission_id`; the Gateway accepted the switch but the UI discarded the returned mission identity. React now reads the canonical host-side `missionId`, and the host-neutral fixture uses the same camelized contract.

The installed-VSIX run now proves original project/screen -> governed `frontend.project.switch` -> second project/mission + `screens/alternate` -> governed switch back -> original project + `screens/checkout`. This closes the packaged WIRED/E2E/visual obligation for `TB-02`.

## Row-specific read-projection closure — 2026-09-08

The installed-VSIX harness now also asserts authoritative data for eight controls without adding mock-only state:

- `EX-02` project heading/menu: project slug/ID and PXG revision come through the production context/explorer projection;
- `EX-03` Explorer search: the real packaged webview filters the projected tree;
- `EX-04` Screens group/count: the freshly persisted one-screen PXG renders a count of `1`;
- `EX-16`..`EX-19`: Style/Section/Component/Behaviour lock rows render the real `LockService.inventory()` zero counts on the fresh database; and
- `ST-06`: installed package version `0.1.0` and real PXG revision `r1` render together in the production status bar.

The passing marker includes `verifiedControls=["EX-02","EX-03","EX-04","EX-16","EX-17","EX-18","EX-19","ST-06"]`. Their WIRED and E2E layers are therefore VERIFIED. The derived ledger is now **20 VERIFIED / 70 BOUND / 9 TYPED_UNAVAILABLE / 0 UNBOUND**.

## Universal DDE Chat packaged closure — 2026-09-08

The installed VSIX now proves `CH-01`, `CH-03` and `CH-04` through a provider-independent deterministic read query. The real webview exposes the composer, projects `checkout` + `Desktop 1440` into context/settings, opens a durable conversation, persists `frontend.chat.set_context`, executes `frontend.chat.send` with `how much coverage do we have?`, and renders `COVERAGE_QUERY` plus the honest fresh-project answer `Coverage UNASSESSED: percentage unavailable`. No external model/runtime participates in this proof.

The pass marker now includes `CH-01`, `CH-03`, `CH-04`. Their remaining E2E layers are VERIFIED; the derived ledger is **23 VERIFIED / 67 BOUND / 9 TYPED_UNAVAILABLE / 0 UNBOUND**.

## READY candidate, code-backed preview and Inspector packaged closure — 2026-09-08

The packaged fixture now creates an isolated workspace through `WorkspaceService`, writes a project-local prototype into that DDE-owned worktree, creates `Packaged Direction A` through `CandidateService`, and advances only through the legal lifecycle to `READY`. The PXG screen/hero carry real source refs and canonical layout tokens. No candidate row, preview document, lock, score, or Inspector descriptor is injected directly into the browser.

The installed VSIX run now proves, against fresh PostgreSQL at migration head:

- the real candidate card is `READY`, has `0 changes`, and honestly projects `UNSCORED` with no fabricated score dimensions;
- the candidate thumbnail moves from `NOT_RENDERED` to a real rendered preview document;
- candidate preview start crosses the production Gateway and reaches browser-attested `LIVE`;
- stable `screens/checkout#hero` PXG identity reaches React selection and the real Inspector descriptor;
- breadcrumb, selected-node header, source mapping, Layout token values, Source/code, project-native provenance, and the honest `Not evaluated` accessibility state render from production reads;
- Style and Section locks are created through real Gateway commands, appear as effective selection chips, and drive `Current (Locked)`;
- the Responsive `390` action creates a replacement code-backed preview session and that new session re-attests `LIVE`; and
- project switching still succeeds after the candidate/preview/lock activity.

Two production-only defects were found and repaired by this deeper host proof. First, VS Code webview CSP is inherited by `srcdoc`; with a nonce-bearing parent policy, CSP3 ignores `unsafe-inline`, so DDE's generated preview runtime did not execute and the persisted preview remained `LOADING`. The webview now exposes its per-instance nonce only to the trusted DDE React shell, which stamps that nonce only onto the generated `dde-preview-runtime` script. Target-application inline scripts remain blocked. Second, the preview ready signal is now a session/content-hash handshake (`host_ping` -> `ready`) rather than relying on a one-shot DOM-ready race.

The headless VS Code CDP target does not route Playwright's physical click into this doubly nested `srcdoc` on this host. The harness detects that limitation and dispatches the same production `click` event only when the physical event did not enter the child. Host-neutral Playwright independently proves physical click delivery; the installed-VSIX leg proves the generated runtime -> `postMessage` -> React selection/Inspector path. This limitation is recorded rather than hidden.

Fixture teardown is independently idempotent: the outer harness invokes `fixture_server.py --cleanup-only` while the scratch database is live, and cleanup now fails if the candidate workspace directory remains. Passing runs emit `PACKAGED_HOST_FIXTURE_CLEANUP <workspace-id>`. This avoids relying on Uvicorn SIGTERM unwinding.

The row-specific packaged-host proof closes: `CT-01`, `CV-01`, `CV-02`, `CV-04`, `CV-06`, `CV-07`, `CA-01`, `CA-02`, `CA-03`, `CA-04`, `CA-05`, `CA-06`, `IN-01`, `IN-06`, `IN-07`, `IN-13`, `IN-15`, `IN-16`, and `ST-01`. Together with the previously verified rows, the derived ledger becomes **42 VERIFIED / 48 BOUND / 9 TYPED_UNAVAILABLE / 0 UNBOUND**.

`CA-07` is deliberately not promoted: its contract is `frontend.design.try_live` from a persisted DesignArtifact into an isolated candidate workspace, while this batch starts preview for an already persisted candidate. Inspector write rows such as `IN-02`, `IN-03`, `IN-08`, `IN-09`, `IN-10`, and `IN-11` also remain BOUND until the installed host performs their exact governed mutations.

## Non-overclaim boundary

This baseline proves installed VSIX -> VS Code -> React webview -> real Gateway -> PostgreSQL. Project switching, deterministic Chat, preview attestation, lock creation, responsive preview, candidate/read projections and the reviewed Inspector surfaces now have row-specific production evidence. It does **not** mass-verify unexercised commands such as `frontend.design.try_live`, candidate comparison/promotion, Inspector property writes, comments, resize, preview scenarios, or assist-policy mutations; those rows remain BOUND until their exact action and resulting durable state are exercised in the packaged host.
