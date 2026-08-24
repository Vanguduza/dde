"""Chapter 4.3 planning registries — the production mutation site.

Owner of `mission_templates` and `plan_drafts` rows (Chapter 3.8: the
planner owns decomposition). Public mutations, each the single call site
for its rules:

- `register_template()` — Chapter 4.3: mission templates are "first-class
  registry objects with their own version and conformance tests".
  Registration is idempotent on `template_version` (Chapter 3.10:
  immutable definition, a material change is a NEW version, never an
  overwrite) and refuses a template whose structural shape could never
  validate as a graph (dangling edge endpoints, duplicate keys, cycles,
  empty node set) — a template that cannot decompose must not enter the
  registry.
- `retire_template()` — the one template lifecycle mutation,
  ACTIVE -> RETIRED terminal.
- `submit_draft()` — records one model-assisted proposal as UNTRUSTED
  input in PROPOSED state. Nothing here executes; provenance (origin,
  adapter_ref, policy version) is recorded on the row itself.
- `validate_draft()` — runs the SAME deterministic structural validator
  the Task Planner contract enforces over template graphs
  (`engine.planning.validate.validate_graph`) after materialising the
  draft's node_keys into Task/TaskGraphEdge objects scoped to the
  mission. Chapter 4.3: "`validate`, `schedule` and the write-scope
  allocation inside `plan` are deterministic code... A proposed graph is
  not usable until `validate` passes". Typed refusals are recorded on
  the row; a REJECTED draft is durable evidence of what the model
  proposed and why the planner refused it.
- `promote_draft()` — turns a VALIDATED draft into a real TaskGraph by
  composing `MissionService.create_task_graph` with
  `planning_mode="model_assisted"`: the draft's nodes pass through the
  ordinary DRAFT -> VALIDATING -> APPROVED|REJECTED lifecycle and land
  as real Task rows only if APPROVED. A REJECTED or still-PROPOSED draft
  can NEVER mint a graph — this call site is where "a model can never
  emit an executable graph directly" is enforced. The draft row records
  `promoted_graph_id`, the durable provenance link from graph back to
  the proposal that produced it.

Idempotency (Chapter 12.5): every mutating entry point is guarded by the
existing CommandLedger on the caller-supplied idempotency key; a repeated
invocation with the same key returns the first call's stored result
instead of re-executing.

Human gate (Chapter 4.3 planning-mode table): a `model_assisted` graph
whose nodes carry `risk_class >= high` or `blast_radius >= cross_module`
requires a Chapter 13 Approval before activation. `promote_draft`
computes the requirement from the validated nodes via
`promote_human_gate_required` and records it on the promotion event; the
gate itself sits between APPROVED and ACTIVE, where every other
activation path already sits.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.mission import Mission
from engine.contracts.mission_template import (
    MissionTemplate,
    TemplateEdge,
    TemplateNode,
)
from engine.contracts.plan_draft import DraftEdge, DraftNode, PlanDraft, Refusal
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.planning.registry_hashing import (
    draft_provenance_key,
    template_version_hash,
)
from engine.planning.registry_repository import PlanningRegistryRepository
from engine.planning.registry_states import (
    assert_draft_transition,
    assert_template_transition,
)
from engine.planning.validate import validate_graph
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: The closed edge-type vocabulary a template/draft edge may carry --
#: mirrored from the generated contracts rather than introspected.
_EDGE_TYPE_VOCABULARY: frozenset[str] = frozenset(
    {
        "depends_on",
        "produces_contract_for",
        "verifies",
        "repairs",
        "blocks_on_decision",
    }
)

#: Policy version stamped on drafts validated by this service. Bumped
#: when the refusal vocabulary changes shape, so stored rows stay
#: explainable by the code that wrote them.
DRAFT_VALIDATOR_POLICY_VERSION = "draft-validator-v1"

#: Chapter 4.3 human-gate thresholds for model_assisted graphs.
HUMAN_GATE_RISK_CLASSES: frozenset[str] = frozenset({"high", "critical"})
HUMAN_GATE_BLAST_RADII: frozenset[str] = frozenset({"cross_module", "systemic"})


class TemplateShapeError(DdeError):
    """Typed refusal for a template whose decomposition could never
    validate as a task graph (unknown edge endpoints, no nodes)."""


class DraftNotPromotableError(DdeError):
    """Typed refusal for promoting a draft the deterministic validator
    did not leave in VALIDATED state."""


def _check_template_shape(nodes: list[TemplateNode], edges: list[TemplateEdge]) -> None:
    """Conformance pre-check at registration time (Chapter 4.3: templates
    carry conformance tests -- this is the structural half at the
    mutation site; the test suite pins the behavioural half)."""
    if not nodes:
        raise TemplateShapeError(
            "DECOMPOSITION_REQUIRED",
            "A mission template must decompose to at least one node",
        )
    keys = {node.node_key for node in nodes}
    if len(keys) != len(nodes):
        raise TemplateShapeError(
            "GRAPH_INVALID",
            "Mission template node keys must be unique",
        )
    for edge in edges:
        unknown = [
            key for key in (edge.from_node_key, edge.to_node_key) if key not in keys
        ]
        if unknown:
            raise TemplateShapeError(
                "GRAPH_INVALID",
                f"Template edge references unknown node(s): {unknown}",
                details={"unknown": unknown},
            )
        if edge.edge_type not in _EDGE_TYPE_VOCABULARY:
            raise TemplateShapeError(
                "GRAPH_INVALID",
                f"Unknown template edge type {edge.edge_type}",
            )
    # A cycle inside a registered template guarantees every instantiation
    # is rejected downstream; refuse it at registration instead.
    cycle_nodes = [_template_node_to_task_like(node) for node in nodes]
    cycle_edges = [_template_edge_to_edge_like(edge) for edge in edges]
    if has_cycle(cycle_nodes, cycle_edges):
        raise TemplateShapeError(
            "GRAPH_INVALID",
            "Mission template decomposition contains a dependency cycle",
        )


def _template_node_to_task_like(node: TemplateNode) -> _TaskLike:
    return {
        "task_id": node.node_key,
        "title": node.title,
        "intent": node.intent,
        "task_class": node.task_class,
        "requirement_refs": ["REQ"],
        "feature_refs": [],
        "success_criteria": list(node.success_criteria),
        "expected_write_scope": list(node.write_scope),
        "expected_read_scope": list(node.read_scope or []),
        "blast_radius": node.blast_radius or "local",
        "risk_class": node.risk_class or "low",
        "estimated_effort": node.estimated_effort,
        "autonomy_ceiling": 1,
        "requires_approval": False,
        "parent_task_id": None,
        "verification_profile_ref": "unit",
    }


def _template_edge_to_edge_like(edge: TemplateEdge) -> _EdgeLike:
    return {
        "from_task_id": edge.from_node_key,
        "to_task_id": edge.to_node_key,
        "edge_type": edge.edge_type,
        "contract_ref": edge.contract_ref,
    }


_TaskLike = dict[str, object]
_EdgeLike = dict[str, object]


def has_cycle(tasks: list[_TaskLike], edges: list[_EdgeLike]) -> bool:
    """Kahn's algorithm over the dependency edges of shapeless dicts --
    the registry checks templates before they ever become contracts, so
    it cannot depend on `engine.contracts.task` instances. Dependency
    semantics mirror `engine.planning.hashing.DEPENDENCY_EDGES`."""
    dependency_edges = frozenset(
        {"depends_on", "produces_contract_for", "blocks_on_decision", "repairs"}
    )
    ids = sorted(str(task["task_id"]) for task in tasks)
    incoming: dict[str, int] = {task_id: 0 for task_id in ids}
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        if str(edge["edge_type"]) not in dependency_edges:
            continue
        source = str(edge["from_task_id"])
        dest = str(edge["to_task_id"])
        outgoing.setdefault(source, []).append(dest)
        incoming[dest] = incoming.get(dest, 0) + 1
        incoming.setdefault(source, incoming.get(source, 0))
    ready = [task_id for task_id, count in incoming.items() if count == 0]
    seen = 0
    while ready:
        current = ready.pop()
        seen += 1
        for dest in outgoing.get(current, []):
            incoming[dest] -= 1
            if incoming[dest] == 0:
                ready.append(dest)
    return seen != len(ids)


def promote_human_gate_required(graph: TaskGraph, tasks: list[Task]) -> bool:
    """Chapter 4.3 planning-mode table: a model_assisted graph needs
    approval when any node is risk_class >= high or blast_radius >=
    cross_module. Pure function over the promoted nodes so both the
    promotion event and the caller's activation path consult ONE
    definition of the threshold."""
    if graph.planning_mode != "model_assisted":
        return False
    return any(
        task.risk_class in HUMAN_GATE_RISK_CLASSES
        or task.blast_radius in HUMAN_GATE_BLAST_RADII
        for task in tasks
    )


def human_gate_scope_hash(*, mission_id: UUID, graph_id: UUID) -> str:
    """Chapter 13.1 scope_hash binding an `architecture_change` approval
    to exactly one promoted model-assisted graph."""
    return approval_scope_hash(
        approval_type="architecture_change",
        mission_id=mission_id,
        payload={"graph_id": str(graph_id), "gate": "model_assisted_activation"},
    )


class PlanningRegistryService:
    """Async, PostgreSQL-backed writer for the two Chapter 4.3 tables.
    Each public method opens and commits its own unit of work unless one
    is supplied, matching every sibling service in this codebase."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: PlanningRegistryRepository | None = None,
        events: EventService | None = None,
        clock: Clock | None = None,
        commands: CommandLedger | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or PlanningRegistryRepository()
        self._events = events or EventService(engine)
        self._clock = clock or SystemClock()
        self._commands = commands or CommandLedger(engine)

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    # --- template registry -------------------------------------------------

    async def register_template(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        template_key: str,
        description: str,
        nodes: list[dict[str, object]],
        edges: list[dict[str, object]],
        created_by: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> MissionTemplate:
        """Register (or idempotently return) one named template version."""
        if not template_key:
            raise DdeError(
                "POLICY_DENIED",
                "A mission template declares the stable key it is registered under",
                details={"template_key": template_key},
            )
        parsed_nodes = [TemplateNode.model_validate(node) for node in nodes]
        parsed_edges = [TemplateEdge.model_validate(edge) for edge in edges]
        _check_template_shape(parsed_nodes, parsed_edges)
        version = template_version_hash(
            tenant_id=tenant_id,
            project_id=project_id,
            template_key=template_key,
            description=description,
            nodes=parsed_nodes,
            edges=parsed_edges,
            # Registered templates instantiate through the deterministic
            # template-mode planner policy; the version travels with the
            # row so a graph can always name what produced it.
            planner_policy_version="template-v1",
        )

        async def _op(active: PostgresUnitOfWork) -> MissionTemplate:
            existing = await self._repository.get_template_by_version(
                active.connection,
                project_id=project_id,
                template_key=template_key,
                template_version=version,
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            template = MissionTemplate(
                template_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                template_key=template_key,
                template_version=version,
                description=description,
                nodes=parsed_nodes,
                edges=parsed_edges,
                status="ACTIVE",
                planner_policy_version="template-v1",
                created_by=created_by,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_template(active.connection, template)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="MissionTemplateRegistered",
                aggregate_type="mission_template",
                aggregate_id=template.template_id,
                payload={
                    "template_key": template_key,
                    "template_version": version,
                    "node_count": len(parsed_nodes),
                },
                uow=active,
            )
            return template

        return await self._run(uow, tenant_id, project_id, _op)

    async def retire_template(
        self,
        record: MissionTemplate,
        *,
        uow: PostgresUnitOfWork | None = None,
    ) -> MissionTemplate:
        """The single lifecycle mutation: ACTIVE -> RETIRED at this call
        site, terminal thereafter."""

        async def _op(active: PostgresUnitOfWork) -> MissionTemplate:
            current = await self._require_template(active, record.template_id)
            assert_template_transition(current.status, "RETIRED")
            now = self._clock.now()
            await self._repository.update_template_status(
                active.connection,
                current.template_id,
                status="RETIRED",
                updated_at=now,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="MissionTemplateRetired",
                aggregate_type="mission_template",
                aggregate_id=current.template_id,
                payload={
                    "template_key": current.template_key,
                    "template_version": current.template_version,
                },
                uow=active,
            )
            return await self._require_template(active, current.template_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    async def get_template(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        template_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> MissionTemplate:
        async def _op(active: PostgresUnitOfWork) -> MissionTemplate:
            return await self._require_template(active, template_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_active_templates(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[MissionTemplate]:
        async def _op(active: PostgresUnitOfWork) -> list[MissionTemplate]:
            return await self._repository.list_active_for_project(
                active.connection, project_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    # --- plan drafts ---------------------------------------------------------

    async def submit_draft(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        origin: str,
        origin_policy_version: str,
        nodes: list[dict[str, object]],
        edges: list[dict[str, object]],
        created_by_principal: UUID,
        adapter_ref: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> PlanDraft:
        """Record one untrusted proposal in PROPOSED state. Idempotent on
        the draft's provenance identity: the same mission proposed from
        the same origin/adapter/policy over the same node content replays
        the first row instead of minting a twin."""
        if origin not in {"model_assisted", "human_authored"}:
            raise DdeError(
                "POLICY_DENIED",
                "A plan draft records which planner proposed it; "
                "'template' plans are produced deterministically and "
                "never enter this table",
                details={"origin": origin},
            )
        parsed_nodes = [DraftNode.model_validate(node) for node in nodes]
        parsed_edges = [DraftEdge.model_validate(edge) for edge in edges]
        if not parsed_nodes:
            raise DdeError(
                "GRAPH_INVALID",
                "An empty decomposition is not a plan draft",
            )
        provenance = sha256_hex(
            canonical_json(
                {
                    "identity": draft_provenance_key(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        mission_id=mission_id,
                        origin=origin,
                        adapter_ref=adapter_ref,
                        origin_policy_version=origin_policy_version,
                        nodes=[],
                    ),
                    "nodes": sorted(str(node.node_key) for node in parsed_nodes),
                    "edges": sorted(
                        f"{edge.from_node_key}>{edge.to_node_key}:{edge.edge_type}"
                        for edge in parsed_edges
                    ),
                }
            )
        )

        async def _op(active: PostgresUnitOfWork) -> PlanDraft:
            existing = await self._repository.get_draft_by_provenance(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                provenance_key=provenance,
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            draft = PlanDraft(
                draft_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                origin=origin,
                adapter_ref=adapter_ref,
                origin_policy_version=origin_policy_version,
                nodes=parsed_nodes,
                edges=parsed_edges,
                status="PROPOSED",
                refusals=[],
                provenance_key=provenance,
                created_by_principal=created_by_principal,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_draft(active.connection, draft)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="PlanDraftSubmitted",
                aggregate_type="plan_draft",
                aggregate_id=draft.draft_id,
                mission_id=mission_id,
                payload={
                    "origin": origin,
                    "adapter_ref": adapter_ref,
                    "provenance_key": provenance,
                },
                uow=active,
            )
            return draft

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_draft(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        draft_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> PlanDraft:
        async def _op(active: PostgresUnitOfWork) -> PlanDraft:
            return await self._require_draft(active, draft_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def validate_draft(
        self,
        record: PlanDraft,
        *,
        mission: Mission,
        approved_requirement_slugs: set[str],
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> PlanDraft:
        """Run the deterministic structural validator over the draft's
        nodes/edges and record the verdict on the row. Guarded by the
        command ledger: same key in, same recorded verdict out. The
        request hash covers the DRAFT identity, not the caller's snapshot
        of its status -- a replay after the first call mutated the row is
        still the same command."""
        request_hash = sha256_hex(
            canonical_json(
                {
                    "draft_id": str(record.draft_id),
                    "command": "validate",
                    "policy": DRAFT_VALIDATOR_POLICY_VERSION,
                }
            )
        )

        async def _op(active: PostgresUnitOfWork) -> PlanDraft:
            ledger_record, is_new = await self._commands.begin(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                replayed = await self._replay_or_raise(ledger_record, active)
                return replayed
            current = await self._require_draft(active, record.draft_id)
            assert_draft_transition(current.status, "VALIDATED")

            tasks, edges, refusals = self._materialise(current, mission)
            report = validate_graph(
                tasks,
                edges,
                approved_requirement_slugs=approved_requirement_slugs,
            )
            refusals.extend(
                Refusal(error_code=code, message=message)
                for code, message in zip(
                    report.error_codes, report.messages, strict=True
                )
            )
            target = "VALIDATED" if report.valid else "REJECTED"
            now = self._clock.now()
            await self._repository.update_draft(
                active.connection,
                current.draft_id,
                status=target,
                refusals=list(refusals),
                promoted_graph_id=None,
                updated_at=now,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="PlanDraftValidated",
                aggregate_type="plan_draft",
                aggregate_id=current.draft_id,
                mission_id=current.mission_id,
                payload={
                    "status": target,
                    "refusal_codes": [r.error_code for r in refusals],
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                command_id=ledger_record.command_id,
                result={"draft_id": str(current.draft_id), "status": target},
                uow=active,
            )
            return await self._require_draft(active, current.draft_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    async def promote_draft(
        self,
        record: PlanDraft,
        *,
        mission: Mission,
        graph_id: UUID,
        planner_policy_version: str,
        created_by_principal: UUID,
        approved_requirement_slugs: set[str],
        create_task_graph: Callable[..., Awaitable[TaskGraph]],
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> tuple[PlanDraft, TaskGraph]:
        """Turn a VALIDATED draft into a real TaskGraph through the
        ordinary creation lifecycle. The materialised nodes are handed to
        the caller-supplied composition hook -- production wiring passes
        `MissionService.create_task_graph`, which drives
        DRAFT -> VALIDATING -> APPROVED|REJECTED, inserts the Task rows
        and their edges in one shared unit of work. This service never
        writes `task_graphs`/`tasks` rows itself: Chapter 3.8 keeps those
        tables owned by their existing writer modules.

        Returns `(draft, graph)`; the draft row carries
        `promoted_graph_id` as the durable provenance link.
        """
        request_hash = sha256_hex(
            canonical_json(
                {
                    "draft_id": str(record.draft_id),
                    "command": "promote",
                    "policy": planner_policy_version,
                }
            )
        )

        async def _op(active: PostgresUnitOfWork) -> tuple[PlanDraft, TaskGraph]:
            ledger_record, is_new = await self._commands.begin(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                replayed = await self._replay_or_raise(ledger_record, active)
                if replayed.promoted_graph_id is None:
                    raise DdeError(
                        "VERSION_CONFLICT",
                        "Command previously failed; refusing to re-execute",
                        details={"idempotency_key": idempotency_key},
                    )
                graph = await self._require_graph(active, replayed.promoted_graph_id)
                return replayed, graph
            current = await self._require_draft(active, record.draft_id)
            if current.status != "VALIDATED":
                raise DraftNotPromotableError(
                    "POLICY_DENIED",
                    "Only a VALIDATED draft may be promoted; a model's raw "
                    "proposal is never an executable graph",
                    details={
                        "draft_id": str(current.draft_id),
                        "status": current.status,
                    },
                )
            assert_draft_transition(current.status, "PROMOTED")

            tasks, edges, _refusals = self._materialise(
                current, mission, graph_id=graph_id
            )
            graph = await create_task_graph(
                mission=mission,
                graph_id=graph_id,
                tasks=tasks,
                edges=edges,
                planning_mode="model_assisted",
                planner_policy_version=planner_policy_version,
                rationale=f"draft:{current.provenance_key[:16]}",
                created_by_principal=created_by_principal,
                approved_requirement_slugs=approved_requirement_slugs,
                uow=active,
            )
            if graph.status != "APPROVED":
                raise DraftNotPromotableError(
                    "GRAPH_INVALID",
                    "The draft's nodes failed graph validation on promotion",
                    details={
                        "graph_id": str(graph.graph_id),
                        "graph_status": graph.status,
                    },
                )

            gate_required = promote_human_gate_required(graph, tasks)
            now = self._clock.now()
            await self._repository.update_draft(
                active.connection,
                current.draft_id,
                status="PROMOTED",
                refusals=[],
                promoted_graph_id=graph.graph_id,
                updated_at=now,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="PlanDraftPromoted",
                aggregate_type="plan_draft",
                aggregate_id=current.draft_id,
                mission_id=current.mission_id,
                payload={
                    "promoted_graph_id": str(graph.graph_id),
                    "planning_mode": "model_assisted",
                    "human_gate_required": gate_required,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                command_id=ledger_record.command_id,
                result={
                    "draft_id": str(current.draft_id),
                    "promoted_graph_id": str(graph.graph_id),
                },
                uow=active,
            )
            return (
                await self._require_draft(active, current.draft_id),
                graph,
            )

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    # --- internals ---------------------------------------------------------

    def _materialise(
        self,
        draft: PlanDraft,
        mission: Mission,
        *,
        graph_id: UUID | None = None,
    ) -> tuple[list[Task], list[TaskGraphEdge], list[Refusal]]:
        """Materialise untrusted node_keys into real Task/TaskGraphEdge
        objects scoped to the mission so `validate_graph` can run
        unchanged. Structural problems that make materialisation
        impossible (dangling edge endpoints, duplicate keys) become typed
        refusals rather than crashes -- the draft is data, and bad data
        gets judged, not raised over. Promotion passes the caller's real
        `graph_id`; validation uses a deterministic placeholder that is
        never persisted."""
        refusals: list[Refusal] = []
        by_key: dict[str, Task] = {}
        now = self._clock.now()
        target_graph_id = graph_id or _placeholder_graph_id(draft.draft_id)
        for node in draft.nodes:
            if node.node_key in by_key:
                refusals.append(
                    Refusal(
                        error_code="GRAPH_INVALID",
                        message=f"Duplicate node key {node.node_key}",
                        node_keys=[node.node_key],
                    )
                )
                continue
            by_key[node.node_key] = Task(
                task_id=_stable_task_id(draft.draft_id, node.node_key),
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                mission_id=mission.mission_id,
                graph_id=target_graph_id,
                parent_task_id=None,
                title=node.title,
                intent=node.intent,
                task_class=node.task_class,
                requirement_refs=list(node.requirement_refs or []),
                feature_refs=list(node.feature_refs or []),
                success_criteria=list(node.success_criteria),
                expected_write_scope=list(node.write_scope),
                expected_read_scope=list(node.read_scope or []),
                blast_radius="local",
                risk_class="low",
                estimated_effort=node.estimated_effort or "s",
                autonomy_ceiling=min(mission.autonomy_ceiling, 3),
                requires_approval=False,
                verification_profile_ref="unit",
                status="CREATED",
                lock_version=1,
                created_at=now,
                updated_at=now,
            )
        tasks = [
            by_key[node.node_key] for node in draft.nodes if node.node_key in by_key
        ]
        edges: list[TaskGraphEdge] = []
        for edge in draft.edges:
            source = by_key.get(edge.from_node_key)
            dest = by_key.get(edge.to_node_key)
            if source is None or dest is None:
                dangling = [
                    key
                    for key in (edge.from_node_key, edge.to_node_key)
                    if key not in by_key
                ]
                refusals.append(
                    Refusal(
                        error_code="GRAPH_INVALID",
                        message=f"Edge references unknown node(s): {dangling}",
                        node_keys=dangling,
                    )
                )
                continue
            edges.append(
                TaskGraphEdge(
                    edge_id=uuid7(),
                    tenant_id=mission.tenant_id,
                    project_id=mission.project_id,
                    mission_id=mission.mission_id,
                    graph_id=target_graph_id,
                    from_task_id=source.task_id,
                    to_task_id=dest.task_id,
                    edge_type=edge.edge_type,
                    contract_ref=edge.contract_ref,
                    created_at=now,
                    updated_at=now,
                )
            )
        return tasks, edges, refusals

    async def _replay_or_raise(
        self,
        ledger_record: CommandIdempotency,
        active: PostgresUnitOfWork,
    ) -> PlanDraft:
        if ledger_record.status == "completed" and ledger_record.result is not None:
            draft_id = UUID(str(ledger_record.result["draft_id"]))
            return await self._require_draft(active, draft_id)
        if ledger_record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": ledger_record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": ledger_record.idempotency_key},
        )

    async def _require_template(
        self, active: PostgresUnitOfWork, template_id: UUID
    ) -> MissionTemplate:
        found = await self._repository.get_template(active.connection, template_id)
        if found is None:
            raise DdeError("POLICY_DENIED", "Unknown mission template")
        return found

    async def _require_draft(
        self, active: PostgresUnitOfWork, draft_id: UUID
    ) -> PlanDraft:
        found = await self._repository.get_draft(active.connection, draft_id)
        if found is None:
            raise DdeError("POLICY_DENIED", "Unknown plan draft")
        return found

    async def _require_graph(
        self, active: PostgresUnitOfWork, graph_id: UUID
    ) -> TaskGraph:
        from engine.planning.repository import TaskGraphRepository

        found = await TaskGraphRepository().get_task_graph(active.connection, graph_id)
        if found is None:
            raise DdeError("GRAPH_INVALID", "Unknown task graph")
        return found


def _placeholder_graph_id(seed: UUID) -> UUID:
    """Deterministic per-draft placeholder graph id for the materialised
    validation objects. Promotion replaces it with the caller's real
    `graph_id`; validation objects are never persisted anywhere, and the
    determinism keeps a re-run of `_materialise` comparable."""
    return UUID(int=(seed.int & ~0xFFFF) | 0x5C0F)


def _stable_task_id(seed: UUID, node_key: str) -> UUID:
    """Deterministic per-(draft, node_key) identifier so repeated
    materialisation of one draft yields comparable objects without any
    database round-trip. Version bits keep it a valid UUIDv7-shaped
    value only incidentally; identity, not ordering, matters here."""
    digest = sha256_hex(canonical_json({"seed": str(seed), "node": node_key}))
    return UUID(int=int(digest[:32], 16))


__all__ = [
    "DRAFT_VALIDATOR_POLICY_VERSION",
    "DraftNotPromotableError",
    "PlanningRegistryService",
    "TemplateShapeError",
    "has_cycle",
    "human_gate_scope_hash",
    "promote_human_gate_required",
]
