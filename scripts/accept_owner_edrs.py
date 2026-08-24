"""Idempotent acceptance of the human-approved EDRs into Project Truth.

The project owner explicitly accepted EDR-0001..EDR-0010 (the markdown
pre-images under docs/truth/edr/). Per Chapter 2.2 rank 4 and Chapter 3.6 the
authoritative record of that acceptance is a row in `edrs` written by
`engine.truth.service.TruthService` — the sole Project Truth writer — never a
hand-written SQL insert. This operator script provisions, once and
idempotently, the durable tenant/project/principal scaffold those rows
foreign-key against, then runs the propose -> accept path for each pre-image.

On 2026-08-24 the project owner issued the standing directive "close all
queued decisions per coordinator recommendations"; that decision accepted
EDR-0012, EDR-0013 and EDR-0014 alongside the Frontend Studio charter v3
sign-off, extending the accepted processing below to EDR-0001..EDR-0014.

Later on 2026-08-24 the project owner issued the standing directive "accept
and fix all EDRs according to best recommended solutions", which accepted
EDR-0015 and EDR-0016 (their decided defaults are recorded in their ACCEPTANCE
sections) and accepted EDR-0011 as its recommended Option B — with the Option B
containment machinery itself deferred to the first non-DDE-native execution
substrate per gap-closure-record §6.3, while donor-search egress proceeds now
under EDR-0015. The accepted processing below covers EDR-0001..EDR-0016;
PROPOSED_OWNER_EDR_SLUGS is empty.


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
    {
        *(f"EDR-{number:04d}" for number in range(1, 17)),
    }
)

#: PROPOSED pre-images awaiting a human decision -- registered here so the
#: acceptance runner can reconcile them once accepted, but never proposed or
#: accepted by this script's run loop itself. Acceptance is always a human
#: act; registration only records that the markdown pre-image exists.
#:
#: Owner standing directives of 2026-08-24 ("close all queued decisions per
#: coordinator recommendations", then "accept and fix all EDRs according to
#: best recommended solutions") moved every registered slug into
#: ACCEPTED_OWNER_EDR_SLUGS above: EDR-0011 (Option B posture, machinery
#: deferred per §6.3; donor-search egress admitted now via EDR-0015),
#: EDR-0015 (decided defaults in its ACCEPTANCE section) and EDR-0016
#: (model/cost/rubric/retention defaults in its ACCEPTANCE section).
PROPOSED_OWNER_EDR_SLUGS: frozenset[str] = frozenset()


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
        "EDR-0011": {
            "context": (
                "Chapter 7.2's T2 tier promises that for any autonomous run "
                "the Execution Environment is the enforcement boundary: "
                "container/microVM isolation, workspace-only bind mount, "
                "non-privileged user, seccomp profile, resource limits, and "
                "an egress proxy with per-environment allowlists; revocation "
                "latency is 'bounded — revocation kills the egress allowlist "
                "entry and terminates the run'. The repository's one real "
                "substrate, LocalProcessBackend, is an honest plain-"
                "subprocess implementation: it filters the environment, "
                "registers live children for arm-time termination, and "
                "records everything it cannot enforce on IsolationReport."
                "gaps (NETWORK_ISOLATION_GAP, RESOURCE_LIMIT_GAP, "
                "AMBIENT_ENVIRONMENT_GAP) rather than claiming it. Two T2 "
                "surfaces stay genuinely open: (1) network egress — a "
                "spawned subprocess shares the host network stack, so a "
                "worker-controlled command can exfiltrate whatever secret "
                "material its containment left reachable; Chapter 7.2 rule 2 "
                "('all egress through the proxy ... direct IP egress is "
                "dropped') is recorded, not enforced, and the kill flag does "
                "not consult egress either; (2) container-scoped runs — when "
                "a run executes inside a container, DDE has no policy object "
                "declaring what isolation that container must carry, no way "
                "to enumerate or terminate processes inside it from the "
                "control plane's process registry, and no per-run network "
                "namespace; grandchildren and containers are disclosed "
                "residuals, not enforced boundaries."
            ),
            "alternatives": [
                "Option A — container policies first: declare per-container "
                "isolation policies (bind mounts, capabilities, network "
                "mode) checked at admission by a new docker backend, with "
                "egress gated by the daemon's network config — matches where "
                "the industry ecosystem already is, but on this codebase it "
                "makes the daemon the trust root, gives per-run revocation "
                "latency bounded by Docker's own tooling, and leaves every "
                "non-container run with no egress story at all.",
                "Option B — per-run namespace/proxy admission: every "
                "run-scoped spawn, local or containerized, is admitted "
                "through one egress boundary — DNS pinned to a DDE-owned "
                "resolver, HTTP(S) through a local allowlist proxy whose "
                "entries derive from the ExecutionPlan's capability set "
                "(Chapter 7.2 rule 2 verbatim); container backends "
                "additionally run each run in its own namespace so the "
                "boundary is structural, not advisory.",
            ],
            "decision": (
                "Accepted as Option B (per-run namespace/proxy admission), "
                "the recommended option, informed by the OpenSandbox donor "
                "study (docs/planning/opensandbox-graft-research-integration."
                "md Pattern 1): OpenSandbox independently shipped in "
                "production almost exactly what Option B sketches — an "
                "egress sidecar enforcing FQDN/wildcard allow-deny rules, "
                "DNS-pinned resolution plus nftables enforcement of resolved "
                "IPs/CIDRs, a runtime policy API (GET/PATCH /policy), "
                "platform-enforced always-allow/deny overlays, NET_ADMIN "
                "stripped from the main sandbox container so only the "
                "sidecar mutates network rules, and a credential vault that "
                "injects outbound credentials at the sidecar so real secrets "
                "never enter sandbox env/commands/files/logs — the strongest "
                "known implementation of Ch.7.2 rules 1-5. Wired now by this "
                "acceptance: nothing in code — acceptance authorizes the "
                "posture only; the concrete wired-now mutation surface is "
                "EDR-0015's broker-admitted control-plane egress (donor "
                "search), which migrates onto this boundary once it exists. "
                "Deferred to its trigger (gap-closure-record §6.3: the first "
                "non-DDE-native execution substrate landing): the egress "
                "proxy/resolver component itself, env-injection pointing "
                "LocalProcessBackend children at the proxy, "
                "IsolationReport.network_policy.enforced flipping true only "
                "when the proxy is actually in path, namespace-scoped kills, "
                "and the Ch.7.2 enforcement-mechanism-table amendment. When "
                "that trigger fires, the implementing mission MUST evaluate "
                "this reference implementation of the hard parts (nftables "
                "IP enforcement, NET_ADMIN stripping, runtime policy "
                "mutation, secrets-injected-at-boundary) before specifying "
                "DDE's own proxy/resolver, and must treat isolation-tier "
                "choice and egress mechanism as interacting axes (their own "
                "docs flag gVisor x nftables incompatibility); any divergence "
                "from the donor pattern must be justified in that memo, not "
                "silent. Windows keeps proxy-admission-only enforcement, "
                "disclosed per-platform on IsolationReport. Until then 'T2' "
                "remains a descriptor no local substrate may claim, and the "
                "NETWORK_ISOLATION_GAP disclosure stays truthful."
            ),
            "rationale": (
                "Option B gives one enforcement point for all substrates "
                "with revocation = drop the run's proxy entries plus the "
                "already-built process sweep, exactly matching Ch.7.2's "
                "bounded-revocation promise; Option A remains available as "
                "machinery for the future container backend rather than the "
                "trust root. The OpenSandbox study de-risks the two hard "
                "parts (structural-not-advisory enforcement and zero ambient "
                "credentials at the boundary) with production evidence, "
                "while its own documented limitations confirm deferral until "
                "a real substrate exists — patterns are adopted, packages "
                "are not (no Kubernetes/container substrate drags FastAPI/"
                "K8s machinery into adapters/** under Ch.9.6)."
            ),
            "consequences": [
                "If adopted: EDR-0015's broker-admitted control-plane egress "
                "is the one live egress surface today and migrates onto the "
                "shared boundary when the containment substrate lands; the "
                "future decision-memo obligation (evaluate OpenSandbox "
                "patterns 1-2 before specifying DDE's own component) binds "
                "whichever mission charters the substrate.",
                "The blueprint's Chapter 7.2 enforcement-mechanism table "
                "gains a Project Truth amendment naming the chosen mechanism "
                "only when the substrate mission lands — proposed there, not "
                "made here.",
                "If rejected instead, the phrase 'T2' must be retired from "
                "any descriptor that cannot meet Chapter 7.2 on this "
                "platform, and today's honest gap disclosures remain the "
                "whole story for worker runs.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0012": {
            "context": (
                "EDR-0010 (accepted 2026-08-23) added INTENTIONALLY_STOPPED "
                "as a first-class Chapter 12.3 recovery class with governed "
                "action acknowledge_stop (requires_human=True, no automatic "
                "retry, no new WorkerRun until the operator acknowledges). "
                "The implementation shipped three pieces: RecoveryService."
                "classify_run_stop_failure_class (engine/recovery/dispatch."
                'py) — described by its docstring as "the classification '
                'writer for the kill-flag refusal sites"; RecoveryService.'
                "assert_clear_to_retry — refuses any new WorkerRun for a "
                "task whose runs hold an ARMED durable stop record; and "
                "engine/recovery/matrix.py's KILL_FLAG_ACTIVE → "
                "INTENTIONALLY_STOPPED mapping. The gate review found both "
                "halves of exactly the failure mode .cursor/rules/mission-"
                "chapter-gate.mdc exists to catch: a docstring claiming "
                "wiring that does not exist at any production call site, "
                "and an adversarial path around a control. Finding A — "
                "classification gap (docstring overclaim): "
                "classify_run_stop_failure_class has ZERO production "
                'callers. The docstring says "the kill-flag checkout/'
                "admission sites ... consult this before writing the "
                "attempt's failure_class\" — they do not; they raise typed "
                "KILL_FLAG_ACTIVE without recording any attempt "
                "classification. The real mid-run failure writer is "
                "_drive_lifecycle's adapter-start handler in engine/workers/"
                "service.py, which catches every non-EFFECT_CONFLICT "
                "DdeError and records WORKER_CAPABILITY_DENIED. "
                "Consequence: a run killed mid-flight by an armed stop is "
                "durably classified WORKER_CAPABILITY_DENIED, which aliases "
                "to AUTHORIZATION_FAILURE in the matrix — the exact borrowed "
                "classification EDR-0010 retired — instead of the accepted "
                "INTENTIONALLY_STOPPED row; the accepted decision is not "
                "operational at the one site where a mid-run stop actually "
                "lands. Finding B — resume bypass (the adversarial "
                "question): WorkerManagerService.resume_run creates a brand-"
                "new WorkerRun on an IN_PROGRESS attempt with fresh "
                "capability leases, guarded only by assert_clear_to_start_"
                "attempt, completed-result refusal, effect-journal refusal "
                "and budget checks. It never calls assert_clear_to_retry nor "
                "consults _find_armed_stop. Exploit window: arm a stop on "
                "run R1 while its attempt is still IN_PROGRESS and R1 has "
                "not gone terminal — the operator's stop has not yet been "
                "observed by R1's synchronous lifecycle. resume_run passes "
                "the IN_PROGRESS check, fails R1 as replaced_by_resume_run, "
                "inserts a NEW run whose id is unknown to the kill-switch "
                "registry, grants it fresh leases, and drives its lifecycle: "
                "continuing the intentional stop without operator "
                "acknowledgement. This answers the gate rule's question "
                '"could a new WorkerRun bypass this control?" — currently '
                "yes. Chapter 12.4's law (\"only verified absence permits a "
                'new mutation") is enforced for invoke_run but not for the '
                "resume path."
            ),
            "alternatives": [
                "Keep the borrowed AUTHORIZATION_FAILURE mapping and record "
                "the semantic mismatch in a comment only — rejected once a "
                "human decision adopted the dedicated row.",
                "Add a distinct INTENTIONALLY_STOPPED classification raised "
                "from the existing KILL_FLAG_ACTIVE refusal sites and/or the "
                "durable ledger stop record, governed on its own terms — "
                "accepted.",
            ],
            "decision": (
                "Two wirings, minimal and at existing call sites; nothing "
                "new invented. (1) Classification wired where failure "
                "classes are durably written: the mid-run exception mapping "
                "in WorkerManagerService._drive_lifecycle consults the "
                "durable stop record when the caught DdeError carries "
                'error_code == "KILL_FLAG_ACTIVE" and records '
                "INTENTIONALLY_STOPPED instead of the borrowed "
                "WORKER_CAPABILITY_DENIED; every other code keeps today's "
                "mapping byte-identically (EFFECT_CONFLICT → "
                "SIDE_EFFECT_UNKNOWN, everything else "
                "WORKER_CAPABILITY_DENIED). The kill-flag refusal surfaces "
                "themselves (require_active checkout, broker credential "
                "admission) raise without writing attempt rows — their "
                "durable trail remains the enforcement events plus the ARMED "
                "ledger row, which the lifecycle writer now reads through "
                "the classifier. classify_run_stop_failure_class's docstring "
                "is corrected to name its real callers. (2) resume_run "
                "routed through the armed-stop guard: immediately after "
                "resolving the attempt (beside the existing recovery guards, "
                "before any prior-run replace, new run insert or lease "
                "grant), resume_run consults the same armed-stop semantics "
                "assert_clear_to_retry uses and refuses with typed "
                "KILL_FLAG_ACTIVE while any run of the task holds an ARMED "
                "stop record, recording observability consistent with the "
                "existing _record_resume_refusal pattern. After "
                "disarm_run_stop (the operator acknowledgement), resume "
                "proceeds exactly once as today. What stays deferred (named, "
                "not silently open): operator acknowledgement remains a "
                "service-layer act (CapabilityLeaseService.disarm_run_stop); "
                "no gateway command exposes it yet — exposing run.stop_"
                "acknowledge over the gateway is follow-on work behind its "
                'own scope decision. "Exactly one new guarded run after '
                'DISARM" is enforced as absence-of-ARMED plus per-failure-'
                "class occurrence counters in assert_clear_to_retry, not by "
                "a dedicated post-stop counter. The T2 egress/container "
                "residuals remain under the distinct proposed EDR-0011; "
                "nothing here touches them."
            ),
            "rationale": (
                "Closes the two MAJOR findings of the independent chapter-"
                "gate review of the DDE-024 recovery landing by implementing "
                "the already-accepted EDR-0010 at its real mutation sites: a "
                "mid-run intentional stop becomes durably queryable as its "
                "own class instead of a borrowed authorization-failure "
                "alias, and no new WorkerRun can be minted past an "
                "unacknowledged stop — turning the accepted decision from a "
                "docstring claim into enforcement at the production call "
                "sites where failure classes are written and runs are born."
            ),
            "consequences": [
                "If adopted: a mid-run intentional stop is durably queryable "
                "as INTENTIONALLY_STOPPED end-to-end (matrix dispatch, "
                "acknowledge_stop, requires_human), and the resume bypass "
                "closes — no new WorkerRun can be minted past an "
                "unacknowledged stop. EDR-0010 becomes true at its "
                "production mutation call sites rather than in docstrings.",
                "If rejected: the borrowed WORKER_CAPABILITY_DENIED "
                "classification stands for mid-flight kills and resume_run "
                "stays a documented bypass; both must then be recorded "
                "explicitly as accepted divergences from accepted EDR-0010, "
                "not left as docstring claims.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0013": {
            "context": (
                "The gate review verified every Chapter 11.6 and Chapter "
                "12.3/12.4 rule in scope wired at real production call sites "
                "(state machine single mutation site, worker/TTL/binding "
                "refusals, bidirectional READY gate, migration 0012 "
                "idempotence, RLS fail-closed predicates, armed-stop "
                "classification and resume guard). Four bounded residuals "
                "remain; they are recorded here with their smallest "
                "corrections rather than silently open. Finding 1 — "
                "verifier-to-service composition gap: ProductEnvironment"
                "Service.apply_migrations_forward(empty_verified=..., "
                "previous_verified=...) records caller-asserted booleans; no "
                "production code composes MigrationVerifier's real "
                "VerificationResult into it — today both are exercised only "
                "from tests with literals. The bidirectional MUST is still "
                "enforced at the real mark_ready mutation site against the "
                "recorded flags, so this is not a docstring-overclaim "
                "failure mode — but the flags themselves are trusted input "
                "until provisioning automation exists. Finding 2 — "
                "abandoned-event UoW split: teardown_expired commits the "
                "teardown transaction, then appends ProductEnvironment"
                "Abandoned in a separate uow=None unit of work. A crash "
                "between the two destroys the row but loses the monitored-"
                "metric event; the append should fold into the same unit of "
                "work as the teardown. Finding 3 — seed version hardcode: "
                "SeedRegistry.register writes version=1 despite the module "
                "docstring claiming supersession semantics; a second "
                "distinct-artifact registration of the same slug violates "
                "UNIQUE (tenant_id, project_id, slug, version) instead of "
                "creating v2; next version should be computed from existing "
                "rows. Related nit: the reproducibility hash covers the "
                "artifact pointer (artifact_ref), not payload bytes. Finding "
                "5 — principal trust disclosure: requested_by_origin on "
                "provision() is an unverified caller string; the worker-"
                "origin FORBIDDEN refusal is only as strong as principal "
                "authentication, which is globally deferred (disclosed at "
                "engine/truth/db.py, DDE-027/DDE-051); the dependency must "
                "be named in the service docstring so the refusal is never "
                "mistaken for an authentication control. (The review's "
                "Finding 4 — a dead _script_head helper left in engine/"
                "product_env/verification.py after the database-revision fix "
                "— is a plain cleanup, applied directly without an EDR.)"
            ),
            "alternatives": [
                "Leave the four residuals implicit, discoverable only by "
                "reading source code.",
                "Record each residual with its smallest correction and named "
                "timing so no future mission treats the current shape as a "
                "settled contract — retained.",
            ],
            "decision": (
                "Accepted as designed, four smallest corrections. (1) "
                "Composition deferred to first provisioning consumer, filed "
                "now: when DDE-043/044 build provisioning automation, the "
                "service must accept (or internally run) MigrationVerifier "
                "results instead of caller-asserted booleans — or require "
                "verifiable evidence references in the recorded halves; this "
                "EDR is the filing that obligation now, so no future mission "
                "can treat the boolean parameters as a settled contract. "
                "(2) Event atomicity fix at teardown_expired: same-unit-of-"
                "work event append, pinned by a test that observes both the "
                "row state and the outbox in one commit boundary. (3) Seed "
                "versioning fix: compute next version per (tenant_id, "
                "project_id, slug) inside the register transaction; "
                "reproducibility fingerprint unchanged (same identity "
                "inputs). (4) Docstring disclosure on ProductEnvironment"
                "Service.provision naming the authentication deferral. What "
                "stays deferred (named, not silently open): payload-bytes "
                "hashing for seed fingerprints (pointer-hash remains "
                "adequate while artifacts are repo-resident); none."
            ),
            "rationale": (
                "Carries the four MINOR residuals that kept the independent "
                "chapter-gate review of DDE-038 from being a clean PASS — "
                "none breaks a MUST/shall at a production call site today, "
                "but recording each with its owner and timing (2–4 "
                "immediate, 1 at DDE-043/044) keeps them from becoming "
                "silent divergences from Chapter 11.6's intent while letting "
                "DDE-038 close clean."
            ),
            "consequences": [
                "If adopted: DDE-038 closes clean; the four residuals have "
                "owners, timing (2-4 immediate, 1 at DDE-043/044), and "
                "smallest corrections.",
                "If rejected: each residual must be re-recorded as an "
                "accepted divergence from Chapter 11.6's intent or "
                "explicitly re-scoped, not left implicit.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0014": {
            "context": (
                "Chapter 4.3's approval table (docs/blueprint/REV_2_0.md, "
                '§4.3) requires graph approval "when any node is risk_class '
                '≥ high or blast_radius ≥ cross_module". DDE-040 encoded '
                "that threshold verbatim (engine/planning/registry.py "
                "promote_human_gate_required, {high, critical} / "
                "{cross_module, systemic}). The gate review proved — "
                "including with a live counterfactual probe — that the "
                "threshold function is correct but can never fire on real "
                "input: DraftNode (schemas/objects/plan_draft.json, engine/"
                "contracts/plan_draft.py) carries no risk_class/blast_radius "
                "fields; _materialise hardcodes every materialised Task to "
                'risk_class="low", blast_radius="local", requires_'
                "approval=False; and the gate result's only consumer is the "
                "PlanDraftPromoted event payload — activate_task_graph "
                "(engine/planning/service.py) performs no planning-mode/risk-"
                "aware check, and dispatch-side approval enforcement keys off "
                "task.requires_approval, which is hardcoded false on this "
                "path. So the model-assisted path has an inert computation "
                "where Chapter 4.3 requires an enforceable human boundary. It "
                "is safe-by-erasure today (drafts cannot express risk, and "
                "no dispatch surface consumes promoted graphs), which is why "
                "this is PASS-WITH-EDR rather than FAIL — but the moment "
                "drafts grow risk vocabulary, or promote_draft gains any "
                "gateway/dispatch exposure, the gate stays silently off "
                "unless this EDR's decision lands first. MINOR findings "
                "closed in the remediation commit (recorded here): mission_"
                "template.json blast_radius enum value system corrected to "
                "systemic (Chapter 4.2 and the Task contract say systemic; "
                "the old value validated a template whose instantiation "
                "later crashed Task construction); mission_template.json "
                "order 210 → 212 (210 collided with verification_run.json, "
                "silently coupling canonical table order to a future "
                "rename); five refusal branches gained direct negative tests "
                "(duplicate node keys, unknown template edge type, promote-"
                "time graph-not-APPROVED, null-result replay guard, fresh-"
                "key validate-on-non-PROPOSED)."
            ),
            "alternatives": [
                "Leave the inert gate as-is and rely on erasure-safety.",
                "Wire risk vocabulary into DraftNode and enforce the human "
                "gate where graphs become live — retained.",
            ],
            "decision": (
                "Accepted as designed, two wirings. (1) Risk vocabulary "
                "reaches the draft: DraftNode gains risk_class and "
                "blast_radius (with requires_approval derived from the same "
                "Ch.4.3 threshold); _materialise maps them onto materialised "
                "Task objects instead of hardcoded defaults, so a model-"
                "proposed high-risk node produces a high-risk Task. (2) The "
                "gate is enforced where graphs become live, not merely "
                "recorded: the APPROVED→ACTIVE boundary (the existing "
                "TaskGraph lifecycle writer) refuses activation of a graph "
                "whose promotion was human_gate_required=True until the "
                "corresponding human approval exists — keyed on durable "
                "state (planning mode + node risk on the graph/tasks), never "
                "on event payloads alone. Landing condition (hard "
                "precondition): items 1–2 MUST be landed before "
                "promote_draft is exposed through ANY gateway command "
                "surface, dispatch path, or automation consumer. Today's "
                "erasure-safety is the only thing that makes the current "
                "wiring honest."
            ),
            "rationale": (
                "Carries the one MAJOR finding of the independent chapter-"
                "gate review of DDE-040 (verdict PASS-WITH-EDR): the Ch.4.3 "
                "human-boundary threshold was true at the threshold function "
                "only, never on real input. Wiring risk vocabulary into the "
                "draft and enforcing the gate at the APPROVED→ACTIVE "
                "mutation site makes the chapter table enforceable end to "
                "end before any surface can reach the inert computation."
            ),
            "consequences": [
                "If adopted: model-assisted planning gains a genuinely "
                "enforceable human boundary at activation, and the Ch.4.3 "
                "table becomes true end to end rather than "
                "true-at-the-threshold-function-only.",
                "If rejected: promote_draft must remain unexposed "
                "indefinitely, or the divergence must be recorded as an "
                "explicit accepted decision — an inert gate behind an "
                "exposed surface is not an option.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0015": {
            "context": (
                "DDE-066 (Donor Discovery & Feature-Function Taxonomy) is "
                "the first Stage 5 mission that requires routine, recurring "
                "outbound network egress from the control plane: search "
                "fan-out over donor sources classified per Chapter 13.8. The "
                "hosts in scope are narrow and enumerable: GitHub API "
                "(api.github.com) for repos/tools/libraries search and "
                "metadata; shadcn-ecosystem registry endpoints for registry "
                "JSON of OPEN_REUSE components; commercial-template product "
                "sites' public catalogue/metadata endpoints (CONDITIONAL_"
                "REUSE, metadata only, never bundles or assets). Marketplace "
                "bundles are excluded entirely (REJECTED); no executing "
                "donor code, no ingesting code into the generator, no asset "
                "downloads on this surface. Today no production path can "
                "make these calls honestly: Chapter 7.2 rule 2 is recorded, "
                "not enforced; LocalProcessBackend discloses its egress gap "
                "(NETWORK_ISOLATION_GAP) rather than claiming enforcement; "
                "and EDR-0011's general T2 containment was deferred by human "
                "decision 2026-08-23 (gap-closure-record §6.3). Donor search "
                "does not fit that deferral: it is a control-plane "
                "capability with known hosts, human-auditable queries and "
                "no worker-controlled payload — and DDE-066 needs it before "
                "the general containment substrate exists."
            ),
            "alternatives": [
                "Wait for EDR-0011's general per-run proxy substrate before "
                "any egress — rejected: DDE-066 stays unimplementable for a "
                "bounded, enumerable control-plane surface that needs no "
                "per-run machinery.",
                "Ad-hoc direct HTTP calls from mission code with ambient "
                "environment credentials — rejected: unjournalled egress, "
                "long-lived secrets reachable by model-influenced code, no "
                "allowlist widening control.",
                "Broker-admitted, allowlisted, journal-recorded control-"
                "plane egress behind a side-effecting capability — accepted.",
            ],
            "decision": (
                "Accepted with decided defaults (amendable by future EDR): "
                "(1) Endpoint allowlist at host+path granularity, in-repo "
                "curated: api.github.com (search/repositories, "
                "search/code under authenticated scopes used only for "
                "metadata, /repos/* metadata — GitHub is the canonical "
                "source-of-record for donor repos/tools and per-result "
                "Ch.13.8 classification), github.com + raw.githubusercontent."
                "com (README/metadata reads only — licence evidence lives in "
                "the repo tree), registry.npmjs.org (package metadata for "
                "npm-class OPEN_REUSE donors), ui.shadcn.com registry "
                "endpoints plus shadcn-ecosystem blocks registries (OPEN_"
                "REUSE component JSON per Ch.13.8's amendment), and an "
                "explicitly enumerated commercial-template metadata list "
                "(Tailwind Plus / Cruip catalogue endpoints, CONDITIONAL_"
                "REUSE metadata-only) maintained as reviewed data in-repo. "
                "Marketplace hosts stay REJECTED and absent. Widening any "
                "entry is itself an EDR-class change. (2) Broker-issued "
                "short-lived credentials only: every outbound call "
                "authenticates with broker-minted short-lived tokens "
                "(GitHub tokens included); no long-lived secret ever passes "
                "to anything executing model-generated code and no ambient "
                "environment credential is reachable by the search path. "
                "(3) Placement: a control-plane service behind a new "
                "side-effecting capability with declared side_effect_class "
                "(Ch.9.3), NOT inside the T2 sandbox — donor search is a "
                "builder-side capability, not worker-run egress; EDR-0011's "
                "boundary continues to govern worker runs and this "
                "capability migrates onto it when it lands. (4) Quota "
                "ownership: per-mission budget rows in execution_plans' "
                "existing token_budget/dollar-denominated budget JSONB "
                "(Ch.16.4 overhead accounting), recorded in the capability "
                "registration; quota exhaustion is typed observable state, "
                "never a silent empty result. (5) Ch.12.4 journal per "
                "outbound query with idempotency key before retry; replaying "
                "a duplicated query asserts exactly one effect. (6) Fail-"
                "closed posture: classifier unreachable = empty results plus "
                "typed refusal; UNKNOWN sources default SOURCE_REFERENCE_ONLY/"
                "REJECTED and never silently upgrade (Ch.13.8 classify-"
                "before-use). (7) Injection screening precedes any model-"
                "visible surface (Ch.14.5 invariant 6). (8) Revocation: "
                "removing an allowlist entry stops future queries at the "
                "admission gate; already-journal-recorded effects remain "
                "queryable audit history. Relationship to EDR-0011: this "
                "EDR is the admission policy for one named surface; EDR-0011 "
                "(accepted same day, Option B deferred to the substrate "
                "trigger) remains the runtime-containment law for worker-run "
                "egress; each cites the other, nothing here widens the T2 "
                "boundary."
            ),
            "rationale": (
                "Host+path granularity keeps the allowlist auditable without "
                "enumerating every CDN edge host; brokered short-lived "
                "credentials keep AGENTS.md's forbidden-list invariant true "
                "by construction; builder-side placement matches what the "
                "surface actually is (control-plane search fan-out, not "
                "worker containment) and lets DDE-066 start ahead of the "
                "deferred general substrate; reusing execution_plans budget "
                "JSONB avoids inventing a second budget ledger (no second "
                "source of truth for mutable state)."
            ),
            "consequences": [
                "DDE-066 can start implementation after acceptance, with "
                "every query durable, budgeted, screened and auditable from "
                "day one; Ch.7.2/13.8 gain an admitted-surface record "
                "through the normal chapter-amendment path (proposed there, "
                "not made here).",
                "The allowlist file becomes reviewed, hash-pinned policy "
                "data: changes are code review + EDR-class justification, "
                "not operator edits.",
                "When EDR-0011 Option B lands, this capability migrates "
                "onto the shared egress boundary; until then it is the only "
                "admitted outbound surface in the system.",
            ],
            "affected_requirement_slugs": [],
        },
        "EDR-0016": {
            "context": (
                "DDE-068 (Visual Verification & Critique Loop) needs a "
                "multimodal-model capability no existing repo toolchain "
                "provides: screenshot -> rubric critique scored against "
                "playbook §8 scorecards -> bounded revise <=3 cycles -> "
                "residuals escalate to human. The Phase-B render harness is "
                "already landed (EDR-0008's Playwright job in dde-studio."
                "yml), so the missing piece is exactly the critic dependency "
                "and its budget envelope. AGENTS.md admits a new dependency/"
                "model call only with licence, maintenance signal, cost "
                "ownership and why the existing toolchain is insufficient — "
                "static lints (DD201-DD206) and string fingerprints cannot "
                "judge composition, hierarchy or distinctiveness of rendered "
                "pixels. Model credentials must follow the same brokered "
                "path as every other capability; EDR-0011's general "
                "containment remains deferred and nothing here widens "
                "worker-run egress — critique calls are control-plane "
                "side-effecting steps like donor-search queries under "
                "EDR-0015."
            ),
            "alternatives": [
                "Frontier closed multimodal API model as primary critic — "
                "strongest rubric fidelity but highest per-call cost.",
                "Low-cost high-throughput multimodal tier as primary "
                "critic, escalating to frontier only when residuals persist "
                "— accepted: first-pass rubric scoring is mechanical "
                "judgement, not taste.",
                "Self-hosted open-weights VLM — no per-call vendor cost but "
                "a GPU/ops burden DDE cannot carry at this stage; revisit "
                "behind its own Ch.9.6 admission decision.",
            ],
            "decision": (
                "Accepted with decided defaults (amendable by future EDR): "
                "(1) Model class: one low-cost, high-throughput multimodal "
                "model as the primary critic, selected by name at "
                "implementation time from whatever providers are then "
                "declared — routed through the EXISTING provider-agnostic "
                "path (Appendix A 'vision and visual evidence' profile; "
                "RouterService.model_mode='fixed' already supports pinning "
                "a declared model id/provider). No new credential plumbing, "
                "no new provider SDK outside adapters/**; the critic rides "
                "the same broker/adapter machinery as every other harness. "
                "(2) Cost ceiling, enforced against Ch.16.4 overhead "
                "accounting: $0.05 per critique cycle (one screenshot + "
                "rubric scoring + verdict) and $10 per product per month "
                "across all critique cycles; crossing either is typed "
                "BUDGET_EXCEEDED state routed to the existing pause-for-"
                "human path, never silently absorbed. Numbers are initial "
                "targets, retunable by policy version with measured data. "
                "(3) Rubric storage: extend the existing verification row "
                "structure — rubric text versioned under schemas/design/ "
                "alongside tokens.json (Ch.3.1 drift-gate discipline), with "
                "the compiled prompt pinning rubric + playbook versions on "
                "each VerificationRun/Evidence linkage so verdicts are "
                "reproducible against named inputs; no new table while the "
                "verification_runs/evidence structure can carry it, and a "
                "dedicated durable table only if query needs outgrow it "
                "(that widening would be its own schema decision). "
                "(4) Retention: screenshots and critiques are rank-9 "
                "evidence artifacts following existing law — WORM object-"
                "lock >= project audit retention (Ch.17.5), evidence-linked "
                "artifacts never detached while referenced (Ch.3.7), never "
                "auto-deleted while the screen they judged remains merged; "
                "raw screenshots may age to cold storage ahead of verdict "
                "rows per the artifact lifecycle policy, never deleted "
                "inside the retention window. (5) Bounded revise <=3 cycles: "
                "each cycle consumes exactly one stored critique artifact; "
                ">3 cycles blocks auto-progression and escalates residuals "
                "to explicit human approval through the approvals surface "
                "(prototype_pixel_signoff must be added through the "
                "ordinary contract path or an existing type designated — "
                "GUI-spec open item D2). (6) Silhouette generic-corpus "
                "sourcing: option (c), self-generated generic layouts "
                "seeded from playbook §1.1's nevers catalog — fully "
                "licence-clean with trivially internal provenance; godly/"
                "land-book-class galleries stay SOURCE_REFERENCE_ONLY with "
                "no APIs and no scraping (playbook §10.5), usable as human "
                "curation inspiration only. Rank-9 forever: critiques inform "
                "humans and the bounded loop, never modify rank <=3 "
                "artifacts, never auto-approve themselves, never widen "
                "autonomy."
            ),
            "rationale": (
                "A cheap high-throughput tier fits what the loop actually "
                "does (mechanical rubric scoring repeated across revise "
                "cycles) and keeps the $10/product/month envelope honest, "
                "with frontier escalation available later if measured "
                "verdict quality demands it; routing through the existing "
                "provider-agnostic fixed-model path means zero new "
                "credential surface; extending schemas/design plus the "
                "verification-row linkage respects the single-source-of-"
                "truth and generated-contract disciplines instead of adding "
                "a parallel store."
            ),
            "consequences": [
                "DDE-068 starts from an admitted, budget-bounded critic with "
                "a reproducible rubric lineage; every critique is durable "
                "rank-9 evidence bound to its VerificationRun.",
                "The silhouette gate gets a licence-clean corpus answer "
                "before the gate exists; gallery-sourcing questions stay "
                "closed (SOURCE_REFERENCE_ONLY, no APIs).",
                "If rejected instead, Definition-of-Polished gates that "
                "depend on VLM critique stay named deferrals and DD201-DD206 "
                "+ honesty tests remain the merge bar.",
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
