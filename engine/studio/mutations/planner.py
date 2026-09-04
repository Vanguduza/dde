"""DDE-069 mutation planner -- one write path for every affordance.

Inspector edits, drag/drop, chat instructions, `/design` refinements,
template blends, source imports, agent packets and keyboard operations
all arrive here as a `MutationRequest` and leave as a `MutationPlan`. That
is the point: a rule enforced in one affordance and forgotten in another
is not a rule, so lock checks, staleness checks, scope checks and token
discipline live here once rather than at each entry point.

Planning is pure with respect to the database -- it takes the state it
needs as arguments and returns a decision. The executor persists it. That
split is what lets the refusal rules be swept in unit tests without
standing up Postgres, and it is why a refusal is a *recorded* row rather
than an exception that vanishes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.frontend_lock import FrontendLock
from engine.contracts.frontend_mutation import Preconditions
from engine.studio.candidates.lifecycle import CandidateState, is_mutable
from engine.studio.locks.resolution import covers_key, effective_lock_hash
from engine.studio.locks.resolution import evaluate as evaluate_locks
from engine.studio.pxg.service import PxgGraph
from engine.studio.tokens_catalog import STYLE_PROPERTIES, allowed_values

#: Operations that write a design-token-governed value. These are checked
#: against the token catalogue so a richer V2 inspector cannot bypass the
#: DDE-067 server-side token discipline by choosing a different operation.
TOKEN_GOVERNED: Final[frozenset[str]] = frozenset({"RESTYLE", "SET_PROPERTY"})

VALID_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        "ADD",
        "REMOVE",
        "MOVE",
        "REORDER",
        "REPLACE",
        "RESTYLE",
        "SET_PROPERTY",
        "SET_BEHAVIOUR",
        "SET_RESPONSIVE",
    }
)

VALID_ORIGINS: Final[frozenset[str]] = frozenset(
    {
        "INSPECTOR",
        "CHAT",
        "DIRECT_MANIPULATION",
        "DESIGN_PROVIDER",
        "TEMPLATE",
        "SOURCE_IMPORT",
        "AGENT",
        "KEYBOARD",
        "REPAIR",
    }
)


@dataclass(frozen=True)
class MutationRequest:
    """What a caller wants to change, before any rule has been applied."""

    operation: str
    target_key: str
    origin: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PlannedMutation:
    request: MutationRequest
    inverse: dict[str, object]
    preconditions: Preconditions


@dataclass(frozen=True)
class RefusedMutation:
    request: MutationRequest
    code: str
    detail: str
    preconditions: Preconditions


@dataclass(frozen=True)
class MutationPlan:
    """The planner's whole answer.

    A plan carrying refusals is still a plan: the refusals are persisted
    as REFUSED rows so "the studio silently did nothing" is never the
    user-visible outcome.
    """

    planned: tuple[PlannedMutation, ...]
    refused: tuple[RefusedMutation, ...]

    @property
    def is_applicable(self) -> bool:
        return bool(self.planned) and not self.refused


def plan(
    requests: Sequence[MutationRequest],
    *,
    candidate: FrontendCandidate,
    graph: PxgGraph,
    locks: Sequence[FrontendLock],
    contract_version: int | None = None,
    design_system_hash: str | None = None,
    accepted_pxg_revision: int | None = None,
) -> MutationPlan:
    """Decide each request against locks, scope, staleness and tokens.

    The whole batch is planned even when one request is refused, so a
    user editing several properties sees every problem at once rather
    than one per round trip.
    """
    lock_hash = effective_lock_hash(locks)
    accepted_revision = (
        graph.revision if accepted_pxg_revision is None else accepted_pxg_revision
    )
    preconditions = Preconditions(
        pxg_revision=accepted_revision,
        candidate_base_revision=candidate.base_pxg_revision,
        frontend_contract_version=contract_version,
        design_system_hash=design_system_hash,
        effective_lock_hash=lock_hash,
    )

    planned: list[PlannedMutation] = []
    refused: list[RefusedMutation] = []

    state = CandidateState(candidate.state)
    for request in requests:
        refusal = _refusal_for(
            request,
            candidate=candidate,
            state=state,
            graph=graph,
            locks=locks,
            accepted_pxg_revision=accepted_revision,
        )
        if refusal is not None:
            code, detail = refusal
            refused.append(
                RefusedMutation(
                    request=request,
                    code=code,
                    detail=detail,
                    preconditions=preconditions,
                )
            )
            continue
        planned.append(
            PlannedMutation(
                request=request,
                inverse=_inverse_for(request, graph=graph),
                preconditions=preconditions,
            )
        )
    return MutationPlan(planned=tuple(planned), refused=tuple(refused))


def _refusal_for(
    request: MutationRequest,
    *,
    candidate: FrontendCandidate,
    state: CandidateState,
    graph: PxgGraph,
    locks: Sequence[FrontendLock],
    accepted_pxg_revision: int,
) -> tuple[str, str] | None:
    if request.operation not in VALID_OPERATIONS:
        return (
            "MUTATION_INVALID",
            f"unknown operation {request.operation!r}",
        )
    if request.origin not in VALID_ORIGINS:
        return ("MUTATION_INVALID", f"unknown origin {request.origin!r}")
    if not is_mutable(state):
        return (
            "MUTATION_INVALID",
            f"candidate is {state.value} and does not accept mutations",
        )

    # Staleness is about the accepted base, not the candidate's effective
    # revision. Candidate-local mutations advance the effective projection
    # without advancing accepted PXG, so comparing base_revision to
    # graph.revision would falsely mark every edited candidate stale.
    if candidate.base_pxg_revision < accepted_pxg_revision:
        return (
            "STALE_CANDIDATE",
            "accepted PXG advanced from revision "
            f"{candidate.base_pxg_revision} to {accepted_pxg_revision}; "
            "rebase or create a new candidate before editing",
        )

    # Scope: a candidate may only touch keys it declared. Without this a
    # candidate created to change a hero could quietly rewrite navigation.
    if not any(covers_key(scope, request.target_key) for scope in candidate.scope_keys):
        return (
            "SCOPE_DENIED",
            f"{request.target_key} is outside this candidate's declared "
            f"scope {sorted(candidate.scope_keys)}",
        )

    # An operation other than ADD needs the node to exist.
    if request.operation != "ADD" and graph.node_by_key(request.target_key) is None:
        return (
            "MUTATION_INVALID",
            f"no PXG node at {request.target_key}",
        )

    decision = evaluate_locks(
        locks, target_key=request.target_key, operation=request.operation
    )
    if not decision.allowed:
        return ("LOCK_DENIED", decision.reason or "locked")

    if request.operation in TOKEN_GOVERNED:
        token_refusal = _token_refusal(request)
        if token_refusal is not None:
            return token_refusal
    return None


def _token_refusal(request: MutationRequest) -> tuple[str, str] | None:
    """Preserve the DDE-067 server-side token discipline.

    A property that the token catalogue governs may only receive a
    catalogue alias. A freehand literal is refused here, before anything
    reaches a workspace, so the V2 inspector cannot become a hole in a
    rule the DDE-067 canvas already enforces.
    """
    prop = request.payload.get("property")
    value = request.payload.get("value")
    if not isinstance(prop, str):
        return ("MUTATION_INVALID", "payload.property must be a string")
    if prop not in STYLE_PROPERTIES:
        return None
    if not isinstance(value, str):
        return ("MUTATION_INVALID", "payload.value must be a string")
    if value not in allowed_values(prop):
        return (
            "OFF_TOKEN_REFUSED",
            f"{value!r} is not a token-sheet alias for {prop}; freehand "
            "literals are unauthorable",
        )
    return None


def _inverse_for(request: MutationRequest, *, graph: PxgGraph) -> dict[str, object]:
    """Record what undoing this needs, observed before it is applied.

    After application the prior value is gone, so an inverse computed
    later would be a guess.
    """
    node = graph.node_by_key(request.target_key)
    if request.operation == "ADD":
        return {"operation": "REMOVE", "target_key": request.target_key}
    if request.operation == "REMOVE":
        return {
            "operation": "ADD",
            "target_key": request.target_key,
            "node": node.model_dump(mode="json") if node else None,
        }
    if request.operation in ("MOVE", "REORDER"):
        return {
            "operation": request.operation,
            "target_key": request.target_key,
            "parent_key": node.parent_key if node else None,
        }
    prop = request.payload.get("property")
    prior = None
    if node is not None and isinstance(prop, str):
        prior = node.attributes.get(prop)
    return {
        "operation": request.operation,
        "target_key": request.target_key,
        "property": prop,
        "value": prior,
    }
