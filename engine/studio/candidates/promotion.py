"""DDE-069 candidate promotion gate.

Promotion is a governed state transition, not a button. This service
aggregates every condition that must hold and returns a typed decision;
there is no path that reaches PROMOTED without passing through it,
because the lifecycle table has no transition from PROMOTABLE to PROMOTED
-- only PROMOTABLE to PROMOTING, and PROMOTING is here.

Each gate is evaluated and reported even when an earlier one already
failed, so a user sees everything blocking them rather than fixing one
condition per round trip.

Promotion is also the *only* writer of accepted PXG nodes from candidate
work. Editing a candidate records mutations and nothing else
(`engine.studio.mutations`), so the accepted graph moves exactly once,
here, after every gate has passed.

The visual gate deliberately consults DDE-068's own evidence rather than
re-deriving a verdict: `VerificationRun` rows carry the outcome that
mission's runner produced, and this gate refuses whenever a required
check is absent, errored or failed. Unavailable verification is never
read as approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.verification_run import VerificationRun
from engine.core.errors import DdeError
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.service import CandidateService
from engine.studio.coverage.service import CoverageService
from engine.studio.locks.resolution import covers_key
from engine.studio.locks.service import LockService
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.pxg.service import NodeInput, PxgService
from engine.studio.source.service import SourceIntelligenceService

#: Evidence kinds whose absence blocks promotion for a frontend
#: candidate. Kept in step with `screen_acceptance_defaults.json`'s
#: mandatory set; a screen bound by that policy is gated on exactly the
#: checks it was bound to.
REQUIRED_VISUAL_KINDS: frozenset[str] = frozenset({"silhouette", "visual_critique"})


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str

    @property
    def blocking(self) -> bool:
        return not self.passed


@dataclass(frozen=True)
class PromotionDecision:
    """Every gate's answer, not just the first failure."""

    candidate_id: UUID
    allowed: bool
    gates: tuple[GateResult, ...]

    @property
    def blockers(self) -> tuple[GateResult, ...]:
        return tuple(gate for gate in self.gates if gate.blocking)

    @property
    def reason(self) -> str | None:
        if self.allowed:
            return None
        return "; ".join(f"{gate.name}: {gate.detail}" for gate in self.blockers)


