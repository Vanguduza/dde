"""Production VEKL Unit Knowledge Graph and deterministic GraphRAG service.

The service compiles rebuildable projections and immutable resolution evidence. It reads
existing Project Truth, TaskGraph, StackFingerprint, Source/VEKL and Context
authorities; it never becomes a second writer for any of them.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.embeddings import EMBEDDING_MODEL_VERSION, cosine_similarity, embed
from engine.context.index_repository import ContextIndexRepository
from engine.contracts.stack_fingerprint import StackFingerprint
from engine.contracts.task import Task
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.contracts.task_signature import TaskSignature
from engine.contracts.vekl_execution_knowledge_binding import (
    VEKLExecutionKnowledgeBinding,
)
from engine.contracts.vekl_graph_invalidation import VEKLGraphInvalidation
from engine.contracts.vekl_knowledge_edge import VEKLKnowledgeEdge
from engine.contracts.vekl_knowledge_node import VEKLKnowledgeNode
from engine.contracts.vekl_research_finding import VEKLResearchFinding
from engine.contracts.vekl_resolution_trace import VEKLResolutionTrace
from engine.contracts.vekl_retrieval_route import VEKLRetrievalRoute
from engine.contracts.vekl_truth_challenge import VEKLTruthChallenge
from engine.contracts.vekl_truth_challenge_finding import VEKLTruthChallengeFinding
from engine.contracts.vekl_unit_map import VEKLUnitMap
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.missions.repository import MissionsRepository
from engine.missions.service import MissionService
from engine.planning.repository import TaskGraphRepository
from engine.studio.tables import frontend_contracts, pxg_nodes
from engine.truth.db import open_unit_of_work
from engine.truth.service import TruthService
from engine.vekl.knowledge import (
    GRAPH_COMPILER_VERSION,
    HARD_PRODUCT_QUALITY_GATES,
    QUALITATIVE_ESCALATION,
    QUALITATIVE_PRODUCT_QUALITY_GATES,
    RETRIEVAL_ROUTE_POLICY_HASH,
    ROUTE_REGISTRY_VERSION,
    TRUTH_DECISION_CLASS,
    TRUTH_DECISION_ROLE,
    TRUTH_REVIEWER_CLASS,
    UNIT_BOUNDARY_POLICY_VERSION,
    UNIT_PROJECTION_COMPILER_VERSION,
    challenge_eligibility,
    classify_concerns,
    deterministic_uuid,
    graph_snapshot_hash,
    resolution_envelope,
    route_policy,
    route_slug,
    selection_role,
    unit_lineage_id,
    unit_revision_hash,
    validate_truth_patch,
)
from engine.vekl.knowledge_repository import VEKLKnowledgeRepository
from engine.vekl.models import ChangeImpactSpec
from engine.vekl.policy import EligibilityContext, evaluate
from engine.vekl.repository import VEKLRepository
from engine.vekl.service import ProjectTruthSnapshot, VEKLService

REFERENCE_LIFECYCLE = frozenset(
    {
        "REFERENCE_QUALIFIED",
        "EXECUTION_QUARANTINED",
        "EXECUTION_EVALUATED",
        "CANARY",
        "PRODUCTION_QUALIFIED",
    }
)
UI_CONCERNS = frozenset({"WEB_UI", "MOBILE_UI", "DESIGN", "ACCESSIBILITY"})
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


class VEKLKnowledgeService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        knowledge: VEKLKnowledgeRepository | None = None,
        vekl: VEKLRepository | None = None,
        context_indexes: ContextIndexRepository | None = None,
    ) -> None:
        self._engine = engine
        self._knowledge = knowledge or VEKLKnowledgeRepository()
        self._vekl = vekl or VEKLRepository()
        self._context_indexes = context_indexes or ContextIndexRepository()
        self._vekl_service = VEKLService(engine, repository=self._vekl)
        self._approvals = ApprovalService(engine)
        self._missions = MissionService(engine, EventService(engine))
        self._truth_service = TruthService(engine)

    @staticmethod
    def _str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]

    @staticmethod
    def _dict_list(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _score_tuple(value: object) -> tuple[int, ...]:
        if not isinstance(value, list):
            return ()
        return tuple(
            int(item)
            for item in value
            if isinstance(item, (int, float)) and not isinstance(item, bool)
        )

    @staticmethod
    def _score_int(value: object) -> int:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        return 0

    async def _truth(
        self, *, tenant_id: UUID, project_id: UUID, request_mode: str
    ) -> ProjectTruthSnapshot:
        return await self._vekl_service.current_truth_snapshot(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )

    @staticmethod
    def _canonical_task_groups(
        tasks: list[Task], edges: list[TaskGraphEdge]
    ) -> list[list[Task]]:
        """Feature-explicit connected groups; unclassified work stays one-task.

        DDE never guesses a feature boundary. Tasks sharing an explicit feature ref may
        group only if they are weakly dependency-connected; tasks without one remain
        single-task Units, which the architecture explicitly permits.
        """
        by_id = {task.task_id: task for task in tasks}
        adjacency: dict[UUID, set[UUID]] = defaultdict(set)
        for edge in edges:
            if edge.from_task_id in by_id and edge.to_task_id in by_id:
                adjacency[edge.from_task_id].add(edge.to_task_id)
                adjacency[edge.to_task_id].add(edge.from_task_id)
        by_feature: dict[str, list[Task]] = defaultdict(list)
        singles: list[Task] = []
        for task in tasks:
            if not task.feature_refs:
                singles.append(task)
                continue
            by_feature[sorted(task.feature_refs)[0]].append(task)
        groups: list[list[Task]] = [[task] for task in singles]
        for feature in sorted(by_feature):
            candidates = {task.task_id: task for task in by_feature[feature]}
            unseen = set(candidates)
            while unseen:
                root = min(unseen, key=str)
                stack = [root]
                component: set[UUID] = set()
                while stack:
                    current = stack.pop()
                    if current in component:
                        continue
                    component.add(current)
                    stack.extend(
                        sorted(
                            adjacency[current] & set(candidates) - component,
                            key=str,
                            reverse=True,
                        )
                    )
                unseen -= component
                groups.append([candidates[item] for item in component])
        return [
            VEKLKnowledgeService._topological_order(group, edges) for group in groups
        ]

    @staticmethod
    def _topological_order(tasks: list[Task], edges: list[TaskGraphEdge]) -> list[Task]:
        by_id = {task.task_id: task for task in tasks}
        indegree = {task_id: 0 for task_id in by_id}
        outgoing: dict[UUID, set[UUID]] = defaultdict(set)
        for edge in edges:
            if edge.from_task_id in by_id and edge.to_task_id in by_id:
                if edge.to_task_id not in outgoing[edge.from_task_id]:
                    outgoing[edge.from_task_id].add(edge.to_task_id)
                    indegree[edge.to_task_id] += 1
        ready = sorted(
            (item for item, degree in indegree.items() if degree == 0), key=str
        )
        ordered: list[UUID] = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for target in sorted(outgoing[current], key=str):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort(key=str)
        if len(ordered) != len(by_id):
            raise DdeError(
                "VEKL_UNIT_INVALID",
                "TaskGraph cycle prevents deterministic Unit projection",
            )
        return [by_id[item] for item in ordered]

    @staticmethod
    def _truth_slice(
        truth: ProjectTruthSnapshot, tasks: list[Task]
    ) -> tuple[dict[str, object], str]:
        refs = {ref for task in tasks for ref in task.requirement_refs}
        global_items = {
            key: value
            for key, value in truth.constraints.items()
            if key.startswith("constitution:") or key.startswith("edr:")
        }
        if not refs:
            selected = dict(truth.constraints)
        else:
            selected = dict(global_items)
            resolved: set[str] = set()
            for ref in sorted(refs):
                keys = {
                    ref,
                    f"requirement:{ref}",
                }
                matches = [
                    key
                    for key in truth.constraints
                    if key in keys
                    or key.startswith(f"constraint:{ref}:")
                    or key.startswith(f"constraint:requirement:{ref}:")
                ]
                if matches:
                    resolved.add(ref)
                    for key in matches:
                        selected[key] = truth.constraints[key]
            if resolved != refs:
                # Unknown reference syntax is not guessed. Preserve all authoritative
                # truth so the Unit cannot silently lose a governing constraint.
                selected = dict(truth.constraints)
        return selected, sha256_hex(canonical_json(selected))

    @staticmethod
    def _boundary(
        *, task_ids: set[UUID], edges: list[TaskGraphEdge]
    ) -> tuple[list[UUID], list[UUID], list[str], list[str]]:
        upstream: set[UUID] = set()
        downstream: set[UUID] = set()
        consumed: set[str] = set()
        produced: set[str] = set()
        for edge in edges:
            source_inside = edge.from_task_id in task_ids
            target_inside = edge.to_task_id in task_ids
            if target_inside and not source_inside:
                upstream.add(edge.from_task_id)
            if source_inside and not target_inside:
                downstream.add(edge.to_task_id)
            if edge.contract_ref:
                if target_inside:
                    consumed.add(edge.contract_ref)
                if source_inside:
                    produced.add(edge.contract_ref)
        return (
            sorted(upstream, key=str),
            sorted(downstream, key=str),
            sorted(consumed),
            sorted(produced),
        )

    async def _product_experience(
        self,
        *,
        connection: object,
        project_id: UUID,
        requires_ui: bool,
    ) -> tuple[str | None, list[str], bool]:
        if not requires_ui:
            return None, [], True
        # SQLAlchemy AsyncConnection is intentionally duck-typed here to keep this
        # helper private to the transaction-owning caller.
        contract_row = (
            (
                await connection.execute(  # type: ignore[attr-defined]
                    select(frontend_contracts)
                    .where(
                        frontend_contracts.c.project_id == project_id,
                        frontend_contracts.c.status == "ACTIVE",
                    )
                    .order_by(frontend_contracts.c.contract_version.desc())
                    .limit(1)
                )
            )
            .mappings()
            .first()
        )
        pxg_revision = await connection.scalar(  # type: ignore[attr-defined]
            select(func.max(pxg_nodes.c.pxg_revision)).where(
                pxg_nodes.c.project_id == project_id
            )
        )
        if contract_row is None or pxg_revision is None:
            return None, [], False
        refs = [
            f"frontend-contract:{contract_row['contract_id']}:{contract_row['contract_version']}",
            f"pxg-revision:{pxg_revision}",
        ]
        digest = sha256_hex(
            canonical_json(
                {
                    "contract_hash": contract_row["content_hash"],
                    "contract_version": contract_row["contract_version"],
                    "pxg_revision": int(pxg_revision),
                }
            )
        )
        return digest, refs, True

    @staticmethod
    def _foresight_questions(
        *,
        concerns: set[str],
        requires_ui: bool,
        consumed_contracts: list[str],
        produced_contracts: list[str],
    ) -> list[str]:
        """Deterministic ahead-of-work research questions for one Unit.

        Only questions explicitly prefixed MANDATORY participate in the readiness gate.
        The policy is intentionally conservative: security, payment-integrity and
        migration concerns require current evidence; ordinary implementation questions
        remain useful foresight without blocking work.
        """
        mandatory = {"SECURITY", "PAYMENTS", "MIGRATION"}
        questions: list[str] = []
        for concern in sorted(concerns):
            prefix = "MANDATORY" if concern in mandatory else "OPTIONAL"
            questions.append(
                f"{prefix}|{concern}|Confirm exact current, source-admitted guidance "
                "and known failure/recovery constraints for this Unit."
            )
        if requires_ui:
            questions.append(
                "OPTIONAL|PRODUCT_EXPERIENCE|Confirm the current PXG/Frontend Contract "
                "journey, state, accessibility and visual-verification obligations."
            )
        if consumed_contracts or produced_contracts:
            questions.append(
                "OPTIONAL|CONTRACTS|Check compatibility and downstream impact for "
                "consumed/produced contracts before mutation."
            )
        return questions

    @staticmethod
    def _mandatory_research_concerns(questions: list[str]) -> set[str]:
        return {
            parts[1]
            for question in questions
            if len(parts := question.split("|", 2)) == 3 and parts[0] == "MANDATORY"
        }

    async def seed_retrieval_routes(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        request_mode: str,
    ) -> list[VEKLRetrievalRoute]:
        await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        now = datetime.now(UTC)
        created: list[VEKLRetrievalRoute] = []
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            for concern in (
                "WEB_UI",
                "MOBILE_UI",
                "BACKEND_API",
                "DATABASE",
                "AUTH",
                "SECURITY",
                "PAYMENTS",
                "MIGRATION",
                "TESTING",
                "DESIGN",
                "ACCESSIBILITY",
                "PERFORMANCE",
                "OBSERVABILITY",
                "DEPLOYMENT",
                "INCIDENT",
                "PACKAGE_UPGRADE",
                "DONOR_REUSE",
                "GENERIC_IMPLEMENTATION",
            ):
                policy = route_policy(concern)
                policy_hash = sha256_hex(
                    canonical_json(
                        {
                            "registry_version": ROUTE_REGISTRY_VERSION,
                            "concern": concern,
                            "policy": policy,
                        }
                    )
                )
                existing = await self._knowledge.route_by_hash(
                    uow.connection,
                    project_id=project_id,
                    policy_hash=policy_hash,
                )
                if existing is not None:
                    created.append(existing)
                    continue
                record = VEKLRetrievalRoute(
                    route_id=deterministic_uuid(
                        "route",
                        {
                            "tenant_id": str(tenant_id),
                            "project_id": str(project_id),
                            "policy_hash": policy_hash,
                        },
                    ),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    route_slug=route_slug(concern),
                    version=ROUTE_REGISTRY_VERSION,
                    concern=concern,
                    policy=policy,
                    policy_hash=policy_hash,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
                await self._knowledge.insert_route(uow.connection, record)
                created.append(record)
            await uow.commit()
        return created

    async def foresight(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_graph_id: UUID,
        request_mode: str,
    ) -> dict[str, object]:
        """Project the next dependency-safe knowledge needs without replanning Tasks."""
        truth = await self._truth(
            tenant_id=tenant_id, project_id=project_id, request_mode=request_mode
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            graph = await TaskGraphRepository().get_task_graph(
                uow.connection, task_graph_id
            )
            if (
                graph is None
                or graph.tenant_id != tenant_id
                or graph.project_id != project_id
            ):
                raise DdeError(
                    "VEKL_UNIT_INVALID",
                    "foresight TaskGraph is absent or outside the target project",
                )
            tasks = await MissionsRepository().list_tasks_for_graph(
                uow.connection, task_graph_id
            )
            task_by_id = {task.task_id: task for task in tasks}
            units = await self._knowledge.list_active_unit_maps(
                uow.connection,
                project_id=project_id,
                task_graph_id=task_graph_id,
            )
            routes = {
                route.route_id: route
                for route in await self._knowledge.list_active_routes(
                    uow.connection, project_id=project_id
                )
            }
            forecasts: list[dict[str, object]] = []
            for unit in units:
                blocked_by = [
                    task_id
                    for task_id in unit.upstream_task_refs
                    if (task := task_by_id.get(task_id)) is None
                    or task.status not in {"COMPLETED", "SUPERSEDED", "RETIRED"}
                ]
                unit_tasks = [
                    task_by_id[task_id]
                    for task_id in unit.task_ids
                    if task_id in task_by_id
                ]
                if not unit_tasks:
                    continue
                active_work = any(
                    task.status not in {"COMPLETED", "SUPERSEDED", "RETIRED"}
                    for task in unit_tasks
                )
                signatures = [
                    await self._vekl.latest_signature_for_task(
                        uow.connection, project_id=project_id, task_id=task.task_id
                    )
                    for task in unit_tasks
                ]
                archetypes = sorted(
                    {
                        str(signature.constraints.get("engineering_archetype"))
                        for signature in signatures
                        if signature is not None
                        and signature.constraints.get("engineering_archetype")
                    }
                )
                route_rows = [
                    routes[route_id]
                    for route_id in unit.knowledge_route_ids
                    if route_id in routes
                ]
                preferred_source_families = sorted(
                    {
                        kind
                        for route in route_rows
                        for kind in self._str_list(route.policy.get("resource_kinds"))
                    }
                )
                required_resource_roles = sorted(
                    {
                        role
                        for route in route_rows
                        for role in self._str_list(route.policy.get("roles"))
                    }
                )
                concerns = self._str_list(unit.scope.get("concerns"))
                forecasts.append(
                    {
                        "unit_map_id": str(unit.unit_map_id),
                        "unit_lineage_id": unit.unit_lineage_id,
                        "unit_revision_hash": unit.unit_revision_hash,
                        "task_refs": [str(item) for item in unit.task_ids],
                        "objective": unit.objective,
                        "task_classes": sorted(
                            {task.task_class for task in unit_tasks}
                        ),
                        "engineering_archetypes": archetypes,
                        "stack_concerns": concerns,
                        "research_questions": list(unit.research_questions),
                        "preferred_source_families": preferred_source_families,
                        "required_resource_roles": required_resource_roles,
                        "security_questions": [
                            item
                            for item in unit.research_questions
                            if "|SECURITY|" in item
                        ],
                        "product_experience_questions": [
                            item
                            for item in unit.research_questions
                            if "|PRODUCT_EXPERIENCE|" in item
                        ],
                        "known_risks": sorted(
                            {
                                f"{task.risk_class}:{task.blast_radius}"
                                for task in unit_tasks
                            }
                        ),
                        "verification_needs": list(unit.required_verifiers),
                        "truth_conflict_watchpoints": list(unit.requirement_refs)
                        + list(unit.edr_refs),
                        "dependency_safe": not blocked_by,
                        "blocked_by_upstream": [
                            str(item) for item in sorted(blocked_by, key=str)
                        ],
                        "active_work": active_work,
                        "knowledge_readiness_state": unit.knowledge_readiness_state,
                    }
                )
            forecasts.sort(
                key=lambda item: (
                    not bool(item["dependency_safe"]),
                    not bool(item["active_work"]),
                    str(item["unit_lineage_id"]),
                )
            )
            return {
                "project_truth_hash": truth.truth_hash,
                "task_graph_id": str(task_graph_id),
                "task_graph_version": graph.version,
                "forecasts": forecasts,
            }

    async def compile_units_for_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_graph_id: UUID,
        stack_fingerprint_id: UUID,
        request_mode: str,
        exemption: dict[str, object] | None = None,
    ) -> list[VEKLUnitMap]:
        truth = await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        routes = await self.seed_retrieval_routes(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        route_by_concern = {route.concern: route for route in routes}
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            graph = await TaskGraphRepository().get_task_graph(
                uow.connection, task_graph_id
            )
            if (
                graph is None
                or graph.tenant_id != tenant_id
                or graph.project_id != project_id
            ):
                raise DdeError(
                    "VEKL_UNIT_INVALID",
                    "TaskGraph is absent or outside the addressed target project",
                )
            tasks = await MissionsRepository().list_tasks_for_graph(
                uow.connection, task_graph_id
            )
            edges = await TaskGraphRepository().list_edges_for_graph(
                uow.connection, task_graph_id
            )
            fingerprint = await self._vekl.get_fingerprint(
                uow.connection,
                project_id=project_id,
                fingerprint_id=stack_fingerprint_id,
            )
            if (
                fingerprint is None
                or fingerprint.project_truth_hash != truth.truth_hash
            ):
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "Unit projection requires a StackFingerprint bound to "
                    "current Project Truth",
                )
            groups = self._canonical_task_groups(tasks, edges)
            output: list[VEKLUnitMap] = []
            for group in groups:
                ids = [task.task_id for task in group]
                id_set = set(ids)
                upstream, downstream, consumed, produced = self._boundary(
                    task_ids=id_set, edges=edges
                )
                truth_slice, truth_slice_hash = self._truth_slice(truth, group)
                concerns: set[str] = set()
                for task in group:
                    concerns.update(
                        classify_concerns(
                            title=task.title,
                            intent=task.intent,
                            task_class=task.task_class,
                            read_scope=task.expected_read_scope,
                            write_scope=task.expected_write_scope,
                        )
                    )
                ordered_concerns = [
                    concern for concern in route_by_concern if concern in concerns
                ]
                route_ids = [
                    route_by_concern[item].route_id for item in ordered_concerns
                ]
                requires_ui = bool(UI_CONCERNS & concerns)
                (
                    product_hash,
                    product_refs,
                    product_ready,
                ) = await self._product_experience(
                    connection=uow.connection,
                    project_id=project_id,
                    requires_ui=requires_ui,
                )
                research_questions = self._foresight_questions(
                    concerns=concerns,
                    requires_ui=requires_ui,
                    consumed_contracts=consumed,
                    produced_contracts=produced,
                )
                contract_payload = {
                    "task_graph_hash": graph.graph_hash,
                    "consumed": consumed,
                    "produced": produced,
                    "upstream": [str(item) for item in upstream],
                    "downstream": [str(item) for item in downstream],
                }
                contract_hash = sha256_hex(canonical_json(contract_payload))
                lineage = unit_lineage_id(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    feature_refs=sorted(
                        {ref for task in group for ref in task.feature_refs}
                    ),
                    realization_facets=sorted({task.task_class for task in group}),
                    fallback_task_ids=sorted(ids, key=str),
                )
                revision = unit_revision_hash(
                    lineage_id=lineage,
                    task_graph_version=graph.version,
                    project_truth_hash=truth.truth_hash,
                    applicable_truth_slice_hash=truth_slice_hash,
                    stack_fingerprint_hash=fingerprint.fingerprint_hash,
                    contract_set_hash=contract_hash,
                    product_experience_hash=product_hash,
                )
                existing = await self._knowledge.unit_map_by_revision(
                    uow.connection,
                    project_id=project_id,
                    unit_revision_hash=revision,
                )
                if existing is not None:
                    output.append(existing)
                    continue
                if exemption is not None:
                    required_exemption = {
                        "policy_id",
                        "policy_version",
                        "policy_hash",
                        "archetype",
                        "reason",
                    }
                    if not required_exemption.issubset(exemption):
                        raise DdeError(
                            "VEKL_UNIT_INVALID",
                            "knowledge exemption is missing its versioned policy "
                            "binding",
                            details={
                                "missing": sorted(required_exemption - set(exemption))
                            },
                        )
                    readiness = "EXEMPT_BY_POLICY"
                    exemption_payload: dict[str, object] | None = dict(exemption)
                elif not product_ready:
                    readiness = "BLOCKED"
                    exemption_payload = None
                else:
                    readiness = "MAPPING"
                    exemption_payload = None
                scope = {
                    "includes": sorted(
                        {path for task in group for path in task.expected_write_scope}
                    ),
                    "reads": sorted(
                        {path for task in group for path in task.expected_read_scope}
                    ),
                    "excludes": [],
                    "concerns": ordered_concerns,
                    "truth_slice": truth_slice,
                    "product_quality_gates": (
                        {
                            "hard": list(HARD_PRODUCT_QUALITY_GATES),
                            "qualitative": list(QUALITATIVE_PRODUCT_QUALITY_GATES),
                            "qualitative_escalation": QUALITATIVE_ESCALATION,
                            "authority": {
                                "hard": (
                                    "Frontend Contract/PXG + Screen Audit + silhouette"
                                ),
                                "qualitative": "visual_critique",
                                "human_fallback": "prototype_pixel_signoff",
                            },
                        }
                        if requires_ui
                        else {"hard": [], "qualitative": []}
                    ),
                }
                payload: dict[str, object] = {
                    "tenant_id": str(tenant_id),
                    "project_id": str(project_id),
                    "mission_id": str(graph.mission_id),
                    "task_graph_id": str(graph.graph_id),
                    "task_graph_version": graph.version,
                    "task_ids": [str(item) for item in ids],
                    "unit_lineage_id": lineage,
                    "unit_revision_hash": revision,
                    "unit_boundary_policy_version": UNIT_BOUNDARY_POLICY_VERSION,
                    "unit_projection_compiler_version": (
                        UNIT_PROJECTION_COMPILER_VERSION
                    ),
                    "project_truth_hash": truth.truth_hash,
                    "applicable_truth_slice_hash": truth_slice_hash,
                    "stack_fingerprint_id": str(fingerprint.fingerprint_id),
                    "stack_fingerprint_hash": fingerprint.fingerprint_hash,
                    "contract_set_hash": contract_hash,
                    "product_experience_hash": product_hash,
                    "retrieval_route_policy_hash": RETRIEVAL_ROUTE_POLICY_HASH,
                    "objective": " | ".join(task.intent for task in group),
                    "scope": scope,
                    "requirement_refs": sorted(
                        {ref for task in group for ref in task.requirement_refs}
                    ),
                    "edr_refs": sorted(
                        ref for ref in truth.refs if ref.startswith("edr:")
                    ),
                    "constitution_refs": sorted(
                        ref for ref in truth.refs if ref.startswith("constitution:")
                    ),
                    "upstream_task_refs": [str(item) for item in upstream],
                    "downstream_task_refs": [str(item) for item in downstream],
                    "contracts_consumed": consumed,
                    "contracts_produced": produced,
                    "code_targets": sorted(
                        {path for task in group for path in task.expected_write_scope}
                    ),
                    "workspace_refs": [],
                    "product_experience_refs": product_refs,
                    "security_refs": [
                        ref
                        for ref in truth.refs
                        if "security" in ref.lower() or "privacy" in ref.lower()
                    ],
                    "eventuality_refs": [],
                    "research_questions": research_questions,
                    "knowledge_route_ids": [str(item) for item in route_ids],
                    "required_verifiers": sorted(
                        {
                            task.verification_profile_ref
                            for task in group
                            if task.verification_profile_ref is not None
                        }
                        | (
                            set(QUALITATIVE_PRODUCT_QUALITY_GATES) | {"silhouette"}
                            if requires_ui
                            else set()
                        )
                    ),
                    "knowledge_readiness_state": readiness,
                    "knowledge_exemption": exemption_payload,
                    "challenge_state": "CLEAR",
                    "invalidation_reasons": [],
                }
                map_hash = sha256_hex(canonical_json(payload))
                record = VEKLUnitMap(
                    unit_map_id=deterministic_uuid(
                        "unit-map",
                        {
                            "tenant_id": str(tenant_id),
                            "project_id": str(project_id),
                            "unit_revision_hash": revision,
                        },
                    ),
                    created_at=now,
                    updated_at=now,
                    invalidated_at=None,
                    unit_map_hash=map_hash,
                    **payload,
                )
                for prior in await self._knowledge.active_unit_maps_by_lineage(
                    uow.connection,
                    project_id=project_id,
                    unit_lineage_id=lineage,
                ):
                    if prior.unit_revision_hash == revision:
                        continue
                    await self._knowledge.invalidate_unit_map(
                        uow.connection,
                        project_id=project_id,
                        unit_map_id=prior.unit_map_id,
                        reason="VEKL_UNIT_MAP_CHANGED",
                        invalidated_at=now,
                    )
                await self._knowledge.insert_unit_map(uow.connection, record)
                output.append(record)
            await uow.commit()
            return output

    @staticmethod
    def _node_record(
        *,
        tenant_id: UUID,
        project_id: UUID,
        node_kind: str,
        object_type: str,
        object_id: UUID | None,
        stable_ref: str,
        authority_class: str,
        authority_service: str,
        content_hash: str,
        project_truth_hash: str | None,
        metadata: dict[str, object],
        now: datetime,
    ) -> VEKLKnowledgeNode:
        identity = {
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
            "node_kind": node_kind,
            "stable_ref": stable_ref,
            "content_hash": content_hash,
            "projection_compiler_version": GRAPH_COMPILER_VERSION,
        }
        return VEKLKnowledgeNode(
            knowledge_node_id=deterministic_uuid("knowledge-node", identity),
            tenant_id=tenant_id,
            project_id=project_id,
            node_kind=node_kind,
            object_type=object_type,
            object_id=object_id,
            stable_ref=stable_ref,
            authority_class=authority_class,
            authority_service=authority_service,
            source_revision=None,
            content_hash=content_hash,
            projection_compiler_version=GRAPH_COMPILER_VERSION,
            project_truth_hash=project_truth_hash,
            metadata=metadata,
            created_at=now,
            updated_at=now,
            invalidated_at=None,
        )

    @staticmethod
    def _edge_record(
        *,
        tenant_id: UUID,
        project_id: UUID,
        from_node: VEKLKnowledgeNode,
        relationship: str,
        to_node: VEKLKnowledgeNode,
        provenance_ref: str,
        provenance_hash: str,
        derivation_class: str,
        now: datetime,
    ) -> VEKLKnowledgeEdge:
        identity = {
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
            "from_node_id": str(from_node.knowledge_node_id),
            "relationship": relationship,
            "to_node_id": str(to_node.knowledge_node_id),
            "provenance_hash": provenance_hash,
        }
        return VEKLKnowledgeEdge(
            knowledge_edge_id=deterministic_uuid("knowledge-edge", identity),
            tenant_id=tenant_id,
            project_id=project_id,
            from_node_id=from_node.knowledge_node_id,
            relationship=relationship,
            to_node_id=to_node.knowledge_node_id,
            provenance_ref=provenance_ref,
            provenance_hash=provenance_hash,
            derivation_class=derivation_class,
            created_at=now,
            updated_at=now,
            invalidated_at=None,
        )

    async def compile_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        unit_map_id: UUID,
        request_mode: str,
    ) -> dict[str, object]:
        truth = await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            unit = await self._knowledge.get_unit_map(
                uow.connection,
                project_id=project_id,
                unit_map_id=unit_map_id,
            )
            if unit is None:
                raise DdeError("NOT_FOUND", "VEKL Unit Knowledge Map not found")
            if (
                unit.invalidated_at is not None
                or unit.project_truth_hash != truth.truth_hash
            ):
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "Unit Knowledge Map is invalidated or bound to stale Project Truth",
                )
            graph = await TaskGraphRepository().get_task_graph(
                uow.connection, unit.task_graph_id
            )
            if graph is None or graph.version != unit.task_graph_version:
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "TaskGraph changed after Unit projection",
                )
            all_tasks = await MissionsRepository().list_tasks_for_graph(
                uow.connection, unit.task_graph_id
            )
            task_by_id = {task.task_id: task for task in all_tasks}
            tasks: list[Task] = []
            for task_id in unit.task_ids:
                task = task_by_id.get(task_id)
                if task is None:
                    raise DdeError(
                        "VEKL_KNOWLEDGE_STALE",
                        "Unit member no longer exists in its TaskGraph",
                    )
                tasks.append(task)
            task_edges = await TaskGraphRepository().list_edges_for_graph(
                uow.connection, unit.task_graph_id
            )
            fingerprint = await self._vekl.get_fingerprint(
                uow.connection,
                project_id=project_id,
                fingerprint_id=unit.stack_fingerprint_id,
            )
            if (
                fingerprint is None
                or fingerprint.fingerprint_hash != unit.stack_fingerprint_hash
                or fingerprint.project_truth_hash != truth.truth_hash
            ):
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "StackFingerprint changed after Unit projection",
                )
            resources = [
                resource
                for resource in await self._vekl.list_resources(
                    uow.connection, project_id=project_id
                )
                if resource.lifecycle_state in REFERENCE_LIFECYCLE
            ]
            routes = await self._knowledge.list_active_routes(
                uow.connection,
                project_id=project_id,
            )
            unit_concerns = set(self._str_list(unit.scope.get("concerns")))
            applicable_routes = [
                route for route in routes if route.concern in unit_concerns
            ]

            nodes: dict[tuple[str, str], VEKLKnowledgeNode] = {}

            def add_node(record: VEKLKnowledgeNode) -> VEKLKnowledgeNode:
                nodes[(record.node_kind, record.stable_ref)] = record
                return record

            unit_node = add_node(
                self._node_record(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    node_kind="DEVELOPMENT_UNIT_PROJECTION",
                    object_type="vekl_unit_map",
                    object_id=unit.unit_map_id,
                    stable_ref=f"unit:{unit.unit_lineage_id}:{unit.unit_revision_hash}",
                    authority_class="DERIVED_PROJECTION",
                    authority_service="engine.vekl.knowledge_service",
                    content_hash=unit.unit_map_hash,
                    project_truth_hash=truth.truth_hash,
                    metadata={
                        "unit_lineage_id": unit.unit_lineage_id,
                        "unit_revision_hash": unit.unit_revision_hash,
                        "readiness": unit.knowledge_readiness_state,
                    },
                    now=now,
                )
            )
            graph_node = add_node(
                self._node_record(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    node_kind="TASK_GRAPH",
                    object_type="task_graph",
                    object_id=graph.graph_id,
                    stable_ref=f"task-graph:{graph.graph_id}:v{graph.version}",
                    authority_class="EXECUTION_AUTHORITY_REF",
                    authority_service="engine.planning",
                    content_hash=graph.graph_hash,
                    project_truth_hash=truth.truth_hash,
                    metadata={"version": graph.version, "status": graph.status},
                    now=now,
                )
            )
            stack_node = add_node(
                self._node_record(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    node_kind="STACK_FINGERPRINT",
                    object_type="stack_fingerprint",
                    object_id=fingerprint.fingerprint_id,
                    stable_ref=f"stack:{fingerprint.fingerprint_id}",
                    authority_class="MECHANICAL_OBSERVATION",
                    authority_service="engine.vekl.stack",
                    content_hash=fingerprint.fingerprint_hash,
                    project_truth_hash=fingerprint.project_truth_hash,
                    metadata={"evidence_refs": fingerprint.evidence_refs},
                    now=now,
                )
            )
            for task in tasks:
                add_node(
                    self._node_record(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        node_kind="TASK",
                        object_type="task",
                        object_id=task.task_id,
                        stable_ref=f"task:{task.task_id}",
                        authority_class="EXECUTION_AUTHORITY_REF",
                        authority_service="engine.missions",
                        content_hash=sha256_hex(
                            canonical_json(task.model_dump(mode="json"))
                        ),
                        project_truth_hash=truth.truth_hash,
                        metadata={
                            "title": task.title,
                            "task_class": task.task_class,
                            "status": task.status,
                        },
                        now=now,
                    )
                )
            for ref, value in sorted(
                (
                    (ref, truth.constraints[ref])
                    for ref in truth.refs
                    if ref in truth.constraints
                ),
                key=lambda item: item[0],
            ):
                if ref.startswith("constitution:"):
                    kind = "PRODUCT_CONSTITUTION"
                elif ref.startswith("requirement:"):
                    kind = "REQUIREMENT"
                elif ref.startswith("edr:"):
                    kind = "EDR"
                else:
                    continue
                add_node(
                    self._node_record(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        node_kind=kind,
                        object_type=kind.lower(),
                        object_id=None,
                        stable_ref=ref,
                        authority_class="PROJECT_TRUTH",
                        authority_service="engine.truth",
                        content_hash=sha256_hex(canonical_json(value)),
                        project_truth_hash=truth.truth_hash,
                        metadata={},
                        now=now,
                    )
                )
            for contract_ref in sorted(
                set(unit.contracts_consumed) | set(unit.contracts_produced)
            ):
                add_node(
                    self._node_record(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        node_kind="CONTRACT",
                        object_type="task_graph_contract_ref",
                        object_id=None,
                        stable_ref=f"contract:{contract_ref}",
                        authority_class="DECLARED_CONTRACT_REF",
                        authority_service="engine.planning",
                        content_hash=sha256_hex(contract_ref),
                        project_truth_hash=truth.truth_hash,
                        metadata={"contract_ref": contract_ref},
                        now=now,
                    )
                )
            for ref in unit.product_experience_refs:
                if ref.startswith("frontend-contract:"):
                    node_kind = "FRONTEND_CONTRACT_OBLIGATION"
                elif ref.startswith("pxg-revision:"):
                    node_kind = "PXG_NODE"
                else:
                    continue
                add_node(
                    self._node_record(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        node_kind=node_kind,
                        object_type="product_experience_ref",
                        object_id=None,
                        stable_ref=ref,
                        authority_class="PRODUCT_EXPERIENCE_AUTHORITY_REF",
                        authority_service="engine.studio",
                        content_hash=sha256_hex(ref),
                        project_truth_hash=truth.truth_hash,
                        metadata={},
                        now=now,
                    )
                )
            for resource in resources:
                add_node(
                    self._node_record(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        node_kind="VEKL_RESOURCE",
                        object_type="vekl_resource",
                        object_id=resource.resource_id,
                        stable_ref=f"vekl-resource:{resource.resource_id}",
                        authority_class="QUALIFIED_ENGINEERING_RESOURCE",
                        authority_service="engine.vekl",
                        content_hash=resource.content_hash,
                        project_truth_hash=None,
                        metadata={
                            "resource_kind": resource.resource_kind,
                            "revision": resource.revision,
                            "source_trust": resource.source_trust,
                            "lifecycle_state": resource.lifecycle_state,
                        },
                        now=now,
                    )
                )

            edges: list[VEKLKnowledgeEdge] = []

            def edge(
                source: VEKLKnowledgeNode,
                relationship: str,
                target: VEKLKnowledgeNode,
                provenance_ref: str,
                derivation_class: str = "DETERMINISTIC",
            ) -> None:
                edges.append(
                    self._edge_record(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        from_node=source,
                        relationship=relationship,
                        to_node=target,
                        provenance_ref=provenance_ref,
                        provenance_hash=sha256_hex(provenance_ref),
                        derivation_class=derivation_class,
                        now=now,
                    )
                )

            edge(
                unit_node, "derives_from", graph_node, f"unit-map:{unit.unit_map_hash}"
            )
            edge(
                unit_node,
                "observes",
                stack_node,
                f"stack:{fingerprint.fingerprint_hash}",
            )
            for task in tasks:
                task_node = nodes[("TASK", f"task:{task.task_id}")]
                edge(unit_node, "derives_from", task_node, f"task:{task.task_id}")
            for ref in unit.constitution_refs + unit.edr_refs:
                key = (
                    "PRODUCT_CONSTITUTION"
                    if ref.startswith("constitution:")
                    else "EDR",
                    ref,
                )
                truth_node = nodes.get(key)
                if truth_node is not None:
                    edge(
                        unit_node,
                        "governed_by",
                        truth_node,
                        f"truth:{truth.truth_hash}",
                    )
            for req in unit.requirement_refs:
                for candidate in (f"requirement:{req}", req):
                    truth_node = nodes.get(("REQUIREMENT", candidate))
                    if truth_node is not None:
                        edge(
                            unit_node,
                            "governed_by",
                            truth_node,
                            f"truth:{truth.truth_hash}",
                        )
                        break
            unit_ids = set(unit.task_ids)
            for task_edge in task_edges:
                if (
                    task_edge.from_task_id in unit_ids
                    and task_edge.to_task_id in unit_ids
                ):
                    source = nodes[("TASK", f"task:{task_edge.from_task_id}")]
                    target = nodes[("TASK", f"task:{task_edge.to_task_id}")]
                    relation = (
                        "depends_on"
                        if task_edge.edge_type == "depends_on"
                        else "affects"
                    )
                    edge(
                        target if relation == "depends_on" else source,
                        relation,
                        source if relation == "depends_on" else target,
                        f"task-edge:{task_edge.edge_id}",
                    )
            for contract_ref in unit.contracts_consumed:
                contract = nodes[("CONTRACT", f"contract:{contract_ref}")]
                edge(
                    unit_node,
                    "consumes",
                    contract,
                    f"unit-contract:{unit.contract_set_hash}",
                )
            for contract_ref in unit.contracts_produced:
                contract = nodes[("CONTRACT", f"contract:{contract_ref}")]
                edge(
                    unit_node,
                    "produces",
                    contract,
                    f"unit-contract:{unit.contract_set_hash}",
                )
            for ref in unit.product_experience_refs:
                for kind in ("FRONTEND_CONTRACT_OBLIGATION", "PXG_NODE"):
                    product_node = nodes.get((kind, ref))
                    if product_node is not None:
                        edge(
                            unit_node,
                            "constrained_by",
                            product_node,
                            f"product:{unit.product_experience_hash}",
                        )
            for resource in resources:
                resource_node = nodes[
                    ("VEKL_RESOURCE", f"vekl-resource:{resource.resource_id}")
                ]
                matching = [
                    route
                    for route in applicable_routes
                    if resource.resource_kind
                    in set(self._str_list(route.policy.get("resource_kinds")))
                ]
                if matching:
                    edge(
                        resource_node,
                        "supports",
                        unit_node,
                        "route-policy:"
                        + sha256_hex(
                            canonical_json(
                                sorted(route.policy_hash for route in matching)
                            )
                        ),
                    )

            for node_record in sorted(
                nodes.values(), key=lambda item: str(item.knowledge_node_id)
            ):
                existing_node = await self._knowledge.node_by_identity(
                    uow.connection,
                    project_id=project_id,
                    node_kind=node_record.node_kind,
                    stable_ref=node_record.stable_ref,
                    content_hash=node_record.content_hash,
                    compiler_version=node_record.projection_compiler_version,
                )
                if existing_node is None:
                    await self._knowledge.insert_node(uow.connection, node_record)
            for edge_record in sorted(
                edges, key=lambda item: str(item.knowledge_edge_id)
            ):
                existing_edge = await self._knowledge.edge_by_identity(
                    uow.connection,
                    project_id=project_id,
                    from_node_id=edge_record.from_node_id,
                    relationship=edge_record.relationship,
                    to_node_id=edge_record.to_node_id,
                    provenance_hash=edge_record.provenance_hash,
                )
                if existing_edge is None:
                    await self._knowledge.insert_edge(uow.connection, edge_record)
            await uow.commit()
            node_payload = [item.model_dump(mode="json") for item in nodes.values()]
            edge_payload = [item.model_dump(mode="json") for item in edges]
            snapshot_hash = graph_snapshot_hash(node_payload, edge_payload)
            return {
                "unit_map": unit.model_dump(mode="json"),
                "nodes": sorted(
                    node_payload, key=lambda item: str(item["knowledge_node_id"])
                ),
                "edges": sorted(
                    edge_payload, key=lambda item: str(item["knowledge_edge_id"])
                ),
                "graph_snapshot_hash": snapshot_hash,
                "graph_compiler_version": GRAPH_COMPILER_VERSION,
            }

    @staticmethod
    def _lexical_score(query: str, candidate: str) -> int:
        left = set(_TOKEN_RE.findall(query.lower()))
        right = set(_TOKEN_RE.findall(candidate.lower()))
        if not left or not right:
            return 0
        return int(10_000 * len(left & right) / len(left | right))

    @staticmethod
    def _semantic_score(query: str, candidate: str) -> int:
        return int(10_000 * cosine_similarity(embed(query), embed(candidate)))

    async def resolve_knowledge(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        unit_map_id: UUID,
        task_id: UUID,
        task_signature_id: UUID,
        requested_modes: list[str],
        available_capabilities: list[str],
        available_verifiers: list[str],
        sandbox_available: bool,
        offline: bool,
        request_mode: str,
    ) -> VEKLResolutionTrace:
        graph_projection = await self.compile_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            unit_map_id=unit_map_id,
            request_mode=request_mode,
        )
        truth = await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            unit = await self._knowledge.get_unit_map(
                uow.connection,
                project_id=project_id,
                unit_map_id=unit_map_id,
            )
            if unit is None:
                raise DdeError("NOT_FOUND", "VEKL Unit Knowledge Map not found")
            if unit.knowledge_readiness_state == "EXEMPT_BY_POLICY":
                candidate_decisions: list[dict[str, object]] = []
            elif unit.knowledge_readiness_state not in {"MAPPING", "READY"}:
                raise DdeError(
                    "VEKL_KNOWLEDGE_NOT_READY",
                    "material Unit cannot resolve worker knowledge "
                    "in its current state",
                    details={"state": unit.knowledge_readiness_state},
                )
            else:
                candidate_decisions = []
            findings = await self._knowledge.list_findings_for_unit(
                uow.connection,
                project_id=project_id,
                unit_map_id=unit_map_id,
            )
            mandatory_concerns = self._mandatory_research_concerns(
                list(unit.research_questions)
            )
            satisfied_concerns = {
                finding.concern
                for finding in findings
                if finding.concern in mandatory_concerns
                and finding.classification != "DISCOVERY_ONLY"
                and finding.source_trust not in {"S7_DISCOVERY_ONLY", "S8_UNTRUSTED"}
                and not bool(finding.freshness.get("stale"))
                and bool(finding.content_hash)
            }
            unresolved = sorted(mandatory_concerns - satisfied_concerns)
            if unresolved:
                raise DdeError(
                    "VEKL_KNOWLEDGE_NOT_READY",
                    "mandatory ahead-of-work research is unresolved",
                    details={"unresolved_concerns": unresolved},
                )
            if task_id not in unit.task_ids:
                raise DdeError(
                    "VEKL_UNIT_INVALID",
                    "knowledge resolution task is not a member of the Unit",
                )
            task = await MissionsRepository().get_task(uow.connection, task_id)
            signature = await self._vekl.get_signature(
                uow.connection,
                project_id=project_id,
                signature_id=task_signature_id,
            )
            fingerprint = await self._vekl.get_fingerprint(
                uow.connection,
                project_id=project_id,
                fingerprint_id=unit.stack_fingerprint_id,
            )
            if task is None or signature is None or fingerprint is None:
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "task, signature or StackFingerprint no longer resolves",
                )
            if (
                signature.task_id != task_id
                or signature.fingerprint_id != fingerprint.fingerprint_id
                or fingerprint.fingerprint_hash != unit.stack_fingerprint_hash
                or fingerprint.project_truth_hash != truth.truth_hash
            ):
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "resolution identity no longer matches Unit/Stack/Task authority",
                )
            index = await self._context_indexes.get_index(
                uow.connection, tenant_id, project_id
            )
            envelope = resolution_envelope(
                graph_hash=str(graph_projection["graph_snapshot_hash"]),
                context_index_id=None if index is None else index.index_id,
                context_index_version=None if index is None else index.current_version,
                embedding_model_version=(
                    EMBEDDING_MODEL_VERSION
                    if index is None
                    else index.embedding_model_version
                ),
            )
            if index is not None and index.status != "ACTIVE":
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "GraphRAG may use only the active project context index",
                    details={"status": index.status},
                )

            node_rows = self._dict_list(graph_projection.get("nodes"))
            edge_rows = self._dict_list(graph_projection.get("edges"))
            unit_node_ids = {
                UUID(str(item["knowledge_node_id"]))
                for item in node_rows
                if item.get("node_kind") == "DEVELOPMENT_UNIT_PROJECTION"
                and item.get("object_id") == str(unit_map_id)
            }
            supported_node_ids = {
                UUID(str(item["from_node_id"]))
                for item in edge_rows
                if item.get("relationship") == "supports"
                and UUID(str(item["to_node_id"])) in unit_node_ids
            }
            resource_ids = {
                UUID(str(item["object_id"]))
                for item in node_rows
                if item.get("node_kind") == "VEKL_RESOURCE"
                and UUID(str(item["knowledge_node_id"])) in supported_node_ids
                and item.get("object_id") is not None
            }
            resources = [
                resource
                for resource in await self._vekl.list_resources(
                    uow.connection, project_id=project_id
                )
                if resource.resource_id in resource_ids
            ]
            routes = await self._knowledge.list_active_routes(
                uow.connection,
                project_id=project_id,
                concerns=self._str_list(unit.scope.get("concerns")),
            )
            from engine.studio.source.tables import design_sources

            admitted_ids = frozenset(
                str(row[0])
                for row in (
                    await uow.connection.execute(
                        select(design_sources.c.source_id).where(
                            design_sources.c.project_id == project_id,
                            design_sources.c.status == "AVAILABLE",
                        )
                    )
                ).all()
            )
            eligibility_context = EligibilityContext(
                project_kind=truth.project_kind,
                request_mode=request_mode,
                truth_constraints=truth.constraints,
                admitted_source_ids=admitted_ids,
                available_capabilities=frozenset(available_capabilities),
                available_verifiers=frozenset(available_verifiers),
                sandbox_available=sandbox_available,
                offline=offline,
                now=now,
            )
            query = " ".join(
                [
                    task.title,
                    task.intent,
                    *task.success_criteria,
                    *task.requirement_refs,
                ]
            )
            hard_eligible: list[dict[str, object]] = []
            truth_conflicts: list[UUID] = []
            if unit.knowledge_readiness_state != "EXEMPT_BY_POLICY":
                for resource in sorted(
                    resources, key=lambda item: str(item.resource_id)
                ):
                    matching_routes = [
                        route
                        for route in routes
                        if resource.resource_kind
                        in {
                            item
                            for item in self._str_list(
                                route.policy.get("resource_kinds")
                            )
                        }
                    ]
                    if not matching_routes:
                        continue
                    possible_modes = [
                        mode
                        for mode in requested_modes
                        if mode in resource.activation_modes
                    ]
                    if not possible_modes:
                        candidate_decisions.append(
                            {
                                "resource_id": str(resource.resource_id),
                                "revision": resource.revision,
                                "content_hash": resource.content_hash,
                                "eligibility": "REJECTED",
                                "reasons": ["ACTIVATION_MODE_UNQUALIFIED"],
                                "selected": False,
                            }
                        )
                        continue
                    source_rejection = (
                        await self._vekl_service._source_rejection_reason(
                            uow,
                            tenant_id=tenant_id,
                            project_id=project_id,
                            resource=resource,
                        )
                    )
                    for route in matching_routes:
                        mode = possible_modes[0]
                        decision = evaluate(
                            resource,
                            activation_mode=mode,
                            signature=signature,
                            context=eligibility_context,
                        )
                        reasons = list(decision.reasons)
                        if (
                            source_rejection is not None
                            and source_rejection not in reasons
                        ):
                            reasons.append(source_rejection)
                        purpose, role = selection_role(
                            resource_kind=resource.resource_kind,
                            activation_mode=mode,
                            purpose=f"{route.concern}:{route.route_slug}",
                        )
                        candidate_text = " ".join(
                            [
                                resource.title,
                                resource.publisher,
                                resource.content_excerpt,
                                str(resource.provenance.get("purpose", "")),
                            ]
                        )
                        row: dict[str, object] = {
                            "resource_id": str(resource.resource_id),
                            "revision": resource.revision,
                            "content_hash": resource.content_hash,
                            "concern": route.concern,
                            "route_id": str(route.route_id),
                            "route_policy_hash": route.policy_hash,
                            "activation_mode": mode,
                            "selection_purpose": purpose,
                            "selection_role": role,
                            "hard_score": list(decision.score),
                            "lexical_score": 0,
                            "semantic_score": 0,
                            "eligibility": "ELIGIBLE" if not reasons else "REJECTED",
                            "reasons": reasons,
                            "selected": False,
                        }
                        if reasons:
                            if "PROJECT_TRUTH_CONFLICT" in reasons:
                                truth_conflicts.append(resource.resource_id)
                            candidate_decisions.append(row)
                            continue
                        # Hybrid signals are calculated only after hard eligibility.
                        row["lexical_score"] = self._lexical_score(
                            query, candidate_text
                        )
                        row["semantic_score"] = self._semantic_score(
                            query, candidate_text
                        )
                        hard_eligible.append(row)
                        candidate_decisions.append(row)
                by_slot: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(
                    list
                )
                for row in hard_eligible:
                    by_slot[
                        (str(row["selection_purpose"]), str(row["selection_role"]))
                    ].append(row)
                for slot in sorted(by_slot):
                    choices = sorted(
                        by_slot[slot],
                        key=lambda item: (
                            self._score_tuple(item.get("hard_score")),
                            self._score_int(item.get("semantic_score")),
                            self._score_int(item.get("lexical_score")),
                            str(item["resource_id"]),
                        ),
                        reverse=True,
                    )
                    choices[0]["selected"] = True
            candidate_decisions.sort(
                key=lambda item: (
                    str(item.get("selection_purpose", "")),
                    str(item.get("selection_role", "")),
                    str(item["resource_id"]),
                )
            )

            finding_by_resource = {
                finding.resource_id: finding
                for finding in findings
                if finding.resource_id is not None
                and finding.classification == "TRUTH_CONFLICT_SIGNAL"
            }
            observation_refs: list[UUID] = []
            from engine.contracts.vekl_conflict_observation import (
                VEKLConflictObservation,
            )
            from engine.vekl.knowledge import challenge_eligibility

            for resource_id in sorted(set(truth_conflicts), key=str):
                finding = finding_by_resource.get(resource_id)
                conflict_resource = next(
                    (item for item in resources if item.resource_id == resource_id),
                    None,
                )
                if finding is None or conflict_resource is None:
                    continue
                eligibility = challenge_eligibility(
                    classification=finding.classification,
                    source_trust=finding.source_trust,
                    provenance_valid=bool(
                        conflict_resource.provenance.get("hash_verified")
                    ),
                    stale=bool(finding.freshness.get("stale")),
                    corroboration_count=len(finding.corroboration_refs),
                    deterministic_reproduction=bool(
                        finding.freshness.get("deterministic_reproduction")
                    ),
                )
                if not eligibility.eligible:
                    continue
                observation = VEKLConflictObservation(
                    observation_id=deterministic_uuid(
                        "conflict-observation",
                        {
                            "project_id": str(project_id),
                            "finding_id": str(finding.finding_id),
                            "truth_hash": truth.truth_hash,
                        },
                    ),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    resource_id=resource_id,
                    finding_id=finding.finding_id,
                    current_truth_hash=truth.truth_hash,
                    conflicting_truth_refs=list(finding.project_truth_refs),
                    conflict_keys=sorted(conflict_resource.truth_constraints),
                    source_trust=finding.source_trust,
                    freshness=finding.freshness,
                    provenance_valid=True,
                    activation_rejected=True,
                    challenge_evaluation_requested=True,
                    created_at=now,
                    updated_at=now,
                )
                existing_observations = (
                    await self._knowledge.list_conflict_observations(
                        uow.connection,
                        project_id=project_id,
                        truth_hash=truth.truth_hash,
                    )
                )
                if all(
                    item.observation_id != observation.observation_id
                    for item in existing_observations
                ):
                    await self._knowledge.insert_conflict_observation(
                        uow.connection, observation
                    )
                observation_refs.append(observation.observation_id)

            trace_payload: dict[str, object] = {
                "tenant_id": str(tenant_id),
                "project_id": str(project_id),
                "mission_id": str(unit.mission_id),
                "task_graph_id": str(unit.task_graph_id),
                "task_ids": [str(item) for item in unit.task_ids],
                "unit_map_id": str(unit.unit_map_id),
                "unit_lineage_id": unit.unit_lineage_id,
                "unit_revision_hash": unit.unit_revision_hash,
                "project_truth_hash": truth.truth_hash,
                "applicable_truth_slice_hash": unit.applicable_truth_slice_hash,
                "stack_fingerprint_hash": fingerprint.fingerprint_hash,
                "task_signature_hash": signature.signature_hash,
                "contract_set_hash": unit.contract_set_hash,
                "graph_snapshot_hash": str(graph_projection["graph_snapshot_hash"]),
                "resolution_envelope": envelope,
                "traversed_node_ids": sorted(
                    [str(item["knowledge_node_id"]) for item in node_rows]
                ),
                "traversed_edge_ids": sorted(
                    [str(item["knowledge_edge_id"]) for item in edge_rows]
                ),
                "candidate_decisions": candidate_decisions,
                "withheld_truth_conflicts": [
                    str(item) for item in sorted(set(truth_conflicts), key=str)
                ],
                "challenge_observation_refs": [
                    str(item) for item in sorted(observation_refs, key=str)
                ],
            }
            trace_hash = sha256_hex(canonical_json(trace_payload))
            existing_trace = await self._knowledge.trace_by_hash(
                uow.connection,
                project_id=project_id,
                trace_hash=trace_hash,
            )
            if existing_trace is not None:
                if unit.knowledge_readiness_state == "MAPPING":
                    await self._knowledge.set_unit_knowledge_state(
                        uow.connection,
                        project_id=project_id,
                        unit_map_id=unit.unit_map_id,
                        readiness_state="READY",
                        challenge_state=unit.challenge_state,
                        reason=None,
                        updated_at=now,
                    )
                    await uow.commit()
                return existing_trace
            trace = VEKLResolutionTrace(
                resolution_trace_id=deterministic_uuid(
                    "resolution-trace",
                    {"project_id": str(project_id), "trace_hash": trace_hash},
                ),
                trace_hash=trace_hash,
                created_at=now,
                **trace_payload,
            )
            await self._knowledge.insert_resolution_trace(uow.connection, trace)
            if unit.knowledge_readiness_state == "MAPPING":
                await self._knowledge.set_unit_knowledge_state(
                    uow.connection,
                    project_id=project_id,
                    unit_map_id=unit.unit_map_id,
                    readiness_state="READY",
                    challenge_state=unit.challenge_state,
                    reason=None,
                    updated_at=now,
                )
            await uow.commit()
            return trace

    async def record_research_finding(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        unit_map_id: UUID,
        task_refs: list[UUID],
        concern: str,
        source_id: UUID | None,
        source_artifact_id: UUID | None,
        resource_id: UUID | None,
        source_trust: str,
        source_revision: str,
        content_hash: str,
        claim: str,
        supporting_excerpt_hash: str,
        freshness: dict[str, object],
        classification: str,
        confidence: str,
        corroboration_refs: list[str],
        project_truth_refs: list[str],
        stack_refs: list[str],
        impact_hypothesis: list[str],
        request_mode: str,
    ) -> VEKLResearchFinding:
        truth = await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            unit = await self._knowledge.get_unit_map(
                uow.connection,
                project_id=project_id,
                unit_map_id=unit_map_id,
            )
            if unit is None or unit.invalidated_at is not None:
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "research finding must bind an active Unit Knowledge Map",
                )
            if unit.project_truth_hash != truth.truth_hash:
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "research finding cannot bind a Unit built from stale "
                    "Project Truth",
                )
            if not set(task_refs).issubset(set(unit.task_ids)):
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "research finding task refs must belong to the bound Unit",
                )
            if resource_id is not None:
                resource = await self._vekl.get_resource(
                    uow.connection,
                    project_id=project_id,
                    resource_id=resource_id,
                )
                if resource is None:
                    raise DdeError("NOT_FOUND", "VEKL resource not found")
                if (
                    resource.content_hash != content_hash
                    or resource.revision != source_revision
                ):
                    raise DdeError(
                        "VEKL_SOURCE_NOT_ADMITTED",
                        "research finding must bind the exact qualified resource "
                        "revision",
                    )
                source_id = resource.source_id
                source_artifact_id = resource.source_artifact_id
                source_trust = resource.source_trust
            finding_payload = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "unit_map_id": unit_map_id,
                "task_refs": sorted(task_refs, key=str),
                "concern": concern,
                "source_id": source_id,
                "source_artifact_id": source_artifact_id,
                "resource_id": resource_id,
                "source_trust": source_trust,
                "source_revision": source_revision,
                "content_hash": content_hash,
                "claim": claim,
                "supporting_excerpt_hash": supporting_excerpt_hash,
                "freshness": freshness,
                "classification": classification,
                "confidence": confidence,
                "corroboration_refs": sorted(corroboration_refs),
                "project_truth_refs": sorted(project_truth_refs),
                "stack_refs": sorted(stack_refs),
                "impact_hypothesis": impact_hypothesis,
            }
            finding = VEKLResearchFinding(
                finding_id=deterministic_uuid(
                    "research-finding",
                    {
                        **finding_payload,
                        "tenant_id": str(tenant_id),
                        "project_id": str(project_id),
                        "unit_map_id": str(unit_map_id),
                        "task_refs": [str(item) for item in sorted(task_refs, key=str)],
                        "source_id": None if source_id is None else str(source_id),
                        "source_artifact_id": (
                            None
                            if source_artifact_id is None
                            else str(source_artifact_id)
                        ),
                        "resource_id": None
                        if resource_id is None
                        else str(resource_id),
                    },
                ),
                created_at=now,
                updated_at=now,
                **finding_payload,
            )
            existing = await self._knowledge.get_finding(
                uow.connection,
                project_id=project_id,
                finding_id=finding.finding_id,
            )
            if existing is not None:
                return existing
            await self._knowledge.insert_finding(uow.connection, finding)
            await uow.commit()
            return finding

    async def create_truth_challenge(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        task_id: UUID | None,
        finding_ids: list[UUID],
        challenge_class: str,
        severity: str,
        conflict: dict[str, object],
        confidence: dict[str, object],
        impact: dict[str, object],
        proposal: dict[str, object],
        decision_analysis: dict[str, object],
        reopen_conditions: list[str],
        requested_by: UUID,
        idempotency_key: str,
        request_mode: str,
    ) -> VEKLTruthChallenge:
        truth = await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        validate_truth_patch(proposal)
        if not finding_ids:
            raise DdeError(
                "VEKL_CHALLENGE_INELIGIBLE",
                "TruthChallenge requires at least one qualified research finding",
            )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            mission = await self._missions.get_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                uow=uow,
            )
            task = None
            if task_id is not None:
                task = await self._missions.get_task(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=task_id,
                    uow=uow,
                )
                if task.mission_id != mission_id:
                    raise DdeError(
                        "TENANT_SCOPE_VIOLATION",
                        "TruthChallenge task must belong to the addressed mission",
                    )
            findings: list[VEKLResearchFinding] = []
            for finding_id in sorted(set(finding_ids), key=str):
                finding = await self._knowledge.get_finding(
                    uow.connection,
                    project_id=project_id,
                    finding_id=finding_id,
                )
                if finding is None:
                    raise DdeError("NOT_FOUND", "TruthChallenge finding not found")
                findings.append(finding)
            eligible: list[dict[str, object]] = []
            for finding in findings:
                deterministic_reproduction = bool(
                    finding.freshness.get("deterministic_reproduction")
                )
                result = challenge_eligibility(
                    classification=finding.classification,
                    source_trust=finding.source_trust,
                    provenance_valid=bool(finding.content_hash),
                    stale=bool(finding.freshness.get("stale")),
                    corroboration_count=len(finding.corroboration_refs),
                    deterministic_reproduction=deterministic_reproduction,
                )
                eligible.append(
                    {
                        "finding_id": str(finding.finding_id),
                        "eligible": result.eligible,
                        "reason": result.reason,
                    }
                )
            if not any(bool(item["eligible"]) for item in eligible):
                raise DdeError(
                    "VEKL_CHALLENGE_INELIGIBLE",
                    "research evidence does not meet deterministic challenge threshold",
                    details={"findings": eligible},
                )
            unit_readiness_before: dict[str, dict[str, object]] = {}
            for finding in findings:
                unit = await self._knowledge.get_unit_map(
                    uow.connection,
                    project_id=project_id,
                    unit_map_id=finding.unit_map_id,
                )
                if unit is None or unit.invalidated_at is not None:
                    raise DdeError(
                        "VEKL_CHALLENGE_INELIGIBLE",
                        "TruthChallenge finding belongs to a stale/missing Unit",
                        details={"finding_id": str(finding.finding_id)},
                    )
                unit_readiness_before[str(unit.unit_map_id)] = {
                    "knowledge_readiness_state": unit.knowledge_readiness_state,
                    "challenge_state": unit.challenge_state,
                }
            evidence = {
                "finding_ids": [str(item.finding_id) for item in findings],
                "eligibility": eligible,
                "project_truth_refs": sorted(
                    {ref for item in findings for ref in item.project_truth_refs}
                ),
                "source_revisions": [
                    {
                        "finding_id": str(item.finding_id),
                        "source_revision": item.source_revision,
                        "content_hash": item.content_hash,
                        "source_trust": item.source_trust,
                    }
                    for item in findings
                ],
                "unit_readiness_before": unit_readiness_before,
            }
            challenge_payload = {
                "tenant_id": str(tenant_id),
                "project_id": str(project_id),
                "mission_id": str(mission_id),
                "task_id": None if task_id is None else str(task_id),
                "challenge_class": challenge_class,
                "severity": severity,
                "current_truth_hash": truth.truth_hash,
                "evidence": evidence,
                "conflict": conflict,
                "confidence": confidence,
                "impact": impact,
                "proposal": proposal,
                "decision_analysis": decision_analysis,
                "required_role": TRUTH_DECISION_ROLE,
                "reopen_conditions": reopen_conditions,
            }
            challenge_hash = sha256_hex(canonical_json(challenge_payload))
            prior = await self._knowledge.challenge_by_hash(
                uow.connection,
                project_id=project_id,
                challenge_hash=challenge_hash,
            )
            if prior is not None:
                return prior
            proposed_delta_hash = sha256_hex(canonical_json(proposal))
            evidence_bundle_hash = sha256_hex(canonical_json(evidence))
            impact_analysis_hash = sha256_hex(canonical_json(impact))
            migration_plan_hash = sha256_hex(
                canonical_json(proposal.get("migration_plan", {}))
            )
            verification_plan_hash = sha256_hex(
                canonical_json(proposal.get("verification_plan", {}))
            )
            scope_payload: dict[str, object] = {
                "decision_class": TRUTH_DECISION_CLASS,
                "reviewer_class": TRUTH_REVIEWER_CLASS,
                "challenge_hash": challenge_hash,
                "current_truth_hash": truth.truth_hash,
                "proposed_delta_hash": proposed_delta_hash,
                "evidence_bundle_hash": evidence_bundle_hash,
                "impact_analysis_hash": impact_analysis_hash,
                "migration_plan_hash": migration_plan_hash,
                "verification_plan_hash": verification_plan_hash,
                "proposal": proposal,
            }
            scope_hash = approval_scope_hash(
                approval_type="project_truth_change",
                mission_id=mission_id,
                task_id=task_id,
                payload=scope_payload,
            )
            approval = await self._approvals.request(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                approval_type="project_truth_change",
                scope_hash=scope_hash,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                task_id=task_id,
                required_role=TRUTH_DECISION_ROLE,
                evidence_refs=[f"vekl-finding:{item.finding_id}" for item in findings],
                suggested_decision=canonical_json(scope_payload),
                uow=uow,
            )
            challenge = VEKLTruthChallenge(
                challenge_id=deterministic_uuid(
                    "truth-challenge",
                    {"project_id": str(project_id), "challenge_hash": challenge_hash},
                ),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
                challenge_class=challenge_class,
                severity=severity,
                status="REVIEW_REQUIRED",
                current_truth_hash=truth.truth_hash,
                evidence=evidence,
                conflict=conflict,
                confidence=confidence,
                impact=impact,
                proposal=proposal,
                decision_analysis={
                    **decision_analysis,
                    "canon_decision_preimage": {
                        "decision_class": TRUTH_DECISION_CLASS,
                        "reviewer_class": TRUTH_REVIEWER_CLASS,
                        "current_project_truth_hash": truth.truth_hash,
                        "proposed_delta_hash": proposed_delta_hash,
                        "evidence_bundle_hash": evidence_bundle_hash,
                        "impact_analysis_hash": impact_analysis_hash,
                        "migration_plan_hash": migration_plan_hash,
                        "verification_plan_hash": verification_plan_hash,
                    },
                },
                approval_id=approval.approval_id,
                required_role=TRUTH_DECISION_ROLE,
                decision=None,
                decision_reason=None,
                decided_at=None,
                reopen_conditions=reopen_conditions,
                challenge_hash=challenge_hash,
                created_at=now,
                updated_at=now,
            )
            await self._knowledge.insert_challenge(uow.connection, challenge)
            for finding in findings:
                link = VEKLTruthChallengeFinding(
                    challenge_finding_id=deterministic_uuid(
                        "truth-challenge-finding",
                        {
                            "project_id": str(project_id),
                            "challenge_id": str(challenge.challenge_id),
                            "finding_id": str(finding.finding_id),
                        },
                    ),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    challenge_id=challenge.challenge_id,
                    finding_id=finding.finding_id,
                    created_at=now,
                    updated_at=now,
                )
                await self._knowledge.insert_challenge_finding(uow.connection, link)
            if severity == "CRITICAL":
                for unit_id_text in sorted(unit_readiness_before):
                    await self._knowledge.set_unit_knowledge_state(
                        uow.connection,
                        project_id=project_id,
                        unit_map_id=UUID(unit_id_text),
                        readiness_state="BLOCKED",
                        challenge_state=f"REVIEW_REQUIRED:{challenge.challenge_id}",
                        reason=f"CANON_CHALLENGE:{challenge.challenge_id}",
                        updated_at=now,
                    )
            if severity == "CRITICAL" and task is not None:
                if task.status != "BLOCKED_ON_DECISION":
                    await self._missions.transition_task(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        task_id=task.task_id,
                        target_status="BLOCKED_ON_DECISION",
                        lock_version=task.lock_version,
                        uow=uow,
                    )
                if mission.status == "ACTIVE":
                    await self._missions.transition_mission(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        mission_id=mission_id,
                        target_status="PARTIAL",
                        lock_version=mission.lock_version,
                        uow=uow,
                    )
            await uow.commit()
            return challenge

    async def _apply_truth_patch(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        proposal: dict[str, object],
        decided_by: UUID,
        uow: object,
    ) -> dict[str, object]:
        from engine.truth.db import PostgresUnitOfWork

        if not isinstance(uow, PostgresUnitOfWork):
            raise TypeError("uow must be PostgresUnitOfWork")
        kind = validate_truth_patch(proposal)
        patch = proposal.get("exact_truth_patch")
        if not isinstance(patch, dict):
            raise DdeError(
                "VEKL_TRUTH_PATCH_INVALID", "exact_truth_patch must be object"
            )

        def required_str(name: str) -> str:
            value = patch.get(name)
            if not isinstance(value, str) or not value.strip():
                raise DdeError(
                    "VEKL_TRUTH_PATCH_INVALID",
                    f"exact truth patch requires non-empty {name}",
                )
            return value

        def string_list(name: str) -> list[str]:
            value = patch.get(name)
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise DdeError(
                    "VEKL_TRUTH_PATCH_INVALID",
                    f"exact truth patch requires string list {name}",
                )
            return list(value)

        def uuid_value(name: str) -> UUID:
            value = patch.get(name)
            try:
                return UUID(str(value))
            except (ValueError, TypeError) as exc:
                raise DdeError(
                    "VEKL_TRUTH_PATCH_INVALID",
                    f"exact truth patch requires UUID {name}",
                ) from exc

        if kind == "PRODUCT_CONSTITUTION_REVISION":
            constitution = await self._truth_service.publish_constitution(
                tenant_id=tenant_id,
                project_id=project_id,
                body_markdown=required_str("body_markdown"),
                uow=uow,
            )
            return {"kind": kind, "version_id": str(constitution.version_id)}
        if kind in {"REQUIREMENT_ADD", "REQUIREMENT_AMEND"}:
            requirement = await self._truth_service.draft_requirement(
                tenant_id=tenant_id,
                project_id=project_id,
                slug=required_str("slug"),
                statement=required_str("statement"),
                constraints=string_list("constraints"),
                acceptance_conditions=string_list("acceptance_conditions"),
                supersedes_id=(
                    uuid_value("supersedes_id") if kind == "REQUIREMENT_AMEND" else None
                ),
                uow=uow,
            )
            requirement = await self._truth_service.approve_requirement(
                tenant_id=tenant_id,
                project_id=project_id,
                requirement_id=requirement.requirement_id,
                uow=uow,
            )
            return {
                "kind": kind,
                "requirement_id": str(requirement.requirement_id),
            }
        if kind == "REQUIREMENT_RETIRE":
            retired_requirement = await self._truth_service.retire_requirement(
                tenant_id=tenant_id,
                project_id=project_id,
                requirement_id=uuid_value("requirement_id"),
                uow=uow,
            )
            return {
                "kind": kind,
                "requirement_id": str(retired_requirement.requirement_id),
            }
        if kind in {"EDR_ADD", "EDR_SUPERSEDE"}:
            edr = await self._truth_service.propose_edr(
                tenant_id=tenant_id,
                project_id=project_id,
                slug=required_str("slug"),
                context=required_str("context"),
                alternatives=string_list("alternatives"),
                decision=required_str("decision"),
                rationale=required_str("rationale"),
                consequences=string_list("consequences"),
                affected_requirement_slugs=string_list("affected_requirement_slugs"),
                supersedes_id=(
                    uuid_value("supersedes_id") if kind == "EDR_SUPERSEDE" else None
                ),
                uow=uow,
            )
            edr = await self._truth_service.accept_edr(
                tenant_id=tenant_id,
                project_id=project_id,
                edr_id=edr.edr_id,
                decided_by_principal=decided_by,
                uow=uow,
            )
            return {"kind": kind, "edr_id": str(edr.edr_id)}
        raise DdeError("VEKL_TRUTH_PATCH_INVALID", "unsupported truth patch")

    async def decide_truth_challenge(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        challenge_id: UUID,
        decision: str,
        reason: str,
        decided_by: UUID,
        request_mode: str,
    ) -> VEKLTruthChallenge:
        normalized = decision.upper()
        if normalized not in {"ACCEPT", "DEFER", "REJECT", "REQUEST_MORE_EVIDENCE"}:
            raise DdeError(
                "VEKL_CHALLENGE_DECISION_INVALID",
                "TruthChallenge decision must be ACCEPT, DEFER, REJECT, "
                "or REQUEST_MORE_EVIDENCE",
            )
        truth = await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            challenge = await self._knowledge.get_challenge(
                uow.connection,
                project_id=project_id,
                challenge_id=challenge_id,
            )
            if challenge is None:
                raise DdeError("NOT_FOUND", "TruthChallenge not found")
            if challenge.status != "REVIEW_REQUIRED" or challenge.approval_id is None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "TruthChallenge is not awaiting a governed decision",
                    details={"status": challenge.status},
                )
            if truth.truth_hash != challenge.current_truth_hash:
                await self._knowledge.update_challenge(
                    uow.connection,
                    project_id=project_id,
                    challenge_id=challenge_id,
                    fields={"status": "STALE", "updated_at": now},
                )
                await uow.commit()
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "Project Truth changed after challenge creation; "
                    "re-evaluate evidence",
                )
            if challenge.required_role != TRUTH_DECISION_ROLE:
                raise DdeError(
                    "FORBIDDEN",
                    "TruthChallenge is not bound to owner-only canon authority",
                )
            approval = await self._approvals.get_approval(
                tenant_id=tenant_id,
                project_id=project_id,
                approval_id=challenge.approval_id,
                uow=uow,
            )
            approval_decision = "APPROVED" if normalized == "ACCEPT" else "REJECTED"
            await self._approvals.decide(
                tenant_id=tenant_id,
                project_id=project_id,
                approval_id=approval.approval_id,
                decision=approval_decision,
                decided_by=decided_by,
                rationale=reason,
                scope_hash=approval.scope_hash,
                uow=uow,
            )
            truth_change: dict[str, object] | None = None
            next_status = "REJECTED"
            if normalized == "DEFER":
                next_status = "DEFERRED"
            elif normalized == "REQUEST_MORE_EVIDENCE":
                next_status = "MORE_EVIDENCE_REQUIRED"
            elif normalized == "ACCEPT":
                truth_change = await self._apply_truth_patch(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    proposal=challenge.proposal,
                    decided_by=decided_by,
                    uow=uow,
                )
                changed = await self._vekl_service._truth_snapshot(
                    uow,
                    tenant_id=tenant_id,
                    project_id=project_id,
                )
                next_status = "TRUTH_CHANGED"
                units = await self._knowledge.list_active_unit_maps(
                    uow.connection,
                    project_id=project_id,
                )
                for unit in units:
                    if unit.project_truth_hash == changed.truth_hash:
                        continue
                    await self._knowledge.invalidate_unit_map(
                        uow.connection,
                        project_id=project_id,
                        unit_map_id=unit.unit_map_id,
                        reason="PROJECT_TRUTH_CHANGED",
                        invalidated_at=now,
                    )
                    invalidation = VEKLGraphInvalidation(
                        graph_invalidation_id=deterministic_uuid(
                            "truth-change-invalidation",
                            {
                                "project_id": str(project_id),
                                "unit_map_id": str(unit.unit_map_id),
                                "previous_truth_hash": unit.project_truth_hash,
                                "observed_truth_hash": changed.truth_hash,
                            },
                        ),
                        tenant_id=tenant_id,
                        project_id=project_id,
                        unit_map_id=unit.unit_map_id,
                        manifest_id=None,
                        resolution_trace_id=None,
                        reason_code="PROJECT_TRUTH_CHANGED",
                        detail={
                            "challenge_id": str(challenge_id),
                            "truth_change": truth_change,
                        },
                        observed_truth_hash=changed.truth_hash,
                        previous_hash=unit.project_truth_hash,
                        observed_hash=changed.truth_hash,
                        created_at=now,
                        updated_at=now,
                    )
                    await self._knowledge.insert_graph_invalidation(
                        uow.connection, invalidation
                    )
            await self._knowledge.update_challenge(
                uow.connection,
                project_id=project_id,
                challenge_id=challenge_id,
                fields={
                    "status": next_status,
                    "decision": normalized,
                    "decision_reason": reason,
                    "decided_at": now,
                    "updated_at": now,
                    "decision_analysis": {
                        **challenge.decision_analysis,
                        "truth_change": truth_change,
                        "owner_decision_record": {
                            "decision_class": TRUTH_DECISION_CLASS,
                            "challenge_id": str(challenge.challenge_id),
                            "project_id": str(project_id),
                            "reviewer_class": TRUTH_REVIEWER_CLASS,
                            "reviewer_principal_id": str(decided_by),
                            "current_project_truth_hash": challenge.current_truth_hash,
                            "proposed_delta_hash": sha256_hex(
                                canonical_json(challenge.proposal)
                            ),
                            "evidence_bundle_hash": sha256_hex(
                                canonical_json(challenge.evidence)
                            ),
                            "impact_analysis_hash": sha256_hex(
                                canonical_json(challenge.impact)
                            ),
                            "migration_plan_hash": sha256_hex(
                                canonical_json(
                                    challenge.proposal.get("migration_plan", {})
                                )
                            ),
                            "verification_plan_hash": sha256_hex(
                                canonical_json(
                                    challenge.proposal.get("verification_plan", {})
                                )
                            ),
                            "decision": normalized,
                            "decision_reason": reason,
                        },
                    },
                },
            )
            if normalized in {"DEFER", "REJECT"}:
                before = challenge.evidence.get("unit_readiness_before", {})
                if isinstance(before, dict):
                    for unit_id_text, raw_state in sorted(before.items()):
                        if not isinstance(raw_state, dict):
                            continue
                        prior_readiness = raw_state.get("knowledge_readiness_state")
                        prior_challenge = raw_state.get("challenge_state")
                        if not isinstance(prior_readiness, str) or not isinstance(
                            prior_challenge, str
                        ):
                            continue
                        try:
                            unit_id = UUID(unit_id_text)
                        except ValueError:
                            continue
                        current_unit = await self._knowledge.get_unit_map(
                            uow.connection,
                            project_id=project_id,
                            unit_map_id=unit_id,
                        )
                        if (
                            current_unit is not None
                            and current_unit.invalidated_at is None
                            and current_unit.challenge_state
                            == f"REVIEW_REQUIRED:{challenge.challenge_id}"
                        ):
                            await self._knowledge.set_unit_knowledge_state(
                                uow.connection,
                                project_id=project_id,
                                unit_map_id=unit_id,
                                readiness_state=prior_readiness,
                                challenge_state=prior_challenge,
                                reason=None,
                                updated_at=now,
                            )
            if normalized != "REQUEST_MORE_EVIDENCE" and challenge.task_id is not None:
                task = await self._missions.get_task(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=challenge.task_id,
                    uow=uow,
                )
                if task.status == "BLOCKED_ON_DECISION":
                    await self._missions.transition_task(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        task_id=task.task_id,
                        target_status="READY",
                        lock_version=task.lock_version,
                        uow=uow,
                    )
            mission = await self._missions.get_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=challenge.mission_id,
                uow=uow,
            )
            if normalized != "REQUEST_MORE_EVIDENCE" and mission.status == "PARTIAL":
                await self._missions.transition_mission(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission.mission_id,
                    target_status="ACTIVE",
                    lock_version=mission.lock_version,
                    uow=uow,
                )
            await uow.commit()
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            updated = await self._knowledge.get_challenge(
                uow.connection,
                project_id=project_id,
                challenge_id=challenge_id,
            )
            if updated is None:
                raise DdeError("NOT_FOUND", "TruthChallenge disappeared after decision")
            return updated

    async def reopen_truth_challenge(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        challenge_id: UUID,
        additional_finding_ids: list[UUID],
        trigger_reason: str,
        requested_by: UUID,
        idempotency_key: str,
        request_mode: str,
    ) -> VEKLTruthChallenge:
        """Open a fresh governed review after new evidence or reconsideration.

        Prior challenge history remains intact. The successor hash binds the prior
        challenge and explicit reopen trigger, so exact retries replay safely.
        """
        reason = trigger_reason.strip()
        if not reason:
            raise DdeError(
                "VALIDATION_FAILED",
                "TruthChallenge reopen requires a material trigger/reason",
            )
        truth = await self._truth(
            tenant_id=tenant_id, project_id=project_id, request_mode=request_mode
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            prior = await self._knowledge.get_challenge(
                uow.connection, project_id=project_id, challenge_id=challenge_id
            )
            if prior is None:
                raise DdeError("NOT_FOUND", "TruthChallenge not found")
            if prior.status not in {
                "DEFERRED",
                "REJECTED",
                "MORE_EVIDENCE_REQUIRED",
            }:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "only deferred/rejected/evidence-required challenges may reopen",
                    details={"status": prior.status},
                )
            if prior.current_truth_hash != truth.truth_hash:
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "Project Truth changed; reopen requires fresh conflict evaluation",
                )
            raw_ids = prior.evidence.get("finding_ids", [])
            prior_ids = (
                [UUID(item) for item in raw_ids if isinstance(item, str)]
                if isinstance(raw_ids, list)
                else []
            )
            finding_ids = sorted(set(prior_ids) | set(additional_finding_ids), key=str)
            mission_id = prior.mission_id
            task_id = prior.task_id
            challenge_class = prior.challenge_class
            severity = prior.severity
            conflict = dict(prior.conflict)
            confidence = dict(prior.confidence)
            impact = dict(prior.impact)
            proposal = dict(prior.proposal)
            reopen_conditions = list(prior.reopen_conditions)
            decision_analysis = {
                **prior.decision_analysis,
                "reopened_from_challenge_id": str(prior.challenge_id),
                "reopen_trigger_reason": reason,
                "additional_finding_ids": [
                    str(item) for item in sorted(set(additional_finding_ids), key=str)
                ],
            }
        return await self.create_truth_challenge(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            task_id=task_id,
            finding_ids=finding_ids,
            challenge_class=challenge_class,
            severity=severity,
            conflict=conflict,
            confidence=confidence,
            impact=impact,
            proposal=proposal,
            decision_analysis=decision_analysis,
            reopen_conditions=reopen_conditions,
            requested_by=requested_by,
            idempotency_key=idempotency_key,
            request_mode=request_mode,
        )

    async def require_fresh_trace(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        resolution_trace_id: UUID,
        request_mode: str,
    ) -> VEKLResolutionTrace:
        trace: VEKLResolutionTrace | None = None
        unit: VEKLUnitMap | None = None
        signature: TaskSignature | None = None
        fingerprint: StackFingerprint | None = None
        index = None
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            trace = await self._knowledge.get_resolution_trace(
                uow.connection,
                project_id=project_id,
                resolution_trace_id=resolution_trace_id,
            )
            if trace is None:
                raise DdeError("NOT_FOUND", "VEKL KnowledgeResolutionTrace not found")
            unit = await self._knowledge.get_unit_map(
                uow.connection,
                project_id=project_id,
                unit_map_id=trace.unit_map_id,
            )
            if unit is None or unit.invalidated_at is not None:
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "resolution trace refers to an invalidated Unit",
                )
            fingerprint = await self._vekl.get_fingerprint(
                uow.connection,
                project_id=project_id,
                fingerprint_id=unit.stack_fingerprint_id,
            )
            task_id = trace.task_ids[0] if trace.task_ids else None
            if task_id is None:
                raise DdeError("VEKL_KNOWLEDGE_STALE", "resolution trace has no task")
            signatures = await uow.connection.execute(
                select(
                    __import__(
                        "engine.vekl.tables", fromlist=["task_signatures"]
                    ).task_signatures
                ).where(
                    __import__(
                        "engine.vekl.tables", fromlist=["task_signatures"]
                    ).task_signatures.c.project_id
                    == project_id,
                    __import__(
                        "engine.vekl.tables", fromlist=["task_signatures"]
                    ).task_signatures.c.task_id
                    == task_id,
                    __import__(
                        "engine.vekl.tables", fromlist=["task_signatures"]
                    ).task_signatures.c.signature_hash
                    == trace.task_signature_hash,
                )
            )
            row = signatures.mappings().first()
            signature = None if row is None else TaskSignature.model_validate(dict(row))
            index = await self._context_indexes.get_index(
                uow.connection, tenant_id, project_id
            )
            invalidations = await self._knowledge.list_invalidations(
                uow.connection,
                project_id=project_id,
                unit_map_id=trace.unit_map_id,
            )
            if invalidations:
                raise DdeError(
                    "VEKL_KNOWLEDGE_STALE",
                    "resolution trace has a recorded graph invalidation",
                    details={"reason": invalidations[-1].reason_code},
                )
        truth = await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        if trace is None or unit is None:
            raise DdeError(
                "VEKL_KNOWLEDGE_STALE",
                "resolution trace lost its Unit binding during freshness check",
            )
        if (
            truth.truth_hash != trace.project_truth_hash
            or unit.project_truth_hash != trace.project_truth_hash
            or unit.unit_revision_hash != trace.unit_revision_hash
            or unit.unit_lineage_id != trace.unit_lineage_id
            or unit.contract_set_hash != trace.contract_set_hash
            or unit.retrieval_route_policy_hash != RETRIEVAL_ROUTE_POLICY_HASH
            or fingerprint is None
            or fingerprint.fingerprint_hash != trace.stack_fingerprint_hash
            or signature is None
        ):
            raise DdeError(
                "VEKL_KNOWLEDGE_STALE",
                "resolution trace no longer matches current Truth/Unit/Stack/Signature",
            )
        projection = await self.compile_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            unit_map_id=trace.unit_map_id,
            request_mode=request_mode,
        )
        if projection["graph_snapshot_hash"] != trace.graph_snapshot_hash:
            raise DdeError(
                "VEKL_KNOWLEDGE_STALE",
                "knowledge graph changed after resolution",
            )
        expected_envelope = resolution_envelope(
            graph_hash=trace.graph_snapshot_hash,
            context_index_id=None if index is None else index.index_id,
            context_index_version=None if index is None else index.current_version,
            embedding_model_version=(
                EMBEDDING_MODEL_VERSION
                if index is None
                else index.embedding_model_version
            ),
        )
        if expected_envelope != trace.resolution_envelope:
            raise DdeError(
                "VEKL_KNOWLEDGE_STALE",
                "GraphRAG determinism envelope changed after resolution",
            )
        return trace

    async def unit_context_for_trace(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        resolution_trace_id: UUID,
        request_mode: str,
    ) -> dict[str, object]:
        """Return the bounded Unit capsule metadata for one fresh resolution trace."""
        trace = await self.require_fresh_trace(
            tenant_id=tenant_id,
            project_id=project_id,
            resolution_trace_id=resolution_trace_id,
            request_mode=request_mode,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            unit = await self._knowledge.get_unit_map(
                uow.connection, project_id=project_id, unit_map_id=trace.unit_map_id
            )
        if unit is None or unit.invalidated_at is not None:
            raise DdeError(
                "VEKL_KNOWLEDGE_STALE",
                "fresh resolution trace lost its active Unit projection",
            )
        selected = [
            {
                "resource_id": str(item.get("resource_id", "")),
                "selection_purpose": str(item.get("selection_purpose", "")),
                "selection_role": str(item.get("selection_role", "")),
                "concern": str(item.get("concern", "")),
            }
            for item in trace.candidate_decisions
            if item.get("selected") is True
        ]
        selected.sort(
            key=lambda item: (
                item["selection_purpose"],
                item["selection_role"],
                item["resource_id"],
            )
        )
        return {
            "unit_map_id": str(unit.unit_map_id),
            "unit_lineage_id": unit.unit_lineage_id,
            "unit_revision_hash": unit.unit_revision_hash,
            "objective": unit.objective,
            "scope": dict(unit.scope),
            "requirement_refs": list(unit.requirement_refs),
            "edr_refs": list(unit.edr_refs),
            "constitution_refs": list(unit.constitution_refs),
            "contracts_consumed": list(unit.contracts_consumed),
            "contracts_produced": list(unit.contracts_produced),
            "product_experience_refs": list(unit.product_experience_refs),
            "security_refs": list(unit.security_refs),
            "eventuality_refs": list(unit.eventuality_refs),
            "research_questions": list(unit.research_questions),
            "required_verifiers": list(unit.required_verifiers),
            "graph_snapshot_hash": trace.graph_snapshot_hash,
            "resolution_trace_id": str(trace.resolution_trace_id),
            "resolution_trace_hash": trace.trace_hash,
            "selected_resource_roles": selected,
            "withheld_truth_conflicts": [
                str(item) for item in trace.withheld_truth_conflicts
            ],
            "resolution_envelope": dict(trace.resolution_envelope),
        }

    async def bind_execution(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        resolution_trace_id: UUID,
        manifest_id: UUID,
        manifest_hash: str,
        context_package_id: UUID | None,
        context_package_hash: str | None,
        context_capsule_hashes: list[str],
        request_mode: str,
    ) -> VEKLExecutionKnowledgeBinding:
        """Append one immutable execution-knowledge checkpoint.

        Resolution traces are never updated. Activation and final context admission are
        represented as separate append-only bindings keyed by trace + stage.
        """
        current = await self.require_fresh_trace(
            tenant_id=tenant_id,
            project_id=project_id,
            resolution_trace_id=resolution_trace_id,
            request_mode=request_mode,
        )
        manifest = await self._vekl_service.get_manifest(
            tenant_id=tenant_id,
            project_id=project_id,
            manifest_id=manifest_id,
        )
        if manifest.manifest_hash != manifest_hash:
            raise DdeError(
                "VEKL_RESOLUTION_MISMATCH",
                "execution binding manifest hash does not match persisted manifest",
            )
        if context_package_id is None and context_package_hash is not None:
            raise DdeError(
                "VEKL_RESOLUTION_MISMATCH",
                "context hash cannot be supplied without a context package id",
            )
        if context_package_id is not None and not context_package_hash:
            raise DdeError(
                "VEKL_RESOLUTION_MISMATCH",
                "context package binding requires its immutable assembly hash",
            )
        stage = (
            "CONTEXT_BOUND" if context_package_id is not None else "ACTIVATION_BOUND"
        )
        envelope_hash = sha256_hex(canonical_json(current.resolution_envelope))
        route_policy_hash = str(
            current.resolution_envelope.get(
                "retrieval_route_policy_hash", RETRIEVAL_ROUTE_POLICY_HASH
            )
        )
        worker_delivery_hash = sha256_hex(
            canonical_json(
                {
                    "resolution_trace_hash": current.trace_hash,
                    "manifest_hash": manifest_hash,
                    "context_package_hash": context_package_hash,
                    "context_capsule_hashes": sorted(set(context_capsule_hashes)),
                }
            )
        )
        payload = {
            "resolution_trace_id": str(resolution_trace_id),
            "binding_stage": stage,
            "project_truth_hash": current.project_truth_hash,
            "unit_lineage_id": current.unit_lineage_id,
            "unit_revision_hash": current.unit_revision_hash,
            "graph_revision_hash": current.graph_snapshot_hash,
            "graph_neighbourhood_hash": current.graph_snapshot_hash,
            "applicable_contract_fingerprints": [current.contract_set_hash],
            "technical_stack_fingerprint": current.stack_fingerprint_hash,
            "knowledge_route_policy_hash": route_policy_hash,
            "determinism_envelope_hash": envelope_hash,
            "activation_manifest_id": str(manifest_id),
            "activation_manifest_hash": manifest_hash,
            "context_package_id": (
                None if context_package_id is None else str(context_package_id)
            ),
            "context_package_hash": context_package_hash,
            "context_capsule_hashes": sorted(set(context_capsule_hashes)),
            "worker_delivery_hash": worker_delivery_hash,
        }
        binding_hash = sha256_hex(canonical_json(payload))
        record = VEKLExecutionKnowledgeBinding(
            execution_binding_id=deterministic_uuid(
                "execution-knowledge-binding",
                {"project_id": str(project_id), "binding_hash": binding_hash},
            ),
            tenant_id=tenant_id,
            project_id=project_id,
            resolution_trace_id=resolution_trace_id,
            binding_stage=stage,
            project_truth_hash=current.project_truth_hash,
            unit_lineage_id=current.unit_lineage_id,
            unit_revision_hash=current.unit_revision_hash,
            graph_revision_hash=current.graph_snapshot_hash,
            graph_neighbourhood_hash=current.graph_snapshot_hash,
            applicable_contract_fingerprints=[current.contract_set_hash],
            technical_stack_fingerprint=current.stack_fingerprint_hash,
            knowledge_route_policy_hash=route_policy_hash,
            determinism_envelope_hash=envelope_hash,
            activation_manifest_id=manifest_id,
            activation_manifest_hash=manifest_hash,
            context_package_id=context_package_id,
            context_package_hash=context_package_hash,
            context_capsule_hashes=sorted(set(context_capsule_hashes)),
            worker_delivery_hash=worker_delivery_hash,
            binding_hash=binding_hash,
            created_at=datetime.now(UTC),
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            existing = await self._knowledge.execution_binding_for_stage(
                uow.connection,
                project_id=project_id,
                resolution_trace_id=resolution_trace_id,
                binding_stage=stage,
            )
            if existing is not None:
                if existing.binding_hash != binding_hash:
                    raise DdeError(
                        "VEKL_RESOLUTION_MISMATCH",
                        (
                            "immutable execution stage is already bound to different "
                            "context"
                        ),
                        details={"binding_stage": stage},
                    )
                return existing
            await self._knowledge.insert_execution_binding(uow.connection, record)
            await uow.commit()
        return record

    async def require_fresh_execution_binding(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        execution_binding_id: UUID,
        request_mode: str,
    ) -> VEKLExecutionKnowledgeBinding:
        """Freshness guard reusable at worker start and consequential actions."""
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            binding = await self._knowledge.get_execution_binding(
                uow.connection,
                project_id=project_id,
                execution_binding_id=execution_binding_id,
            )
        if binding is None:
            raise DdeError("NOT_FOUND", "VEKL execution knowledge binding not found")
        trace = await self.require_fresh_trace(
            tenant_id=tenant_id,
            project_id=project_id,
            resolution_trace_id=binding.resolution_trace_id,
            request_mode=request_mode,
        )
        if (
            binding.project_truth_hash != trace.project_truth_hash
            or binding.unit_lineage_id != trace.unit_lineage_id
            or binding.unit_revision_hash != trace.unit_revision_hash
            or binding.graph_revision_hash != trace.graph_snapshot_hash
            or binding.graph_neighbourhood_hash != trace.graph_snapshot_hash
            or binding.technical_stack_fingerprint != trace.stack_fingerprint_hash
            or binding.knowledge_route_policy_hash
            != str(trace.resolution_envelope.get("retrieval_route_policy_hash"))
            or binding.determinism_envelope_hash
            != sha256_hex(canonical_json(trace.resolution_envelope))
        ):
            raise DdeError(
                "REFUSED_STALE_KNOWLEDGE",
                (
                    "execution knowledge binding no longer matches current "
                    "resolution authority"
                ),
            )
        manifest = await self._vekl_service.get_manifest(
            tenant_id=tenant_id,
            project_id=project_id,
            manifest_id=binding.activation_manifest_id,
        )
        if manifest.manifest_hash != binding.activation_manifest_hash:
            raise DdeError(
                "REFUSED_STALE_KNOWLEDGE",
                "activation manifest changed after execution knowledge binding",
            )
        return binding

    @staticmethod
    def _unit_matches_change(
        unit: VEKLUnitMap, spec: ChangeImpactSpec
    ) -> dict[str, list[str]]:
        changed_contracts = {
            *spec.changed_contract_refs,
            *spec.changed_schema_refs,
            *spec.changed_api_refs,
            *spec.changed_event_refs,
        }
        unit_contracts = {*unit.contracts_consumed, *unit.contracts_produced}
        contract_hits = sorted(changed_contracts & unit_contracts)

        changed_tasks = set(spec.changed_task_refs)
        task_hits = sorted(
            (changed_tasks & set(unit.task_ids))
            | (changed_tasks & set(unit.upstream_task_refs)),
            key=str,
        )

        raw_patterns = [
            *unit.code_targets,
            *VEKLKnowledgeService._str_list(unit.scope.get("includes")),
            *VEKLKnowledgeService._str_list(unit.scope.get("reads")),
        ]
        patterns = sorted(set(raw_patterns))
        path_hits: list[str] = []
        for changed_path in sorted(set(spec.changed_paths)):
            normalized = changed_path.removeprefix("./")
            for pattern in patterns:
                candidate = pattern.removeprefix("./")
                if (
                    normalized == candidate
                    or normalized.startswith(candidate.rstrip("/") + "/")
                    or fnmatchcase(normalized, candidate)
                    or (
                        candidate.endswith("/**")
                        and normalized.startswith(candidate[:-3])
                    )
                ):
                    path_hits.append(changed_path)
                    break

        return {
            "contracts": contract_hits,
            "tasks": [str(item) for item in task_hits],
            "paths": sorted(set(path_hits)),
        }

    async def invalidate_from_change(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        spec: ChangeImpactSpec,
        request_mode: str,
    ) -> list[VEKLGraphInvalidation]:
        """Invalidate only Unit projections deterministically affected by a real change.

        The source mutation remains owned by the existing Task/Workspace/
        ChangePacket path.
        This method persists derived staleness evidence only; it never creates or edits
        the source change authority.
        """
        truth = await self._truth(
            tenant_id=tenant_id, project_id=project_id, request_mode=request_mode
        )
        if not any(
            (
                spec.changed_contract_refs,
                spec.changed_task_refs,
                spec.changed_paths,
                spec.changed_schema_refs,
                spec.changed_api_refs,
                spec.changed_event_refs,
            )
        ):
            raise DdeError(
                "VALIDATION_FAILED",
                "change impact contains no changed contract/task/path authority",
            )
        now = datetime.now(UTC)
        output: list[VEKLGraphInvalidation] = []
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            units = await self._knowledge.list_active_unit_maps(
                uow.connection, project_id=project_id
            )
            for unit in units:
                hits = self._unit_matches_change(unit, spec)
                if not any(hits.values()):
                    continue
                await self._knowledge.invalidate_unit_map(
                    uow.connection,
                    project_id=project_id,
                    unit_map_id=unit.unit_map_id,
                    reason=spec.reason_code,
                    invalidated_at=now,
                )
                detail: dict[str, object] = {
                    "source_change_ref": spec.source_change_ref,
                    "source_change_hash": spec.source_change_hash,
                    "impacted_by": hits,
                    "previous_contract_set_hash": unit.contract_set_hash,
                }
                record = VEKLGraphInvalidation(
                    graph_invalidation_id=deterministic_uuid(
                        "change-impact-invalidation",
                        {
                            "project_id": str(project_id),
                            "unit_map_id": str(unit.unit_map_id),
                            "source_change_ref": spec.source_change_ref,
                            "source_change_hash": spec.source_change_hash,
                            "reason_code": spec.reason_code,
                        },
                    ),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    unit_map_id=unit.unit_map_id,
                    manifest_id=None,
                    resolution_trace_id=None,
                    reason_code=spec.reason_code,
                    detail=detail,
                    observed_truth_hash=truth.truth_hash,
                    previous_hash=unit.contract_set_hash,
                    observed_hash=spec.source_change_hash,
                    created_at=now,
                    updated_at=now,
                )
                await self._knowledge.insert_graph_invalidation(uow.connection, record)
                output.append(record)
            await uow.commit()
        return output

    async def invalidate_unit(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        unit_map_id: UUID,
        reason_code: str,
        detail: dict[str, object],
        observed_truth_hash: str,
        previous_hash: str | None = None,
        observed_hash: str | None = None,
    ) -> VEKLGraphInvalidation:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            unit = await self._knowledge.get_unit_map(
                uow.connection, project_id=project_id, unit_map_id=unit_map_id
            )
            if unit is None:
                raise DdeError("NOT_FOUND", "VEKL Unit Knowledge Map not found")
            await self._knowledge.invalidate_unit_map(
                uow.connection,
                project_id=project_id,
                unit_map_id=unit_map_id,
                reason=reason_code,
                invalidated_at=now,
            )
            record = VEKLGraphInvalidation(
                graph_invalidation_id=deterministic_uuid(
                    "graph-invalidation",
                    {
                        "project_id": str(project_id),
                        "unit_map_id": str(unit_map_id),
                        "reason_code": reason_code,
                        "observed_truth_hash": observed_truth_hash,
                        "previous_hash": previous_hash,
                        "observed_hash": observed_hash,
                    },
                ),
                tenant_id=tenant_id,
                project_id=project_id,
                unit_map_id=unit_map_id,
                manifest_id=None,
                resolution_trace_id=None,
                reason_code=reason_code,
                detail=detail,
                observed_truth_hash=observed_truth_hash,
                previous_hash=previous_hash,
                observed_hash=observed_hash,
                created_at=now,
                updated_at=now,
            )
            await self._knowledge.insert_graph_invalidation(uow.connection, record)
            await uow.commit()
            return record

    async def projection(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        request_mode: str,
    ) -> dict[str, object]:
        await self._truth(
            tenant_id=tenant_id,
            project_id=project_id,
            request_mode=request_mode,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            units = await self._knowledge.list_active_unit_maps(
                uow.connection, project_id=project_id
            )
            nodes = await self._knowledge.list_active_nodes(
                uow.connection, project_id=project_id
            )
            edges = await self._knowledge.list_active_edges(
                uow.connection, project_id=project_id
            )
            routes = await self._knowledge.list_active_routes(
                uow.connection, project_id=project_id
            )
            challenges = await self._knowledge.list_challenges(
                uow.connection, project_id=project_id
            )
            observations = await self._knowledge.list_conflict_observations(
                uow.connection, project_id=project_id
            )
            invalidations = await self._knowledge.list_invalidations(
                uow.connection, project_id=project_id
            )
            traces = await self._knowledge.list_resolution_traces(
                uow.connection, project_id=project_id
            )
            findings = []
            for unit in units:
                findings.extend(
                    await self._knowledge.list_findings_for_unit(
                        uow.connection,
                        project_id=project_id,
                        unit_map_id=unit.unit_map_id,
                    )
                )
            return {
                "unit_maps": [item.model_dump(mode="json") for item in units],
                "knowledge_nodes": [item.model_dump(mode="json") for item in nodes],
                "knowledge_edges": [item.model_dump(mode="json") for item in edges],
                "retrieval_routes": [item.model_dump(mode="json") for item in routes],
                "challenges": [item.model_dump(mode="json") for item in challenges],
                "conflict_observations": [
                    item.model_dump(mode="json") for item in observations
                ],
                "research_findings": [
                    item.model_dump(mode="json")
                    for item in sorted(
                        findings, key=lambda row: (row.created_at, str(row.finding_id))
                    )
                ],
                "graph_invalidations": [
                    item.model_dump(mode="json") for item in invalidations
                ],
                "resolution_traces": [item.model_dump(mode="json") for item in traces],
                "graph_snapshot_hash": graph_snapshot_hash(
                    [item.model_dump(mode="json") for item in nodes],
                    [item.model_dump(mode="json") for item in edges],
                ),
            }
