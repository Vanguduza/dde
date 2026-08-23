"""Idempotent acceptance of the human-approved EDRs into Project Truth.

The project owner explicitly accepted EDR-0001..EDR-0010 (the markdown
pre-images under docs/truth/edr/). Per Chapter 2.2 rank 4 and Chapter 3.6 the
authoritative record of that acceptance is a row in `edrs` written by
`engine.truth.service.TruthService` — the sole Project Truth writer — never a
hand-written SQL insert. This operator script provisions, once and
idempotently, the durable tenant/project/principal scaffold those rows
foreign-key against, then runs the propose -> accept path for each pre-image.

Slug uniqueness is per-project, so re-running after a full run is a no-op
reconciliation read, and a partial run proposes+accepts only missing slugs.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.edr import Edr
from engine.gateway.settings import get_settings
from engine.truth.db import build_engine, open_unit_of_work
from engine.truth.repository import TruthRepository
from engine.truth.service import TruthService

# Fixed, documented identifiers for the human-owner governance scope. They are
# constants, not secrets; determinism is what lets this acceptance runner and
# its verification test agree on one durable scaffold.
OWNER_TENANT_ID = UUID("9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d10")
OWNER_PROJECT_ID = UUID("9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d11")
OWNER_PRINCIPAL_ID = UUID("9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d12")

ACCEPTED_OWNER_EDR_SLUGS: frozenset[str] = frozenset(
    f"EDR-{number:04d}" for number in range(1, 11)
)

#: PROPOSED pre-images awaiting a human decision -- registered here so the
#: acceptance runner can reconcile them once accepted, but never proposed or
#: accepted by this script's run loop itself. Acceptance is always a human
#: act; registration only records that the markdown pre-image exists.
PROPOSED_OWNER_EDR_SLUGS: frozenset[str] = frozenset({"EDR-0012"})


def _payload(slug: str) -> dict[str, object]:
    """Faithful transcription of the accepted markdown pre-images."""
    payloads: dict[str, dict[str, object]] = {
        "EDR-0001": {
            "context": (
                "Claude Code must authenticate with the entitlement of a "
                "human's already-authenticated Claude Pro/Max subscription "
                "session, not an API key DDE mints. Chapter 14.3's "
                "CredentialProvider/CredentialHandle mechanics model only "
                "broker-originated short-lived secrets, while this credential "
                "is one DDE does not originate, cannot freely mint, is "
                "long-lived and refreshable, and may only be revocable by the "
                "human at the vendor — a genuine blueprint gap. Research "
                "(2026-08-21): interactive-session refresh tokens are unsafe "
                "to redeem programmatically (single-use rotation, headless "
                "401s); automating the real, unmodified claude binary is "
                "Anthropic-permitted while extracting or relaying its "
                "credential material is prohibited; headless invocation draws "
                "from a separate Agent SDK credit pool; no local socket lets "
                "a second process reuse an authenticated session for "
                "different work."
            ),
            "alternatives": [
                "Force-fit Claude Code onto the static-secret tier via a "
                "long-lived Anthropic API key — rejected: contradicts the "
                "requirement and is a different product surface in billing "
                "and rate limits.",
                "Adapter holds and uses the vendor CLI session directly, "
                "bypassing the broker — rejected: moves long-lived credential "
                "usage outside the engine/capabilities/broker secret boundary "
                "and Chapter 14.5 audit reach.",
                "Broker custodies a delegated subscription session "
                "(DelegatedSessionProvider + register_delegated_session via "
                "token exchange or full mediation) — retained as deferred "
                "Path B for the no-human-present deployment shape, blocked on "
                "Open Questions #1/#2.",
                "Subprocess-only Path A: adapters/claude spawns the "
                "unmodified claude binary behind a mandatory per-invocation "
                "human approval gate, touching no credential material — "
                "implemented.",
            ],
            "decision": (
                "Accepted as designed. Delegated subscription session is the "
                "primary provider for the Claude/Anthropic capability with a "
                "static Anthropic API key as fallback only (human decision on "
                "primary/fallback order, 2026-08-21). The buildable shape is "
                "Path A: adapters/claude.ClaudeCodeWorkerAdapter is a fail-"
                "closed-until-approved policy shell whose start() requires a "
                "human-approved external_model_invocation Approval bound by "
                "scope_hash before spawning the unmodified claude executable, "
                "enforces at most one live invocation, reports cost honestly "
                "as unknown-to-DDE, and never reads ~/.claude/.credentials"
                ".json or CLAUDE_CODE_OAUTH_TOKEN/ANTHROPIC_API_KEY/"
                "ANTHROPIC_AUTH_TOKEN nor calls Anthropic APIs directly. "
                "external_model_invocation joins APPROVAL_TYPES and "
                "STANDING_FORBIDDEN_TYPES so a StandingApproval can never "
                "cover it; capability.claude_code_invoke is seeded with "
                "side_effect_class=EXTERNAL_NON_IDEMPOTENT, "
                "enforcement_tier=T1. Path B (broker-custodied "
                "DelegatedSessionProvider/register_delegated_session) remains "
                "deferred and unbuilt, blocked on Open Question #1 (may DDE "
                "hold session material at rest at all) and #2 (device-flow/"
                "token-exchange API suitability); installer UX changes remain "
                "downstream of Path A's contract tests."
            ),
            "rationale": (
                "Reuses existing broker mechanics rather than inventing a "
                "parallel authentication system; keeps 'never hand a "
                "long-lived credential to anything executing model-generated "
                "code' true by construction under either token exchange or "
                "full mediation; keeps DeepSeek/Hermes (zero new mechanism) "
                "and Claude Code (a genuinely new tier) separate instead of "
                "stretching one abstraction badly. Path A additionally "
                "resolves Open Question #1 by construction — DDE custodies no "
                "credential at all — stays inside Anthropic's documented "
                "official-binary automation carve-out, and implements the "
                "human's explicit per-invocation approval requirement as a "
                "fail-closed gate at the real subprocess spawn call site "
                "rather than by reviewer discipline."
            ),
            "consequences": [
                "Chapter 14.3 gains an explicitly lowest, different-in-kind "
                "delegated-session tier; blueprint §14.3 should reflect it "
                "when Path B is built.",
                "Path B would add a sixth broker operation, new audit event "
                "types and a dedicated registered-delegated-session record "
                "with its own schema, RLS and tenant/project scoping — "
                "deferred follow-on design work.",
                "Routing/worker-profile certification must treat 'delegated "
                "session not registered' as a visible-but-unselectable "
                "candidate reason.",
                "The Windows installer needs a materially different Claude "
                "Code branch ('Sign in with Claude Code'; no secret ever "
                "written to config.toml/.env), downstream of Path A's "
                "contract tests.",
                "Headless subscription usage is metered in a separate pool "
                "shared with the human's own use, so concurrency is capped at "
                "one live Claude Code WorkerRun inside the adapter.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0002": {
            "context": (
                "DDE-030 implemented the Chapter 5.4 semantic index lifecycle "
                "(build, incremental update/invalidation, embedding-model "
                "versioning, staleness detection, tombstone-on-delete) and a "
                "Chapter 5.2 semantic retriever, then wired it into "
                "ContextService.compile() unconditionally whenever an index "
                "existed — with no eval corpus, no uplift measurement against "
                "the lexical+structural baseline, and no opt-in gate, "
                "silently enabling the most expensive, least debuggable "
                "retriever by default contrary to Chapter 5.2's requirement "
                "that semantic retrieval demonstrate uplift on the eval "
                "corpus before it is enabled by default. The embedding itself "
                "is a deterministic hashing-trick bag-of-tokens vector, not a "
                "transformer embedding — a legitimate zero-new-dependency "
                "stand-in (Chapter 9.6) that is nonetheless not what Chapter "
                "5.13's uplift evaluation is meant to certify."
            ),
            "alternatives": [
                "Keep the retriever enabled by default whenever an index "
                "exists and measure uplift later.",
                "Remove the semantic retriever entirely until Stage 3.",
                "Keep it implemented and testable but disabled by default in "
                "the production call site, enabled only through evidence-"
                "backed promotion.",
            ],
            "decision": (
                "Semantic retrieval stays implemented (all four Chapter 5.4 "
                "lifecycle operations, the retriever, the staleness gate) but "
                "disabled by default at the only production call site: "
                "ContextService.compile() consults the index, runs the "
                "semantic retriever and applies the staleness gate only when "
                "a caller explicitly opts in via "
                "semantic_retrieval_enabled=False-by-default. An index merely "
                "existing is no longer sufficient to enable it. The hashing-"
                "trick embedding remains the model until a real embedding "
                "model plus pgvector dependency clears a Chapter 9.6 licence/"
                "maintenance review; EMBEDDING_MODEL_VERSION bumps then "
                "re-index through the existing change_embedding_model/"
                "activate_index lifecycle, so no schema change is needed "
                "later."
            ),
            "rationale": (
                "Makes the 'not enabled by default' half of Chapter 5.2 true "
                "at the production call site rather than in a docstring, "
                "without discarding tested infrastructure; defers enabling to "
                "the follow-on mission (tracked as DDE-031) building the "
                "Chapter 5.13 eval corpus and promotion gate, so flipping the "
                "flag becomes an evidence-backed act instead of a hand-set "
                "constructor default."
            ),
            "consequences": [
                "No project gets semantic results injected into a "
                "ContextPackage without explicit, code-reviewed opt-in, "
                "closing the undisclosed-divergence gap.",
                "DDE-031 has a concrete, blueprint-anchored deliverable: the "
                "Chapter 5.13 corpus and promotion gate that eventually flips "
                "semantic_retrieval_enabled for evidenced reasons.",
                "Until promotion, retrievers_used for every ContextPackage "
                "stays (explicit, authority, lexical, structural), matching "
                "the Stage 1 set Chapter 5.2 prescribes.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0003": {
            "context": (
                "Chapter 5.13 names five promotion gates a new context policy "
                "must clear against the current certified baseline, 'all must "
                "hold': critical coverage, context-attributed failure rate, "
                "contradiction rate, task success on corpus, and token cost "
                "per verified success (reported, not a gate on its own). "
                "DDE-031 implemented the corpus construction protocol in full "
                "(real-mission sourcing via MERGED IntegrationProposals, "
                "mechanically derived ground truth, the draft-to-frozen human "
                "review boundary, retire-never-delete, and the "
                "60-case/6-class/10-adversarial adequacy precondition) but "
                "only gate 1 (critical_coverage), computed by running "
                "ContextService.compile() for baseline and candidate policies "
                "over every frozen case's real source Task and diffing "
                "Chapter 5.8 coverage category-by-category. Gates 2-4 need a "
                "real TaskAttempt/WorkerRun/VerificationRun execution replay "
                "per case that DDE-031's brief did not charter; gate 5 is "
                "denominated in verified successes and depends on gates 2/4's "
                "loop."
            ),
            "alternatives": [
                "Report Chapter 5.13 clearance from gate 1 alone.",
                "Compute gates 2-5 from fabricated or proxy signals.",
                "Restrict the wire-contract decision vocabulary so a bare "
                "PASS is unconstructable and name deferred gates on every "
                "run.",
            ],
            "decision": (
                "PromotionGateRun.decision is restricted at the schema layer "
                "to INSUFFICIENT_CORPUS, FAIL, or "
                "PARTIAL_PASS_IMPLEMENTED_GATES_ONLY — never a bare PASS — so "
                "no caller can construct a run claiming full Chapter 5.13 "
                "promotion. gate_results always names its own deferred_gates "
                "list (context_attributed_failure_rate, contradiction_rate, "
                "task_success_on_corpus, token_cost_per_verified_success) so "
                "any single run self-describes what was not evaluated. No "
                "production call site wires a "
                "PARTIAL_PASS_IMPLEMENTED_GATES_ONLY decision into flipping "
                "ContextService.semantic_retrieval_enabled; that remains the "
                "manual, code-reviewed change EDR-0002 describes, until a "
                "follow-on mission (provisionally DDE-032) implements gates "
                "2-4's execution-replay mechanism and gate 5's reporting and "
                "'all must hold' can be evaluated for real."
            ),
            "rationale": (
                "Prevents overclaiming at the data layer rather than by "
                "convention: the decision vocabulary and the deferred_gates "
                "field make a partial result unmistakable in the persisted "
                "record itself, honouring the chapter's 'all must hold' "
                "semantics while leaving the implemented gate genuinely "
                "useful."
            ),
            "consequences": [
                "The Chapter 5.13 corpus (sourcing, ground truth, freeze, "
                "adequacy) is real production infrastructure independent of "
                "how many gates run over it; gates 2-5 can be added without "
                "touching engine.context.eval_corpus or the eval_cases "
                "schema.",
                "A PARTIAL_PASS_IMPLEMENTED_GATES_ONLY run can never be "
                "mistaken for Chapter 5.13 promotion clearance.",
                "semantic_retrieval_enabled stays False by default (EDR-0002) "
                "until gates 2-5 exist and a real corpus — none yet has 60 "
                "frozen cases — actually clears all five.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0004": {
            "context": (
                "Chapter 5.11 requires a deterministic rule set first (was a "
                "required category partial? did the worker request context "
                "that existed but was not supplied? did it edit outside the "
                "supplied scope?) with model judgment only as fallback. "
                "DDE-034 implemented the real production writer "
                "engine.attribution wired into VerificationRunnerService.run()"
                "'s FAILED branch in the same transaction as the FAILED "
                "VerificationRun/TaskAttempt rows, idempotent on "
                "verification_run_id. Three gaps are deliberately open and "
                "disclosed: the context_request_denied rule cannot be "
                "evaluated because Chapter 5.12's ContextRequest/"
                "ContextResponse expansion has no writer anywhere yet; the "
                "model-judgment fallback is unimplemented, so inconclusive "
                "rule verdicts persist honestly as outcome=inconclusive; and "
                "Chapter 6.8's routing-learning exclusion filter has no "
                "consumer until ExperienceRecord eligibility filtering "
                "(DDE-057, Stage 7). The scope-overreach rule's causal "
                "disambiguation is additionally a Stage 1 approximation that "
                "attributes away from context when coverage categories are "
                "complete."
            ),
            "alternatives": [
                "Approximate the context_request_denied signal or ship a "
                "model-judgment stand-in.",
                "Leave the gaps implicit, discoverable only by reading source "
                "docstrings.",
                "Ship the rules that are real and disclose, per persisted "
                "row, exactly which rules did not evaluate.",
            ],
            "decision": (
                "Accepted as designed. FailureAttribution.method is "
                "restricted at the schema level to rule_based or "
                "model_judgment, and no writer constructs model_judgment "
                "rows today, so every persisted row is honestly rule_based. "
                "eligible_for_promotion_gating is enforced False whenever "
                "outcome == 'inconclusive' in engine.attribution.rules, so "
                "EDR-0003's still-open gate 2 can never be fed a definite "
                "verdict it did not earn. excluded_from_routing_learning is "
                "computed and persisted for real for the future Chapter 6.8 "
                "consumer, and rule_reasons names "
                "CONTEXT_REQUEST_RULE_DEFERRED explicitly on every row so no "
                "reader must cross-reference this record to know the rule was "
                "not evaluated."
            ),
            "rationale": (
                "Keeps every persisted attribution honest about its own "
                "evidentiary basis while making the failure_attributions "
                "table, its idempotency key and its real mutation call site "
                "durable infrastructure that a later mission can extend — "
                "adding the denied-request rule once Chapter 5.12 exists, or "
                "a real model-judgment fallback — without touching the schema "
                "or the call site."
            ),
            "consequences": [
                "Chapters 5.9 (Context Critic) and 5.13 (promotion gate 2) "
                "have a real, if partial, attribution source; rewiring them "
                "to consume it is named follow-on work, not done implicitly.",
                "The context_request_denied gap closes automatically once "
                "Chapter 5.12's just-in-time expansion feeds the rule; no "
                "schema change is anticipated.",
                "The scope-overreach precedence choice (coverage-partial "
                "wins over scope-overreach) remains a disclosed Stage 1 "
                "simplification pending the model-judgment fallback "
                "decision.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0005": {
            "context": (
                "Chapter 6.5 enumerates what must be recorded for every "
                "routing decision — candidate set, predictions, propensity, "
                "verified outcomes, costs, attribution — as cheap and 'must "
                "never be skipped'. RouterService.route() already persists "
                "the decision-time half on RouteDecision rows (candidates; "
                "predicted_success/cost/latency/confidence currently always "
                "None; selection_propensity fixed 1.0, Chapter 6.3's literal "
                "value for deterministic selection). DDE-035 added the "
                "outcome-side writer engine.telemetry, wired into "
                "VerificationRunnerService.run()'s PASSED and FAILED "
                "branches in the same transaction as the run's status write, "
                "resolving the real RouteDecision through WorkerRun."
                "execution_plan_id to ExecutionPlan.route_decision_id and "
                "idempotent on verification_run_id. Two listed fields have no "
                "upstream producer anywhere in the codebase: actual "
                "token/tool cost (no UsageRecord writer exists) and a "
                "versioned 'context policy version' concept, for which "
                "RoutingDecisionOutcome stores the real context_package_id "
                "join key instead of a fabricated version string; the cost "
                "gap is disclosed per row via disclosed_gaps."
            ),
            "alternatives": [
                "Skip outcome telemetry until every Chapter 6.5 field has a producer.",
                "Record fabricated cost and policy-version values.",
                "Emit outcome-side telemetry at the two terminal verification "
                "branches, disclosing absent fields on every row.",
            ],
            "decision": (
                "Accepted as designed. Chapters 6.6 (Route Critic) and 6.7 "
                "(exploration and propensity) are deferred: the critic's "
                "triggers need real predicted_success/confidence that no "
                "pipeline produces yet, and exploration needs a ranked "
                "candidate set that Chapter 6.1's deterministic policy table "
                "does not expose — implementing either today would require "
                "fabricating trigger reasons, which the no-fabricated-signal "
                "discipline refuses. RoutingDecisionOutcome.escalated and "
                ".human_intervention_required are read from the real "
                "RecoveryDecision and are not a stand-in for the Route "
                "Critic. A future mission that adds real predicted_success is "
                "the natural point to implement Chapter 6.6; real exploration "
                "waits for a genuine ranked candidate set to explore among."
            ),
            "rationale": (
                "Outcome telemetry is exactly the input both deferred "
                "chapters name as their prerequisite; recording it now, "
                "honestly and completely apart from named gaps, is what makes "
                "later learning possible without an architectural migration — "
                "Chapter 6.5's own stated purpose."
            ),
            "consequences": [
                "Chapter 6.8's ExperienceRecord (DDE-057, Stage 7) can be "
                "built against two real upstream sources: FailureAttribution "
                "(EDR-0004) and RoutingDecisionOutcome.",
                "failure_attribution_id is a real non-null FK on every FAILED "
                "row, closing EDR-0004's noted unwired integration on the "
                "telemetry side specifically.",
                "Stale docstrings claiming Chapter 5.11 is unbuilt were "
                "corrected (disclosure-only change) during the originating "
                "mission.",
                "Route Critic and exploration remain unbuilt until real "
                "predictions or ranked candidates exist; heuristic prediction "
                "proxies are refused unless a future decision says otherwise.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0006": {
            "context": (
                "Chapter 6.4 repositions the Routing Simulation Model as an "
                "evaluation and fixture-generation subsystem — never a "
                "training source for a production policy, never an authority "
                "— and names five example adversarial fixture classes. "
                "engine.simulation implements a real, deterministic fixture "
                "generator (engine.simulation.scenarios) driving the real "
                "engine.routing.rules.evaluate() elimination pipeline (never "
                "RouterService.route(), so simulation can never author a "
                "RouteDecision) and persists one RoutingSimulationRun per "
                "invocation with reproducible seed, policy_version and "
                "model_version. Three of the named classes are real today — "
                "worker_outage, generator_independence_violation and "
                "hard_gate_approval_required — each escalating through "
                "evaluate()'s genuine gates, verified directly in "
                "tests/unit/test_simulation_scenarios.py without mocked or "
                "hand-computed results."
            ),
            "alternatives": [
                "Fabricate registry entries or signals to force all five "
                "named fixture classes into existence.",
                "Implement only the classes Stage 1's real signals support "
                "and disclose the rest per persisted run.",
            ],
            "decision": (
                "Accepted as designed. capability_gap, "
                "environment_incompatibility, modality_mismatch and "
                "budget_exhaustion are not implemented: the Stage 1 "
                "worker-profile registry uniformly satisfies each workload "
                "class's preference, so no real gate-1/gate-4 failure set "
                "exists to simulate without misrepresenting a certified "
                "profile; Stage 1 has no per-task modality signal (the Visual "
                "retriever is Stage 5, DDE-044); and gate 5 "
                "(capacity_availability) is a disclosed hard-coded pass-"
                "through with no worker health/quota/concurrency/budget "
                "signal behind it to exhaust. Every RoutingSimulationRun "
                "names any requested-but-deferred class in disclosed_gaps "
                "rather than silently dropping it. experience_origin is "
                "hard-coded 'simulation' and excluded_from_routing_learning "
                "hard-coded True, so the table carries no path into any "
                "future training pipeline by construction."
            ),
            "rationale": (
                "A simulated mismatch or exhaustion needs two real values to "
                "mismatch or a real signal to drain; fabricating them would "
                "misrepresent certified profiles or invent telemetry, "
                "violating the no-fabricated-signal discipline the rest of "
                "the routing chapters depend on."
            ),
            "consequences": [
                "Chapter 6.4's regression/stress-testing use is real today "
                "for the three implemented classes: policy-table changes "
                "breaking outage handling, generator independence or the "
                "hard approval gate are caught by test_simulation_scenarios."
                "py and any CI caller of RoutingSimulationService."
                "run_regression().",
                "Cold-start sanity checks for new workload classes become "
                "mechanical ScenarioFixture branches once a real elimination "
                "signal exists for that class.",
                "The remaining four classes wait on a richer non-uniformly-"
                "capable registry (Chapter 8 territory), a modality signal "
                "(Stage 5), or a capacity signal (Chapter 7.4, DDE-029) — "
                "each a future mission's natural entry point.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0007": {
            "context": (
                "Chapter 11.3: 'Task oracles prove the tasks were done. The "
                "mission oracle proves the right product was built.' Three "
                "production rules: every mission with risk >= medium carries "
                "a mission oracle whose observable_outcomes are end-to-end "
                "and user-visible; mission completion requires the mission "
                "oracle to pass on the mission branch before merge to main "
                "(Ch.10.8); and if all task oracles pass while the mission "
                "oracle fails, the outcome is WRONG_PRODUCT -- the mission "
                "enters replanning with the failing outcomes as context, and "
                "the discrepancy is a first-class learning signal about "
                "decomposition quality, not worker quality. DDE-037 "
                "implemented a real mission-scope AcceptanceOracle (task_id "
                "null -- never a fabricated task identity), a durable "
                "evaluator (MissionOracleService.evaluate(), CommandLedger-"
                "guarded, driving the same run_check path task oracles use), "
                "and a completion gate on MissionService.transition_mission("
                "..., COMPLETED). WRONG_PRODUCT is recorded only when every "
                "defined task-scope oracle has a latest PASSED "
                "VerificationRun and the mission oracle itself fails."
            ),
            "alternatives": [
                "Ship only the oracle contract and disclose Chapter 11.3 as "
                "unimplemented.",
                "Implement the completion gate plus a partial evaluator, "
                "disclosing each deferred chapter rule per persisted row.",
                "Fabricate ProductEnvironment e2e probes or an origin-main "
                "merge gate to claim full scope.",
            ],
            "decision": (
                "Accepted as designed, in documented partial scope. Deferred: "
                "(1) end-to-end user-visible outcomes against a "
                "ProductEnvironment -- Stage 1 has only test/invariant "
                "executable bindings; api_probe/visual_diff/browser and "
                "ProductEnvironment lifecycle are DDE-038/043/044; the slice "
                "runs test/invariant bindings in the supplied workspace and "
                "names the gap in every evaluation's disclosed_gaps. (2) "
                "Merge-to-main gating (Ch.10.8): IntegrationQueueService "
                "still advances the mission integration branch; the "
                "production completion gate is MissionService."
                "transition_mission to COMPLETED; origin-mainline merge "
                "remains the DDE-013 deferral. (3) Automatic replan "
                "invocation: RecoveryService.replan(trigger=WRONG_PRODUCT) "
                "exists (DDE-024) but this slice classifies WRONG_PRODUCT, "
                "attaches decide(WRONG_PRODUCT) to the evaluation row, and "
                "refuses COMPLETED without calling replan() itself. (4) "
                "Mission.risk is derived from max(task.risk_class) -- the "
                "only real signal. (5) 'Authored during planning' is "
                "process sequencing, not a second database lock."
            ),
            "rationale": (
                "The wrong-product classification and completion refusal are "
                "real at their production call sites; deferring the missing "
                "substrates by name keeps every persisted evaluation honest "
                "about its own evidentiary basis instead of fabricating a "
                "product runtime or a merge gate that does not exist."
            ),
            "consequences": [
                "A planted wrong-product whose task oracles are green and "
                "whose mission oracle fails is classified WRONG_PRODUCT with "
                "learning_signal_class=decomposition_quality and "
                "excluded_from_routing_learning=true -- by construction, not "
                "caller discretion.",
                "Medium-or-higher missions cannot COMPLETE without an ACCEPT "
                "evaluation; a WRONG_PRODUCT evaluation refuses COMPLETED "
                "even on a low-risk mission that happened to define a "
                "mission oracle.",
                "Recovery matrix WRONG_PRODUCT remains the operator/dispatch "
                "path for actually replanning.",
                "ProductEnvironment e2e outcomes, merge-to-main gating and "
                "automatic replan invocation stay gated on their own "
                "missions.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0008": {
            "context": (
                "Playbook guardrail 4.4 (screenshot-evidence gate, Phase B) "
                "and 4.9 (accessibility floor automation) require two "
                "capabilities no existing repo toolchain provides: pixel-"
                "level screenshot goldens over gallery/prototype pages (DOM "
                "string fingerprints pin structure and token usage but "
                "cannot see rendered geometry, contrast failures, or layout "
                "collapse at viewport extremes), and automated WCAG 2.x "
                "A/AA evaluation of shipped surfaces (manual keyboard walks "
                "and contrast math cover design-time, not regression-time "
                "enforcement). AGENTS.md Chapter 9.6 admits a new dependency "
                "only with licence, maintenance signal, and why the stdlib/"
                "existing toolchain is insufficient."
            ),
            "alternatives": [
                "Storybook/Ladle -- rejected: no component framework or "
                "bundler exists to host them.",
                "Chromatic/Percy/Lost Pixel -- rejected: SaaS cost and "
                "Storybook-centric architecture.",
                "stylelint plugins -- rejected: DDE styles live in TS strings.",
                "Rive/Lottie/Figma Motion -- rejected: CSP + admission bar.",
                "Adopt exactly Playwright + @axe-core/playwright behind one "
                "dependency-admission decision -- accepted.",
            ],
            "decision": (
                "Accepted as designed. Adopt exactly two dependencies: "
                "@playwright/test (Apache-2.0, Microsoft-backed) for "
                "expect(page).toHaveScreenshot() goldens over Prototype "
                "Gallery pages -- light/dark/high-contrast x reduced-motion "
                "on/off x widths 320/900/1280, baselines generated in the CI "
                "container and updated only in owning PRs; and "
                "@axe-core/playwright (MPL-2.0, Deque Systems) for WCAG "
                "scans per gallery page with tags wcag2a,wcag2aa,wcag22aa "
                "and zero critical/serious violations gating the PR, "
                "target-size rule enabled. Scope when accepted: one new "
                "'visual' job in .github/workflows/dde-studio.yml after the "
                "compile job; screenshots attached as VerificationRun/"
                "Evidence artifact refs; baselines never updated by CI "
                "itself. Implementation proceeds in a separate workstream -- "
                "the visual CI job, golden baselines and axe gates are gated "
                "on their own missions and are not landed by this decision."
            ),
            "rationale": (
                "Node stdlib and node:test have no browser runtime -- "
                "rendered-pixel capture is the entire point of guardrail "
                "4.4 -- and accessibility rule evaluation against live DOM "
                "cannot be reproduced from static strings; both are "
                "industry-standard, actively maintained OSS tools admitted "
                "once instead of re-litigated per PR."
            ),
            "consequences": [
                "node_modules footprint grows materially (browser binaries); "
                "the CI cache key must include the Playwright version.",
                "Flaky-diff risk managed via maxDiffPixels budgets per "
                "element class; threshold tuning documented in playbook "
                "section 4.4 sources.",
                "Rejection would have kept screenshot/a11y gates at Phase-A "
                "state: fingerprints + manual review remain enforcement and "
                "Phase-B rows stay deferred.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0009": {
            "context": (
                "Chapter 6.5 requires DDE to record, for every routing "
                "decision, its actual verified outcome among other outcome-"
                "side signals; the durable shape is the RoutingDecisionOutcome "
                "row, whose actual_verified_outcome enum admits only PASSED/"
                "FAILED, and RoutingTelemetryService.record_decision_outcome "
                "refuses any VerificationRun whose status is not terminal "
                "PASSED or FAILED. The verification self-grading guardrails "
                "introduced a third real verdict: when VerificationRunner"
                "Service.run() detects harness-gaming edits via engine."
                "verification.guardrails.assess_diff_independence, it still "
                "runs the oracle's checks but forces the run's status to "
                "PARTIAL (never PASSED) so an untrusted clean pass is not "
                "certified; the attempt is durably FAILED with "
                "failure_class=SCOPE_VIOLATION through the existing recovery "
                "surface -- but the PARTIAL VerificationRun itself can never "
                "produce a telemetry outcome row. Consequence: every "
                "guardrail-demoted verification silently drops out of "
                "Chapter 6.5's decision-outcome history, even though those "
                "runs are exactly the population a learning pipeline must "
                "not train on as successes and worth counting when tuning "
                "guardrail thresholds."
            ),
            "alternatives": [
                "Widen the enum/schema: admit PARTIAL in "
                "actual_verified_outcome and add a demotion_reason field to "
                "RoutingDecisionOutcome -- rejected: changes a Chapter 6.5 "
                "schema contract for a Stage-1-only producer and blurs the "
                "chapter's meaning of actual_verified_outcome.",
                "Side-table keyed by verification_run_id (recommended): keep "
                "actual_verified_outcome PASSED/FAILED and "
                "record_decision_outcome's terminal gate untouched; add a "
                "small durable side-table (verification_run_demotions) "
                "written by the same guarded runner path that forces "
                "PARTIAL; telemetry consumers join on verification_run_id "
                "when they need the demoted population.",
            ],
            "decision": (
                "Accepted as designed, option 2 (the recommended side-table). "
                "schemas/objects/routing_decision_outcome.json stays byte-"
                "stable; RoutingTelemetryService is unchanged; every "
                "guardrail-demoted PARTIAL run gains its own durable, "
                "queryable demotion record keyed by verification_run_id "
                "instead of overloading an outcome enum designed before the "
                "guardrails existed."
            ),
            "rationale": (
                "Gives the demotion its own durable identity without "
                "blueprint enum surgery: the main Chapter 6.5 row stays "
                "exactly as the blueprint defines it while consumers can "
                "explicitly exclude or count the demoted population via a "
                "join on verification_run_id."
            ),
            "consequences": [
                "Every guardrail-demoted PARTIAL run leaves a queryable "
                "trace; Chapter 6.5 consumers can exclude or count them "
                "explicitly.",
                "The blueprint enum stays untouched; no change to "
                "RoutingTelemetryService or its terminal gate.",
                "A new table + writer + tests were required (landed with "
                "migration 0011 in the implementing mission).",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0010": {
            "context": (
                "Chapter 12.3's recovery matrix dispatches on failure class. "
                "The implemented matrix recognises WORKER_FAILURE, "
                "MERGE_CONFLICT, SCOPE_VIOLATION, VERIFICATION_FAILURE, "
                "WRONG_PRODUCT, SPECIFICATION_FAILURE, RESOURCE_EXHAUSTION, "
                "SIDE_EFFECT_UNKNOWN and DRIFT_FAILURE -- every row "
                "describes something going wrong with the work. An operator "
                "stopping a run via the kill flag is not a failure of the "
                "work: the durable stop record lives in the CommandLedger "
                "under one deterministic key per run "
                "(kill_flag_run_stop:{worker_run_id}), armed/flipped by "
                "CapabilityLeaseService.arm_run_stop/disarm_run_stop, and "
                "enforcement fails closed at capability checkout and broker "
                "admission with typed KILL_FLAG_ACTIVE. Because the taxonomy "
                "had no distinct intentionally-stopped class, the mapping "
                "layer routed the refusal onto a borrowed row: KILL_FLAG_"
                "ACTIVE -> AUTHORIZATION_FAILURE -- chosen because adding a "
                "class would be a Project Truth change, proposed not made. "
                "The mismatch is semantic, not cosmetic: AUTHORIZATION_"
                "FAILURE means 'the system refused to act; a human must "
                "grant authority', while an intentional stop withdraws "
                "authority deliberately; resuming should require an explicit "
                "acknowledge-style action after review rather than being "
                "misread downstream as an authorization-failure episode."
            ),
            "alternatives": [
                "Keep the borrowed AUTHORIZATION_FAILURE mapping and record "
                "the semantic mismatch in a comment only -- rejected once a "
                "human decision adopted the dedicated row.",
                "Add a distinct INTENTIONALLY_STOPPED classification raised "
                "from the existing KILL_FLAG_ACTIVE refusal sites and/or the "
                "durable ledger stop record, governed on its own terms -- "
                "accepted.",
            ],
            "decision": (
                "Accepted as designed. Add INTENTIONALLY_STOPPED to the "
                "Chapter 12.3 recovery matrix with governed action "
                "acknowledge_stop: requires_human=True, no automatic retry, "
                "no replan, allow_new_worker_run=False until an operator "
                "acknowledges the stop; after acknowledgement a new "
                "WorkerRun is permitted through the normal guarded path, "
                "never a silent continuation of the stopped attempt. The "
                "KILL_FLAG_ACTIVE -> AUTHORIZATION_FAILURE alias mapping is "
                "retired for this case."
            ),
            "rationale": (
                "An intentional stop is authority deliberately withdrawn by "
                "an operator, not a refusal the system made; governing it on "
                "its own matrix row stops failure-counting consumers from "
                "conflating operator stops with authorization refusals or "
                "verification failures, and makes acknowledge-gated restarts "
                "a property of the data rather than operator discipline."
            ),
            "consequences": [
                "Intentional stops become a first-class, queryable recovery "
                "outcome with acknowledge-gated restarts.",
                "The borrowed AUTHORIZATION_FAILURE row is retired for this "
                "case; consumers that count failures stop conflating "
                "operator stops with refusals.",
                "Required the classification addition plus matrix wiring in "
                "its own mission (landed alongside this ratification).",
            ],
            "affected_requirement_slugs": [],
        },
    }
    return payloads[slug]


async def ensure_scaffold(engine: AsyncEngine) -> None:
    """Insert the owner tenant/project/principal rows if absent."""
    now = datetime.now(UTC)
    async with open_unit_of_work(
        engine, tenant_id=OWNER_TENANT_ID, project_id=OWNER_PROJECT_ID
    ) as uow:
        await uow.connection.execute(
            text(
                "INSERT INTO tenants (tenant_id, slug, created_at, updated_at) "
                "VALUES (:tenant_id, :slug, :now, :now) ON CONFLICT (tenant_id) "
                "DO NOTHING"
            ),
            {"tenant_id": OWNER_TENANT_ID, "slug": "owner", "now": now},
        )
        await uow.connection.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, slug, created_at, "
                "updated_at) VALUES (:project_id, :tenant_id, :slug, :now, :now) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "project_id": OWNER_PROJECT_ID,
                "tenant_id": OWNER_TENANT_ID,
                "slug": "owner",
                "now": now,
            },
        )
        await uow.connection.execute(
            text(
                "INSERT INTO principals (principal_id, tenant_id, slug, "
                "created_at, updated_at) VALUES (:principal_id, :tenant_id, "
                ":slug, :now, :now) ON CONFLICT DO NOTHING"
            ),
            {
                "principal_id": OWNER_PRINCIPAL_ID,
                "tenant_id": OWNER_TENANT_ID,
                "slug": "owner",
                "now": now,
            },
        )
        await uow.commit()


async def _existing(
    engine: AsyncEngine, repository: TruthRepository, slug: str
) -> Edr | None:
    async with open_unit_of_work(
        engine,
        tenant_id=OWNER_TENANT_ID,
        project_id=OWNER_PROJECT_ID,
    ) as uow:
        record = await repository.get_edr_by_slug(
            uow.connection, OWNER_PROJECT_ID, slug
        )
        await uow.commit()
    return record


async def accept_edr(
    engine: AsyncEngine,
    service: TruthService,
    repository: TruthRepository,
    slug: str,
) -> tuple[str, UUID]:
    """Propose + accept one EDR, or reconcile an already-present row."""
    existing = await _existing(engine, repository, slug)
    if existing is not None:
        if existing.status != "accepted":
            accepted = await service.accept_edr(
                tenant_id=OWNER_TENANT_ID,
                project_id=OWNER_PROJECT_ID,
                edr_id=existing.edr_id,
                decided_by_principal=OWNER_PRINCIPAL_ID,
            )
            return "accepted-existing-proposal", accepted.edr_id
        return "already-accepted", existing.edr_id
    proposed = await service.propose_edr(
        tenant_id=OWNER_TENANT_ID,
        project_id=OWNER_PROJECT_ID,
        slug=slug,
        context=str(_payload(slug)["context"]),
        alternatives=list(_payload(slug)["alternatives"]),
        decision=str(_payload(slug)["decision"]),
        rationale=str(_payload(slug)["rationale"]),
        consequences=list(_payload(slug)["consequences"]),
        affected_requirement_slugs=list(_payload(slug)["affected_requirement_slugs"]),
    )
    accepted = await service.accept_edr(
        tenant_id=OWNER_TENANT_ID,
        project_id=OWNER_PROJECT_ID,
        edr_id=proposed.edr_id,
        decided_by_principal=OWNER_PRINCIPAL_ID,
    )
    return "accepted", accepted.edr_id


async def run() -> None:
    engine = build_engine(get_settings().database_url)
    try:
        await ensure_scaffold(engine)
        service = TruthService(engine)
        repository = TruthRepository()
        for slug in sorted(ACCEPTED_OWNER_EDR_SLUGS):
            state, edr_id = await accept_edr(engine, service, repository, slug)
            print(f"{slug}: {state} edr_id={edr_id} status=accepted")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
