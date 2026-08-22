"""Idempotent acceptance of the six human-approved EDRs into Project Truth.

The project owner explicitly accepted EDR-0001..EDR-0006 (the markdown
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
    f"EDR-{number:04d}" for number in range(1, 7)
)


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
