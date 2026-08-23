# Gap-closure record — infrastructure gaps verified and closed (2026-08)

**Status:** work record, not an EDR. No Project Truth rows were created or
modified. Where a gap touches chartered blueprint scope, the owning mission
or EDR is named below; this file only records what was verified, what was
closed in-repo, and what remains open with its owner.

This document exists so the main DDE setup agent (and any future mission
chain) sees, in one place, which infrastructure gaps were independently
audited, which were closed by whom, and which remain deliberately open —
so nothing is re-implemented twice or silently dropped.

## 1. Audit result: what the main setup agent had already closed

The independent audit confirmed the main agent closed several reported gaps
before this pass; these are **not** re-done here:

| Gap | Evidence it was already closed |
|---|---|
| Real worker adapter | `adapters/cursor/adapter.py`, `adapters/claude/adapter.py` (fail-closed T2 policy shells), `engine/workers/scripted_adapter.py` (real T1 adapter, lease-enforced) |
| Certification runner | `engine/workers/smoke.py` `run_smoke()` — all 12 Chapter 8.5 fixtures enforced |
| EDR lifecycle tracking | `engine/truth/service.py` `propose_edr`/`accept_edr`/`update_edr_status` + idempotent `scripts/accept_owner_edrs.py` |

## 2. Gaps still open before this pass, now CLOSED in this pass

### 2.1 Repo hygiene (`bin/`, `obj/`, `node_modules/`)
`.gitignore` had no .NET build-artifact or node_modules patterns while
`packaging/windows/DdeSetupWizard/bin/**` held hundreds of DLLs as untracked.
Added `[Bb]in/`, `[Oo]bj/`, `publish/`, `node_modules/`, `*.vsix`.

### 2.2 Windows dev loop: `just test-unit` + Windows CI job
- `justfile`: new `test-unit` recipe running `pytest tests/unit -m "not integration"`,
  plus a `set windows-shell` line so every single-invocation recipe runs on
  Windows hosts that have no `sh`.
- `pyproject.toml`: registered the `integration` marker.
- `tests/unit/conftest.py`: auto-marks any test whose module is `*_postgres.py`,
  imports `tests.support.db`, or imports `redis` — so the pure suite stays
  accurate without per-file decorators and picks up new service-backed suites
  automatically.
- `.github/workflows/ci.yml`: new `windows` job (lint, typecheck,
  `just test-unit`). The ubuntu `ci` job remains authoritative for
  services/migrations/integration.

Verified locally on Windows: `179 passed, 239 deselected` in ~21s with no
PostgreSQL/Redis running.

### 2.3 CLI `--json`
All four subcommands (`mission create|status|trace`, `task list`) now accept
`--json` and emit machine-readable JSON built from the same structures the
text renderer consumes (contracts via `model_dump(mode="json")`; view
dataclasses via a shared recursive serializer). Default text output, exit
codes and error mapping are unchanged. `mission trace --json` prints before
the completeness check so callers can parse a trace and still observe
`MISSION_TRACE_INCOMPLETE`'s exit code.

New pure unit tests: `tests/unit/test_cli_json.py`. The existing
subprocess-based postgres suites continue to prove end-to-end behaviour.

This unblocks the dde-studio CLI-JSON bridge seam (planning doc §3.1a).

### 2.4 dde-studio live Gateway client
New `shared/gatewayClient.ts`: typed client over the **real, existing**
Gateway `/v1` surface only — session open/resume/close, command acceptance
(202), `GET /missions/{id}`, `GET /mission-control/{id}` — mirroring the
generated contracts and mapping errors onto the Chapter 15.5 error family.
No endpoint shapes are invented client-side.

New `shared/studioGateway.ts`: session lifecycle service used by
`extension.ts` (opens a `/v1` session when `dde.studio.principalId` is
configured; degrades to explicit `disabled`/`unreachable` states otherwise;
heals expired sessions).

New settings: `dde.studio.principalId`, `dde.studio.cliPath`.
`src/connection/cliTransport.ts` replaced the throwing stub with a real
`ProcessCliJsonTransport` that spawns `dde … --json` and parses stdout
(fail-loud on missing Core install). Fleet-room LIST views intentionally
remain empty — no list endpoint exists yet (DDE-027); honesty tests still
enforce no fabricated rows.

