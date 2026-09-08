# DDE-069 Packaged VS Code Host E2E

Date: 2026-09-08
State: packaged-host baseline **PROVEN**; `TB-02` project switching and the first eight-row packaged read-projection batch are row-specific **PROVEN**; other actions remain evidence-gated.

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

## Non-overclaim boundary

This baseline proves installed VSIX -> VS Code -> React webview -> real Gateway -> PostgreSQL, and `TB-02` now has its own action/state proof. It does **not** by itself verify other row-specific commands such as Try Live, lock create/release, chat send, promotion or preview attestation. Those controls remain BOUND until the same packaged-host path exercises their own action and resulting durable state.
