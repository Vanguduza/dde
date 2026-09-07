# DDE-069 CA-07 — DesignArtifact Try Live Evidence

Date: 2026-09-07
State: UI/VISUAL verified; WIRED/E2E bound pending packaged production browser E2E.

## Scope

CA-07 is the golden Candidate/Directions control that turns exactly one persisted DesignArtifact direction into an isolated code-backed candidate. It must not edit accepted PXG directly, silently select another direction, or treat a generated artboard as LIVE.

## Production implementation evidence

- `DdeStudioApp.tsx` reads persisted artifacts from `frontend.design.artifacts`, sends `frontend.design.try_live` for the selected artifact, selects the returned candidate, starts its code-backed preview, and loads the returned PreviewDocument.
- `FrontendStudioWorkspace.tsx` renders neutral Direction A/B/C cards from those persisted reads, exposes one Try Live action per eligible artifact, and blocks quarantined/discarded/already-tried artifacts.
- `FrontendStudioWorkbenchPanel.ts` routes the design-artifact read through the configured mission and routes the command through the normal `StudioGatewayService` command path.
- `GatewayApiClient.readFrontendDesignArtifacts` calls the mission-scoped Core endpoint; the API validates session/mission/design-session ownership before reading artifacts.
- `DesignGateway.try_live` checks artifact/session/design-system/PXG freshness, creates an isolated `DESIGN_ARTIFACT` candidate, applies the selected proposal through the sole governed mutation path with `all_or_nothing=True`, records artifact/candidate provenance, and never writes accepted PXG.
## Verification

- `visual/claude-design.spec.ts`: 6/6 pass. The strengthened Try Live case proves Direction A remains the only tried artifact, its deterministic `space6` proposal is present in the browser-backed LIVE iframe, the exact preview reaches LIVE, and the automatic fresh verification request reaches `VERIFY PASSED` through `frontend.verification.run`.
- `frontendWorkbenchTransport.test.ts`: extension transport passes with the exact mission-scoped persisted-artifact URL pinned alongside the existing preview/inspector reads and command idempotency guarantees.
- `tests/unit/test_design_gateway_postgres.py`: real PostgreSQL covers persisted neutral directions, quarantine/refusal, atomic selected-artifact materialization, accepted-PXG isolation, provenance and stale-revision refusal.
- `tests/unit/test_frontend_studio_e2e_postgres.py`: real Gateway `/v1/commands` + PostgreSQL covers the same governed candidate/mutation/promotion boundaries used by Try Live.

## Evidence-layer disposition

- **UI: VERIFIED.** The named card action exists as functional React UI backed by persisted DesignArtifacts.
- **VISUAL: VERIFIED (structural).** Playwright renders and operates the control at the canonical workbench surface. AD-039 still blocks exact pixel-reference comparison and is not implied by this status.
- **WIRED: BOUND.** React, VS Code host bridge, shared Gateway client, Core API and backend command/service paths are implemented and independently tested. A packaged VS Code-host run against the real Gateway/PostgreSQL stack is not yet recorded.
- **E2E: BOUND.** Browser Try Live and real PostgreSQL/Gateway legs are both proven, but not yet as one packaged production-host execution.

CA-07 therefore advances from `UNBOUND` to `BOUND`; it is not declared fully VERIFIED until the missing combined production-host E2E is captured.