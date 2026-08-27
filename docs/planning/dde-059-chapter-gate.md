# DDE-059 chapter gate -- adaptive context policy / Ch.5.13 promotion

**Mission:** §18.3 S7 / `DDE-059` -- adaptive context policy with
promotion gates. **Charter:** Chapter 5.13 (all five gates must hold
against the certified baseline before a new context policy is promoted);
push vs pull vs semantic as first-class arms (Graft Pattern 5);
`ContextService.compile()` as the production reader so semantic/push
are not flipped by a constructor default or a PARTIAL_PASS run.
**Not** DDE-060 Flight Lab / Ch.6.10, DDE-061+, or Frontend Studio.

**CI / local proofs (2026-08-27):**

- `just check` green -- ruff / mypy (**368** files) / **1137 passed, 2
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  contract pytest / design-lints baseline / dde-studio `tsc --noEmit`
- `tests/unit/test_context_activation.py`: gates refuse canary on
  PARTIAL_PASS, skip, and insufficient corpus; shadow allowed;
  compile_policy shadow stays pull
- `tests/unit/test_context_activation_postgres.py`: skip-to-canary
  refused; shadow compile stays pull; seeded-canary `compile()` uses
  semantic; `rollback` restores certified pull
- `tests/unit/test_context_assembly.py`: push arm overflows rather than
  silently evicting architecture evidence

## What this mission wires

- `schemas/objects/context_activation_state.json` (migration `0023`,
  tenant/project + RLS).
- Pure mode machine: `engine.context.activation` -- one-step
  `certified_baseline -> shadow -> canary -> promoted`; ROLLBACK to last
  certified; `compile_policy_from_activation`; canary slice.
- Production mutations (`engine.context.activation_service`):
  - `evaluate_candidate` -- Ch.5.13 A/B for one arm vs certified pull
    (`respect_activation=False`).
  - `attempt_advance` -- sole forward `context.mode` writer. Durable
    current mode (a caller cannot skip). Shadow is observation-only.
    Canary/promoted refused on PARTIAL_PASS, FAIL, INSUFFICIENT_CORPUS,
    missing run, or any remaining `deferred_gates`.
  - `rollback` -- from any mode to last certified (Stage 1 pull when
    none); never an untested arm.
- Production reader: `ContextService.compile()` applies the candidate
  arm on the canary slice / promoted traffic. Constructor
  `semantic_retrieval_enabled=False` remains the EDR-0002 default.
- Push arm: `assemble(..., policy_arm="push")` makes architecture/
  security evidence unevictable (bundle injected up front).
- Contradiction rate computed at `PromotionGateService.evaluate` from
  compile-time `CONFLICTED` packages.

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.5.13 all five gates must hold to promote | `ContextActivationService.attempt_advance` -- canary/promoted require empty `deferred_gates` and a non-PARTIAL, non-FAIL run |
| PARTIAL_PASS never flips semantic/push | `attempt_advance` refuses `partial_pass_does_not_flip_production`; `compile()` only applies candidate in canary/promoted |
| Semantic not default-on (Ch.5.2 / EDR-0002) | `ContextService.__init__` default `False`; `compile()` production path reads activation |
| Push vs pull vs semantic as first-class arms | `evaluate_candidate(candidate_arm=)` + `assemble(policy_arm=)` + activation `candidate_arm` |
| Mode one-step; skip refused | `can_transition` inside `attempt_advance`; durable current mode |
| ROLLBACK to last certified, never untested | `ContextActivationService.rollback` -> `context_activation_state` |
| Limited canary | `compile()` + `in_canary_slice`; control slice stays pull |
| Evaluation does not eat its own canary | `PromotionGateService.evaluate` compiles with `respect_activation=False` |
| Contradiction rate no regression | `PromotionGateService.evaluate` -> `contradiction_rate_regressed` |
| Critical coverage no regression | already `PromotionGateService.evaluate` (DDE-032) |
| Token cost regression FAILs | already compile-token mean (DDE-041) |
| Context-attributed failure rate | **deferred** EDR-0003 -- needs worker-verification replay per eval case |
| Task success on corpus | **deferred** EDR-0003 -- same replay |
| Ch.3.2 tenant_id/project_id + RLS | `context_activation_state` `tenant_scoped` / `project_scoped` |
| Idempotency | activation UNIQUE `(tenant_id, project_id)` upsert; promotion runs already keyed |

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002** | Constructor flag remains; hashing-trick embedding unchanged. This mission adds the durable `context_policy` activation row the EDR's open question asked for, but does not enable semantic by default. |
| **EDR-0003** | Gates 2 and 4 still need TaskAttempt/WorkerRun/VerificationRun replay. Contradiction rate is now computed (compile-time). Token cost already computed (DDE-041). No new EDR -- 0003 still covers the replay gap. |
| **EDR-0027** | Sequence/WS/SSE gap replay (Core) -- unchanged |
| Graft-class cached-summary alternative (Pattern 4) | Not implemented; semantic default-on still requires beating it *and* the lexical+structural baseline. Unreachable while canary is refused. Not a new EDR. |

## Adversarial self-check

- A new `WorkerRun` cannot bypass this: compile policy is read from
  `context_activation_state`, not from the run.
- A new idempotency key on `evaluate_candidate` creates a new promotion
  run but cannot write canary (`attempt_advance` is a separate mutation
  and still sees `deferred_gates`).
- Seeding canary via the repository (tests of the reader) is not a
  production mutation; `attempt_advance` is the sole production writer.
- `respect_activation=False` on the eval harness is the control that
  stops a canary from grading itself.

## Verdict

**PASS-WITH-EDR.** EDR-0003 remains open (gates 2 and 4 still need
worker-verification replay). EDR-0002 remains (semantic still default-off;
hashing-trick embedding unchanged). EDR-0027 unchanged. **No new
EDR-0033.** Canary/promoted are unreachable through `attempt_advance`
until those replay gates are computed; `compile()` still honors a canary
row if one exists, which is the production reader a future PASS would
drive. Shadow observation and rollback are live.