## 3. Gaps verified still open — NOT closed here, owners named

These require either Project Truth decisions or chartered missions; per
AGENTS.md they are recorded, not improvised:

1. **Cost telemetry hole (EDR-0005, open).** `WorkerRun.usage_record_id`
   still references a `UsageRecord` concept with no producing writer; every
   persisted outcome row discloses the gap via `disclosed_gaps`
   (`engine/telemetry/model.py`). Owner: a chartered mission implementing
   Chapter 6.5 actual-cost capture behind the broker (needs a real T2 run
   path first). Do not fabricate costs to close it.
2. **Live hosted-model worker execution.** Cursor/Claude adapters are
   deliberate fail-closed shells pending brokered credentials (Chapter 14.3).
   This is disclosed scope, not debt: closing it requires the credential
   broker mission, then certification of the live adapters.
3. **Gateway list endpoints (DDE-027, S3+).** `/v1` has reads by id and
   command acceptance but no mission/run/event listing. dde-studio fleet
   views stay empty until this lands. Owner: DDE-027's charter.
4. **`contradiction_rate` promotion gate (EDR-0003, partial).** Chapter 5.6
   conflict detection now exists (`engine/context/conflict.py`) and partially
   unblocks gate 3, but replay-through-eval wiring is explicitly deferred;
   see `docs/planning/mission-numbering-note.md` for the full interaction.
5. **Semantic retriever default gating (EDR-0002)** and remaining accepted
   EDR constraints — unchanged by this pass.

## 4. Integration guarantees (why nothing breaks)

- CLI changes are additive: new flag, default behaviour byte-identical,
  dispatch table untouched; existing tests pass unmodified.
- Routing/governance code from the earlier adoption pass is untouched.
- Studio changes are additive modules plus one new import and one guarded
  read block in `extension.ts`; all 44 existing client tests pass, including
  the honesty assertions that forbid fabricated data.
- The auto-marking conftest only *deselects* tests that provably need live
  services; pure tests can never be accidentally skipped.
- CI keeps the ubuntu job as authoritative; Windows is additive coverage.

## 5. Closed in this pass — frontend/UX design-gate infrastructure (2026-08-22)

Appended after the v1.1 frontend/UX playbook was operationalized. Only items
with landed commit evidence are recorded here; in-flight work (EDR-0008
implementation of Playwright/axe visual gates) is **not** listed below — it
is admitted but not landed, and will be recorded when its missions land.

### 5.1 Design gates wired into CI (`5f31142`)
- Token SSOT pipeline landed first (`58015fb`): `schemas/design/tokens.json`
  pins every leaf; codegen emits typed `tokens.ts` + CSS root; the generated
  artifact is covered by the existing generated-drift gate.
- Static design lints DD201–DD206 (`d03d415`) run as their own justfile
  recipe and CI step in committed baseline mode (shrink-only budget; legacy
  off-scale values frozen in a committed baseline rather than waived).
- dde-studio client tests became PR-blocking in `.github/workflows/
  dde-studio.yml`, closing the R5 hole where the workflow stopped at
  typecheck.
- Owner: none — wired at its production enforcement point; regressions fail
  the same PR that introduces them.

### 5.2 Prototype-manifest sweep pre-oracle (`b5a0ebb`, contract via `29cc55a`)
- `engine/verification/prototypes.py` validates a workspace's
  `prototypes/flows.json` structurally (version, flow ids, entry points,
  every transition target and declared screen exists on disk) before oracle
  evaluation; violations demote a clean PASS to PARTIAL with
  `VERIFICATION_FAILURE` classification on the existing recovery rows.
- Manifest shape is contracted by `schemas/design/prototype_flow.schema.json`
  under the normal SSOT/drift discipline.
- Byte-stable `index.html` regeneration remains deferred until a gallery
  generator ships (currently a review-skill concern); disclosed above in the
  playbook's §5.3 table.

### 5.3 Live Prototype Gallery (`a80f5a6`)
- `interfaces/dde-studio/src/webviews/previewGalleryProvider.ts`: sandboxed
  srcdoc previews over the workspace `prototypes/` directory, flows table,
  file-watch streaming for mid-mission viewing, reduced-motion toggle.
- The Preview module moved from stub to exists-with-honest-liveToday; the
  honesty tests still forbid fabricated gallery rows.

