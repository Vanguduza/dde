# DDE-068 closure matrix

Every row is `VERIFIED` only where concrete code, a passing test, or a
recorded execution proves it. Implementation merely existing is not
evidence, and is not accepted here.

Suite at closure: **1272 passed, 2 skipped, 0 failed** (`tests/unit`,
`tests/contract`, `tests/recovery`), plus
`tests/integration/test_accepted_edr_rows.py` (3 passed). Lint, format,
typecheck, contract-drift and design-lints all clean.

| Requirement | Status | Concrete evidence |
|---|---|---|
| Render candidate | VERIFIED | `adapters/playwright/probe.py::PlaywrightBrowserProbe.screenshot` behind `capability.browser`. Live: both candidates rendered from `file://` URLs in the evidence run (`evidence-run.json` → `screenshot_bytes` 88906 / 68067). |
| Capture screenshot/evidence | VERIFIED | `_run_visual_diff` persists actual/diff PNGs + sha256; `_run_visual_critique` records the full verdict as `CheckResult.stdout`, stored as `Evidence` with `evidence_type` = the check kind (`runner.py::_execute_outcome`). Live screenshots committed at `good-candidate.png`, `poor-candidate.png`. |
| Deterministic visual checks | VERIFIED | DD201–DD206 plus DD207 combination lints in `scripts/design_lints.py`, run by `just check`'s `design-lints` recipe against a committed shrink-only baseline. |
| Visual diff where required | VERIFIED | `engine/verification/pixel_compare.py` + `checks.py::_run_visual_diff`; `tests/unit/test_visual_diff.py` (6 tests: match, mismatch, fail-closed without browser). |
| Silhouette/fingerprint gate | VERIFIED | `engine/verification/silhouette.py` (`compute_fingerprint`, `evaluate_silhouette`, self-generated `GENERIC_LAYOUT_CORPUS`); `tests/unit/test_silhouette.py` (10 tests). Live: poor candidate similarity 0.689, good 0.430. |
| Deterministic density evidence | VERIFIED | `silhouette.py::compute_density_evidence` (occupancy ratio, row/column spread, largest empty run, top/bottom balance). Live values recorded per candidate in `evidence-run.json` → `deterministic.density`. |
| Genuine multimodal critique | VERIFIED | `capability.visual_critique` (`engine/capabilities/seed.py`) → `engine/capabilities/visual_critic.py` seam → `adapters/visual_critic/adapter.py::LocalMultimodalVisualCritic`. **Real execution, not a mock:** three live invocations on `claude-sonnet-5`, `$0.3631` measured, recorded in `evidence-run.json` / `evidence-run-good-candidate-cycle1.json`. |
| Believable-density judgment | VERIFIED | Scored rubric dimension `believable_density` in `schemas/design/visual_critique_rubric.json` (playbook §8.3). Live: poor candidate scored **1**, good candidate **5** — a real perceptual discrimination, kept separate from the measured density evidence above. |
| Structured critic verdict | VERIFIED | `VERDICT_JSON_SCHEMA` constrains output at source (`--json-schema`) and `visual_critique.py::parse_verdict` re-validates independently, rejecting malformed JSON, missing fields, out-of-range scores and unknown fields. |
| Bounded repair/revision | VERIFIED | `visual_critique.py::decide_revision_action`, pure so the cap cannot be bypassed by a caller losing count; capped at `MAX_REVISION_CYCLES = 3`. Tests sweep at and past the bound. Live: cycle 0 → `REVISE (1 of 3)`. |
| Re-render/re-evaluation | VERIFIED | Live cycle 1: the good candidate was re-rendered after applying the critic's own `repair_instructions`, and re-critiqued **with the prior critique fed back** (`VisualCritiqueRequest.prior_critique`) so the repair was verified rather than assumed. |
| Final visual verdict | VERIFIED | `evaluate_verdict` applies playbook §8's "any dimension <4 blocks" to validated fields. The model's own verdict word is advisory: a `PASS` claim with a sub-threshold score is still blocked (`test_sub_threshold_dimension_blocks_even_when_critic_says_pass`). |
| Promotion-gate consumption | VERIFIED | `VerificationRunnerService.run()` → `_evaluate()` (kind-agnostic) → `_finalise_passed_attempt` / `_fail_unverified_attempt` → `TaskAttemptService.finalize()` / `.fail()`. Proven against real Postgres in `test_visual_critique_promotion_gate_postgres.py` and `test_silhouette_promotion_gate_postgres.py`. |
| Good-candidate acceptance | VERIFIED | `test_rubric_passing_candidate_is_promoted` → `TaskAttempt.status == COMPLETED`. Live: good candidate cycle 1 → all dimensions ≥ 4 → `PROMOTE` → **ELIGIBLE**. |
| Poor-candidate rejection | VERIFIED | `test_rubric_blocked_candidate_cannot_reach_completed` → `TaskAttempt.status == FAILED`, `failure_class == VERIFICATION_FAILURE`. Live: poor candidate BLOCK at 0.92 → **DENIED**. |
| Critic failure → fail closed | VERIFIED | Missing capability → `POLICY_DENIED`; runtime error/timeout/malformed verdict → `ERRORED`, never `PASSED`. `test_unusable_critic_response_does_not_promote` proves an `ERRORED` run leaves the attempt not `COMPLETED`. Failure classes are kept distinct, not collapsed. |
| Capability containment | VERIFIED | `test_command_carries_every_containment_flag` asserts `--restricted`, `--allowed-tools Read`, the deny list, `--permission-prompts none`, `--json-schema`, a spend ceiling, and the **absence** of `--add-dir`/`--mcp-config`/`--agents`. `test_runtime_receives_only_the_screenshot_in_its_scratch_directory` has a fake runtime *observe* that its working directory held exactly `screenshot.png`. |
| Prompt-injection boundary | VERIFIED | Fixed system contract names rendered UI text as data-not-instructions (`test_system_contract_states_rendered_content_is_data_not_instructions`); an adversarial candidate is reported as a `copy_voice` defect and still blocked; `VisualCritiqueRequest` structurally has no prompt/instruction field. |
| Real end-to-end exercise | VERIFIED | `scripts/dde068_evidence_run.py` + `docs/evidence/dde-068/` — render → capture → deterministic → live critique → verdict → policy → bounded revision → promotion decision, across three real invocations and two candidates. |
| Durable EDR-0017 Project Truth | VERIFIED | Added to `scripts/accept_owner_edrs.py` (`ACCEPTED_OWNER_EDR_SLUGS` + payload) — the repository's authoritative versioned representation, from which any environment's `edrs` table is provisioned. Propose+accept run; row read back via `TruthRepository.get_edr_by_slug` as `status=accepted`, decided by the owner principal, 4 alternatives, decision text covering all seven required elements. Pinned by `tests/integration/test_accepted_edr_rows.py`. |

## Not closed here, by design

Authoring a `visual_diff`/`silhouette`/`visual_critique` binding onto every
generated screen's `AcceptanceOracle` **by default** is DDE-069 work, not a
DDE-068 gap. Repository evidence, not preference, decides that:
`FRONTEND_STUDIO_REV3.md`'s "DDE-068 DEPENDENCY" clause assigns "the final
DDE-069/Frontend Studio V2 promotion must consume real rendered visual
verification" to DDE-069, and its implementation order step 3 is
"close/consume DDE-068 prerequisites needed by V2".

The distinction is deliberate and worth stating plainly:

- **DDE-068 (closed):** the visual verification capability and its
  enforcement exist. A bound check is machine-gated at promotion.
- **DDE-069 (open):** generated screens automatically receive those
  bindings through the Frontend Studio authoring workflow, turning
  "a bound check refuses" into "every generated screen is checked".

That carry-over is recorded in `IMPLEMENTATION_STATE.md`'s DDE-069
cold-start entry packet so it cannot be forgotten.
