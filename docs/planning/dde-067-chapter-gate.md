# DDE-067 chapter gate -- Frontend Studio surface & consumption wiring
# ⟨product-studio-charter.md; frontend-studio-gui-spec.md; Ch.13.8; Ch.15⟩

**Mission:** appended Frontend Studio track / `DDE-067`. **Not** the
DDE-068 visual-verification executors or a direct Project Truth writer.

**Status:** CLOSED on `dde-067-frontend-studio-surface`.

**CI / local proofs (2026-08-27):** lint and format clean; mypy **395
source files**; full unit/contract/recovery collection **1,224 tests**
(**1,221 passed, 3 skipped**); repeated contract suite **213 passed**;
focused DDE-067 backend/contract suite **9 passed**; dde-studio client suite
**69 passed**; design lint ratchet green at **70** legacy DD206 findings.
The first full run found one Truth-boundary source-literal contaminant; its
assertion was not weakened.

## What this mission wires

- Six contributed Frontend Studio views under `interfaces/dde-studio/**`:
  Home, Intake, Donors, Canvas, Verify, and Approvals.
- `StudioGatewayService.sendFrontendCommand` → `POST /v1/commands` with a
  command UUID and idempotency key. Acceptance is displayed as asynchronous,
  never completion.
- `GatewayCommandService._execute_frontend` → `FrontendStudioService`: the
  production mutation path for compile, discovery, donor intake/adoption,
  canvas insert/move/update/remove, motion, and flow-step commands.
- `FrontendStudioService._require_donor_reuse`: approved donor-derived
  content cannot enter a screen until `ApprovalService.require_approved`
  finds the exact mission/donor scope hash.
- Token-constrained Canvas controls generated from `tokens.ts`; button-add
  and drag/drop issue the same `frontend.canvas.insert_component` command.
  Style controls are selects, not free-form inputs. Server-side
  `assert_token_value` remains the fail-closed backstop.

## Charter MUST/shall at production call sites

| Rule | Production call site |
|---|---|
| Recorded `donor_reuse` before donor implementation enters a task | `FrontendStudioService.insert_component` → `_require_donor_reuse` → `ApprovalService.require_approved`; blocked/approved Postgres contract proof in `test_canvas_insert_token_refusal_and_donor_reuse`. |
| Every command uses Gateway + idempotency key | `StudioGatewayService.sendFrontendCommand` mints command/key; `GatewayCommandService.accept` uses the existing CommandLedger before `_execute_frontend`. |
| No fabricated donors/verdicts | `frontendStudioHtml` renders factual empty states; client honesty tests reject sample donor rows and synthetic quality scores. |
| Add button and drag/drop share one structured path | `frontendStudioHtml` `sendInsert` emits `frontend.canvas.insert_component` for both events; no preview DOM mutation path exists. |
| Live edits are structured manifest/artifact mutations | `FrontendStudioService.update_element` / `move_component` / `remove_element` / `set_animation` / `upsert_step` read through `WorkspaceService` and write the artifact after validation. |
| Conformance by construction | Canvas property/value controls enumerate generated semantic tokens. `engine.studio.tokens_catalog.assert_token_value` rejects hex, px, duration literals, and unknown variants at the production mutation boundary. |
| Side-effect class | `capability.frontend_canvas` is `WORKSPACE_LOCAL`; mutation results report the same class. |
| Typed pixel-signoff honesty before DDE-068 | `request_pixel_signoff` refuses `POLICY_DENIED` and names missing `prototype_pixel_signoff`; the Verify view does not invent a verdict. |

## Adversarial self-check

- A new command id / idempotency key cannot bypass donor approval because
  approval lookup occurs inside every donor-bearing insert after ledger
  admission, scoped to mission + donor + source class.
- A same-millisecond second insert cannot collide with the first element
  anchor: the full UUIDv7 is retained (the truncated timestamp prefix was
  removed after a regression failure).
- A client-crafted off-token value cannot bypass picker constraints because
  `apply_update` calls `assert_token_value` before any workspace write.
- A fabricated client verdict cannot merge: DDE-067 has no quality-verdict
  mutation and DDE-068 remains the blocking executor mission.

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027 / 0033** | Unchanged. EDR-0027 covers sequence/event push; Studio refresh remains session-resume/by-id until that transport lands. |
| DDE-068 | DD207+, silhouette, density, reduced-motion semantics, rendered evidence, and bounded VLM critique. EDR-0016 is accepted and authorizes that next mission. |
| D3 list reads | Mission/donor/evidence list endpoints remain absent; views show empty states or by-id data rather than client-generated rows. No invented contract and no new EDR in DDE-067. |

## Verdict

**PASS-WITH-EDR.** The DDE-067 mutation and UI rules are enforced at
production call sites. Existing EDR-0002, EDR-0003, EDR-0005, EDR-0027,
and EDR-0033 remain open unchanged. DDE-068 is now unblocked by accepted
EDR-0016 and is the next sequential mission.