class PromotionService:
    """Evaluates and executes the frontend promotion gate."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        candidates: CandidateService | None = None,
        pxg: PxgService | None = None,
        locks: LockService | None = None,
        coverage: CoverageService | None = None,
        mutations: MutationExecutor | None = None,
        sources: SourceIntelligenceService | None = None,
    ) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)
        self._candidates = candidates or CandidateService(engine, pxg=self._pxg)
        self._locks = locks or LockService(engine)
        self._coverage = coverage or CoverageService(engine, pxg=self._pxg)
        self._mutations = mutations or MutationExecutor(
            engine, pxg=self._pxg, locks=self._locks, candidates=self._candidates
        )
        self._sources = sources or SourceIntelligenceService(engine)

    async def evaluate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        verification_runs: tuple[VerificationRun, ...] = (),
    ) -> PromotionDecision:
        view = await self._candidates.view(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        candidate = view.candidate
        gates: list[GateResult] = [
            _state_gate(candidate),
            _staleness_gate(view.stale, candidate, view.current_pxg_revision),
            await self._lock_gate(
                tenant_id=tenant_id, project_id=project_id, candidate=candidate
            ),
            await self._mutation_gate(
                tenant_id=tenant_id, project_id=project_id, candidate=candidate
            ),
            _visual_gate(verification_runs),
            await self._source_gate(
                tenant_id=tenant_id, project_id=project_id, candidate=candidate
            ),
        ]
        return PromotionDecision(
            candidate_id=candidate_id,
            allowed=all(gate.passed for gate in gates),
            gates=tuple(gates),
        )

    async def promote(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        verification_runs: tuple[VerificationRun, ...] = (),
    ) -> FrontendCandidate:
        """Promote, or refuse with every blocking reason attached."""
        decision = await self.evaluate(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            verification_runs=verification_runs,
        )
        if not decision.allowed:
            raise DdeError(
                "POLICY_DENIED",
                "promotion denied",
                retryable=False,
                details={
                    "candidate_id": str(candidate_id),
                    "blockers": [
                        {"gate": gate.name, "detail": gate.detail}
                        for gate in decision.blockers
                    ],
                },
            )
        await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            target=CandidateState.PROMOTING,
            detail="promotion gate passed",
        )
        try:
            accepted_revision = await self._merge_into_accepted(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
            )
        except DdeError as exc:
            # A merge that cannot land must not leave the candidate stuck
            # in PROMOTING; it goes to FAILED with the reason attached.
            await self._candidates.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                target=CandidateState.FAILED,
                detail=f"merge into accepted failed: {exc}",
            )
            raise
        return await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            target=CandidateState.PROMOTED,
            detail=(
                f"promoted at {datetime.now(UTC).isoformat()}; accepted PXG "
                f"revision {accepted_revision}"
            ),
        )

    async def _merge_into_accepted(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> int:
        """Write the candidate's effective graph into the accepted one.

        The whole merge is one PXG revision, so no reader ever observes a
        half-promoted project.
        """
        accepted = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        effective = await self._mutations.candidate_graph(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        accepted_keys = {node.pxg_key for node in accepted.nodes}
        effective_keys = {node.pxg_key for node in effective.nodes}

        nodes = [
            NodeInput(
                pxg_key=node.pxg_key,
                node_kind=node.node_kind,
                title=node.title,
                parent_key=node.parent_key,
                source_refs=tuple(node.source_refs),
                attributes=dict(node.attributes),
                provenance=dict(node.provenance),
            )
            for node in effective.nodes
        ]
        removals = sorted(accepted_keys - effective_keys)
        return await self._pxg.apply(
            tenant_id=tenant_id,
            project_id=project_id,
            nodes=nodes,
            remove_node_keys=removals,
        )

    async def _source_gate(
        self, *, tenant_id: UUID, project_id: UUID, candidate: FrontendCandidate
    ) -> GateResult:
        ready, detail = await self._sources.promotion_readiness(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate.candidate_id,
            candidate_origin=candidate.origin,
        )
        return GateResult("source_provenance", ready, detail)

    async def _lock_gate(
        self, *, tenant_id: UUID, project_id: UUID, candidate: FrontendCandidate
    ) -> GateResult:
        """A lock created after the candidate started must be honoured.

        Otherwise locking a region would not stop work already in flight
        from landing on it, which is the case locks exist for.
        """
        locks = await self._locks.active(tenant_id=tenant_id, project_id=project_id)
        conflicting = [
            lock
            for lock in locks
            for scope in candidate.scope_keys
            if covers_key(lock.scope_key, scope) or covers_key(scope, lock.scope_key)
        ]
        if conflicting:
            return GateResult(
                name="locks",
                passed=False,
                detail="candidate scope intersects active locks: "
                + ", ".join(
                    f"{lock.lock_kind}@{lock.scope_key}" for lock in conflicting
                ),
            )
        return GateResult("locks", True, "no active lock intersects this scope")

    async def _mutation_gate(
        self, *, tenant_id: UUID, project_id: UUID, candidate: FrontendCandidate
    ) -> GateResult:
        history = await self._mutations.history(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate.candidate_id,
        )
        applied = [item for item in history if item.status == "APPLIED"]
        if not applied:
            return GateResult(
                name="mutations",
                passed=False,
                detail="candidate has no applied mutations; there is nothing "
                "to promote",
            )
        return GateResult("mutations", True, f"{len(applied)} applied mutation(s)")


def _state_gate(candidate: FrontendCandidate) -> GateResult:
    state = CandidateState(candidate.state)
    if state is CandidateState.PROMOTABLE:
        return GateResult("state", True, "candidate is PROMOTABLE")
    return GateResult(
        name="state",
        passed=False,
        detail=f"candidate is {state.value}, not PROMOTABLE",
    )


def _staleness_gate(
    stale: bool, candidate: FrontendCandidate, current_revision: int
) -> GateResult:
    if not stale:
        return GateResult(
            "staleness", True, f"based on current PXG revision {current_revision}"
        )
    return GateResult(
        name="staleness",
        passed=False,
        detail=(
            f"candidate is based on PXG revision "
            f"{candidate.base_pxg_revision}; the project is at "
            f"{current_revision}. Rebase and revalidate before promoting."
        ),
    )


def _visual_gate(runs: tuple[VerificationRun, ...]) -> GateResult:
    """Consume DDE-068's evidence. Absent evidence is never approval.

    A missing required kind, an errored run and a failed check are three
    different problems and are reported as such, but all three block.
    """
    if not runs:
        return GateResult(
            name="visual_verification",
            passed=False,
            detail=(
                "no verification run is attached; unavailable verification "
                "is not approval"
            ),
        )
    observed: dict[str, str] = {}
    for run in runs:
        for check in run.check_results:
            # Last run wins for a kind: a re-verification supersedes an
            # earlier attempt rather than being averaged with it.
            observed[check.kind] = check.status

    missing = sorted(REQUIRED_VISUAL_KINDS - set(observed))
    if missing:
        return GateResult(
            name="visual_verification",
            passed=False,
            detail=f"required check(s) never ran: {', '.join(missing)}",
        )
    not_passed = sorted(
        kind for kind in REQUIRED_VISUAL_KINDS if observed.get(kind) != "PASSED"
    )
    if not_passed:
        return GateResult(
            name="visual_verification",
            passed=False,
            detail="; ".join(f"{kind} is {observed[kind]}" for kind in not_passed),
        )
    return GateResult(
        "visual_verification",
        True,
        f"all required visual checks passed: {sorted(REQUIRED_VISUAL_KINDS)}",
    )
