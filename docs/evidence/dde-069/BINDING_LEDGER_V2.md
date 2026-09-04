# DDE-069 — binding ledger v2 recovery evidence

**Recorded:** 2026-09-05  
**Mission:** DDE-069 Frontend Studio V2 + Live Design Foundation  
**Recovery base:** `5f8c0c7be827249943063a28fd6490631dbcc8f6`  
**Branch:** `claude/dde-069-frontend-studio-v2-yn110e`

## Repository reconstruction

The recovery began from a fresh checkout of the tracked remote branch. The
last substantive DDE-069 implementation commit before recovery is
`44cf1b9b3e749ff47d941d0c8b0b1ee40f4d33a6`; the two later commits at the
recovery base are Screen Audit/resume documentation changes, not newer product
implementation.

DDE-068 remains `COMPLETE_EVIDENCED`. EDR-0017 is unchanged: broad
`capability.claude_code_invoke` remains privileged and standing-forbidden;
`capability.visual_critique` remains the narrow bounded visual-verification
capability. This tranche does not alter either governance path.

## Truth drift found

`IMPLEMENTATION_STATE.md` still described the host-neutral UI as not started
and retained an old `9 VERIFIED / 14 TYPED_UNAVAILABLE / 76 UNBOUND` snapshot.
The v1 canonical JSON reconstructed at the same HEAD actually contained
`44 VERIFIED / 24 TYPED_UNAVAILABLE / 31 UNBOUND`.
The v1 status axis could mark a visible golden control VERIFIED from backend
files/tests even when its React control did not exist. That is why backend-only
Chat, candidate and Inspector rows appeared farther along than the product.

## Ledger v2 result

The canonical ledger now records explicit applicability and evidence for:

`DOMAIN / READ / COMMAND / STATE / UI / WIRED / E2E / VISUAL`

Final status is derived and is not authored on a row. Current projection:

- `5 VERIFIED`
- `8 BOUND`
- `5 TYPED_UNAVAILABLE`
- `81 UNBOUND`
- `99 total`

Examples proving the semantic correction:

- `CH-01 Chat composer`: DOMAIN/READ/COMMAND/STATE are verified; UI/WIRED/E2E/VISUAL are unbound; FINAL is UNBOUND.
- `IN-10 Gap`: mutation COMMAND is verified, but the declared InspectorDescriptor READ and React control are unbound; FINAL is UNBOUND.
- `CA-07 Try live`: backend candidate/design path is verified; React/WIRED/E2E/VISUAL are unbound; FINAL is UNBOUND.
- `CT-06 Claude /design`: DesignGateway exists, but the command is typed unavailable without a certified design transport; the React button is present but not production-wired.
## Additional corrections made during verification

- `FrontendReadService` no longer claims the Locks group is waiting for M7;
  M7 exists. The honest gap is the missing LockInventory projection.
- Sync evidence is no longer treated as fully authoritative while pending
  M7 mutations are not projected into `FrontendReadService`.
- Inspector mutation-planner evidence is not reused as proof that an
  `InspectorDescriptor` read model exists.
- `/design` no longer tells the user "DesignGateway is M10". It states the
  actual blocker: no certified design-provider transport, with no generic
  Claude Code fallback.
- The Playwright web-server root was fixed. On a clean checkout the old
  config served Vite from `visual/` but waited on `/visual/fixture.html`, a
  404 that made the suite time out rather than execute.

## Verification

- `ruff check` on changed Python: PASS.
- `mypy engine/studio/binding_matrix.py engine/studio/reads.py`: PASS.
- binding-ledger + chat-intent unit tests: **25 passed**.
- React TypeScript `npm run check`: PASS.
- Playwright structural/honesty suite: **16 passed** at the locked 1672x941
  frame, including real local mode-state changes and honest `/design` state.

An expanded PostgreSQL-backed selection was attempted on the clean runner.
It produced 32 passes and 18 pre-test configuration failures because the
runner has no `DDE_DATABASE_URL` or `DDE_REDIS_URL`; Docker/Postgres/Redis are
not installed on that machine. Those results are `UNAVAILABLE`, not product
failures, and are not counted as fresh database verification for this tranche.
## External blockers preserved

AD-039 still blocks `PIXEL_REFERENCE` conformance because the approved
1672x941 golden artifact is absent. Structural conformance remains testable
and passed in this tranche.

Claude `/design` remains unavailable until a certified `DesignProvider`
transport exists. That blocker does not prevent deterministic Frontend Studio
work and does not authorize use of `capability.claude_code_invoke` as an
unattended substitute.

## Next executable dependency

The next vertical packet is the real candidate workbench loop:

code-backed isolated candidate preview → honest preview states → stable
rendered-node/`pxg_key` identity → canvas selection → Inspector descriptors →
token/lock-governed mutation through the existing Gateway/MutationPlanner →
candidate rerender → verification invalidation/recheck.

This packet must be proven through the real React workbench before backend
breadth is expanded further.
