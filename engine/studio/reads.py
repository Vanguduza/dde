"""DDE-069 Frontend Studio read projections.

The golden workbench shows counts, statuses, coverage and roles. Every
one of those must come from here, and every one of them may be honestly
unknown. This module's entire job is to make "we do not know" a
first-class, typed, renderable answer, so no client is ever tempted to
invent a plausible number (FS-GAP-023, FS-GAP-024, FRONTEND_STUDIO_REV3
section 8).

Two devices carry that:

`Projection`
    every snapshot arrives wrapped with an `Availability`, the revision
    it was observed at, and a reason when it is anything but AVAILABLE.

`CountValue`
    a count is either a real number read from a real inventory, or it is
    `UNKNOWN`. There is no third option and no zero-as-default: a group
    whose backing service does not exist yet reports UNKNOWN, and the UI
    renders an em-dash rather than `0`.

Composition only. This module reads; it never writes and never mutates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.pxg_node import PxgNode
from engine.contracts.workspace import Workspace
from engine.studio.candidates.service import CandidateService
from engine.studio.contract.service import FrontendContractService
from engine.studio.coverage.service import CoverageRead, CoverageService
from engine.studio.preview_runtime.service import PreviewService
from engine.studio.pxg.service import PxgGraph, PxgService
from engine.studio.verification_requests import CandidateVerificationRequestService
from engine.truth.db import open_unit_of_work
from engine.verification.repository import VerificationRunRepository
from engine.workspaces.service import WorkspaceService


class Availability(StrEnum):
    """Why a projection does or does not carry a value."""

    AVAILABLE = "AVAILABLE"
    EMPTY = "EMPTY"
    """Backing service answered; there is genuinely nothing."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    """The capability exists in the architecture but this project has not
    configured it. Distinct from UNAVAILABLE: nothing is broken."""

    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    """No backing service exists in this build yet. The honest state for
    a golden control whose domain is a later milestone."""

    UNAVAILABLE = "UNAVAILABLE"
    """Backing service exists but could not answer."""

    DEGRADED = "DEGRADED"
    """Partial answer; `partial` is set and the reason names what is
    missing."""


@dataclass(frozen=True)
class CountValue:
    """A count that is either known or explicitly unknown.

    `known` is the only way to read the number, so a caller cannot
    accidentally treat an unknown count as zero.
    """

    value: int | None
    availability: Availability
    reason: str | None = None

    @property
    def known(self) -> bool:
        return self.value is not None

    @classmethod
    def of(cls, value: int) -> CountValue:
        return cls(
            value=value,
            availability=Availability.AVAILABLE if value else Availability.EMPTY,
        )

    @classmethod
    def unknown(cls, availability: Availability, reason: str) -> CountValue:
        return cls(value=None, availability=availability, reason=reason)


@dataclass(frozen=True)
class ExplorerGroup:
    """One collapsible group in the project explorer."""

    key: str
    title: str
    count: CountValue
    children: tuple[ExplorerGroup, ...] = ()


@dataclass(frozen=True)
class ProjectExplorerSnapshot:
    project_id: UUID
    pxg_revision: int
    groups: tuple[ExplorerGroup, ...]


@dataclass(frozen=True)
class ScreenNode:
    pxg_key: str
    title: str
    route: str | None
    child_keys: tuple[str, ...]


@dataclass(frozen=True)
class CoverageSummary:
    """What the golden coverage ring renders.

    `weighted_percent` is None whenever the project is not fully
    assessed, and `stale` says the snapshot describes an older graph.
    Either one means the ring shows an em-dash, never a number.
    """

    summary_state: str
    weighted_percent: float | None
    contract_version: int | None
    pxg_revision: int | None
    current_pxg_revision: int
    stale: bool
    dimension_states: tuple[tuple[str, str], ...]
    blocking_finding_count: int
    availability: Availability
    reason: str | None = None


@dataclass(frozen=True)
class ModelRoleView:
    """Desired, configured and serving kept apart, always.

    Blueprint Rev 3 section 5.4 makes serving identity claimable only
    from `ModelServingEvidence`. No evidence source is implemented in
    this build, so `serving` is UNATTESTED and the card must say so
    rather than repeating `configured` in a third slot.
    """

    role: str
    desired: str | None
    configured: str | None
    serving: str | None
    serving_confidence: str


@dataclass(frozen=True)
class OrchestratorFrontendStatus:
    runtime_state: str
    roles: tuple[ModelRoleView, ...]
    design_director: str | None
    activity_event_count: CountValue
    availability: Availability
    reason: str | None = None


@dataclass(frozen=True)
class StudioSyncSnapshot:
    """Save/sync honesty (FS-GAP-022).

    `state` distinguishes an accepted command from a durable one. A 202
    is COMMAND_ACCEPTED, never SYNCED.
    """

    state: str
    durable_pxg_revision: int
    pending_mutation_count: int
    durable_revision_at: datetime | None
    build_version: str | None


@dataclass(frozen=True)
class AttentionItemView:
    category: str
    detail: str
    pxg_key: str | None


@dataclass(frozen=True)
class AttentionCenterSnapshot:
    """Real attention items only. An unknown count is not a badge."""

    items: tuple[AttentionItemView, ...]
    count: CountValue
    availability: Availability
    reason: str | None = None


@dataclass(frozen=True)
class SourceWorkspaceOption:
    workspace_id: str
    current_revision: str
    mission_id: str | None
    purpose: str | None
    created_at: datetime


@dataclass(frozen=True)
class SourceWorkspaceInventory:
    options: tuple[SourceWorkspaceOption, ...]
    selection_state: str
    auto_selected_workspace_id: str | None
    availability: Availability
    reason: str | None = None


@dataclass(frozen=True)
class VerificationCheckSnapshot:
    check_ref: str
    kind: str
    status: str
    detail: str | None


@dataclass(frozen=True)
class CandidateCardSnapshot:
    candidate_id: str
    title: str
    state: str
    origin: str
    workspace_id: str | None
    base_pxg_revision: int
    current_pxg_revision: int
    stale: bool
    scope_keys: tuple[str, ...]
    preview_session_id: str | None
    preview_state: str | None
    preview_state_detail: str | None
    verification_request_id: str | None
    verification_request_state: str | None
    verification_request_reason: str | None
    verification_required_kinds: tuple[str, ...]
    verification_run_id: str | None
    verification_run_status: str | None
    verification_confidence: float | None
    verification_checks: tuple[VerificationCheckSnapshot, ...]
    verification_evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class CandidateBoardSnapshot:
    cards: tuple[CandidateCardSnapshot, ...]
    count: CountValue


@dataclass(frozen=True)
class FrontendStudioSnapshot:
    """One composed read for the whole workbench."""

    project_id: UUID
    observed_at: datetime
    pxg_revision: int
    contract_version: int | None
    explorer: ProjectExplorerSnapshot
    coverage: CoverageSummary
    orchestrator: OrchestratorFrontendStatus
    sync: StudioSyncSnapshot
    attention: AttentionCenterSnapshot
    screens: tuple[ScreenNode, ...]
    source_workspaces: SourceWorkspaceInventory
    candidates: CandidateBoardSnapshot
    degraded_reasons: tuple[str, ...] = field(default_factory=tuple)


#: Golden explorer groups whose backing domain lands in a later
#: milestone. They are listed rather than hidden, so the UI shows the
#: real information architecture with honestly unknown counts instead of
#: a shorter, tidier lie.
_UNIMPLEMENTED_GROUPS: tuple[tuple[str, str, str], ...] = (
    (
        "sources",
        "Sources",
        "DesignSourceRegistry is DDE-069 M8; no source adapter is wired yet",
    ),
    (
        "templates",
        "Templates",
        "TemplateRecommendationService is DDE-069 M8; not wired yet",
    ),
    (
        "locks",
        "Locks",
        "LockService is implemented, but LockInventory is not yet "
        "projected by FrontendReadService",
    ),
)


class FrontendReadService:
    """Composes the Frontend Studio read projections."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        pxg: PxgService | None = None,
        contracts: FrontendContractService | None = None,
        coverage: CoverageService | None = None,
        candidates: CandidateService | None = None,
        previews: PreviewService | None = None,
        workspaces: WorkspaceService | None = None,
        verification_requests: CandidateVerificationRequestService | None = None,
        build_version: str | None = None,
    ) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)
        self._contracts = contracts or FrontendContractService(engine)
        self._coverage = coverage or CoverageService(
            engine, pxg=self._pxg, contracts=self._contracts
        )
        self._candidates = candidates or CandidateService(engine, pxg=self._pxg)
        self._previews = previews or PreviewService(engine, candidates=self._candidates)
        self._workspaces = workspaces or WorkspaceService(engine)
        self._verification_requests = (
            verification_requests or CandidateVerificationRequestService(engine)
        )
        self._verification_runs = VerificationRunRepository()
        self._build_version = build_version

    async def snapshot(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> FrontendStudioSnapshot:
        graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        contract = await self._contracts.get_active(
            tenant_id=tenant_id, project_id=project_id
        )
        coverage_read = await self._coverage.latest(
            tenant_id=tenant_id, project_id=project_id
        )

        coverage = _coverage_summary(coverage_read)
        attention = _attention_from(coverage_read, graph)
        degraded: list[str] = []
        if coverage.availability is not Availability.AVAILABLE and coverage.reason:
            degraded.append(coverage.reason)
        candidates = await self.candidate_board(
            tenant_id=tenant_id, project_id=project_id
        )
        source_workspaces = await self.source_workspace_inventory(
            tenant_id=tenant_id, project_id=project_id
        )

        return FrontendStudioSnapshot(
            project_id=project_id,
            observed_at=datetime.now(UTC),
            pxg_revision=graph.revision,
            contract_version=contract.contract_version if contract else None,
            explorer=explorer_snapshot(project_id, graph),
            coverage=coverage,
            orchestrator=_orchestrator_status(),
            sync=StudioSyncSnapshot(
                state="SYNCED" if graph.revision else "UNASSESSED",
                durable_pxg_revision=graph.revision,
                pending_mutation_count=0,
                durable_revision_at=max(
                    (node.updated_at for node in graph.nodes), default=None
                ),
                build_version=self._build_version,
            ),
            attention=attention,
            screens=screen_tree(graph),
            source_workspaces=source_workspaces,
            candidates=candidates,
            degraded_reasons=tuple(degraded),
        )

    async def screen_tree(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[ScreenNode, ...]:
        graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        return screen_tree(graph)

    async def source_workspace_inventory(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> SourceWorkspaceInventory:
        rows = await self._workspaces.list_project_workspaces(
            tenant_id=tenant_id, project_id=project_id
        )
        return build_source_workspace_inventory(rows)

    async def candidate_board(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> CandidateBoardSnapshot:
        views = await self._candidates.board(tenant_id=tenant_id, project_id=project_id)
        cards: list[CandidateCardSnapshot] = []
        for view in views:
            candidate = view.candidate
            preview = await self._previews.latest_for_candidate(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate.candidate_id,
            )
            verification_request = (
                await self._verification_requests.latest_for_candidate(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate.candidate_id,
                )
            )
            verification_run = None
            if candidate.verification_run_id is not None:
                async with open_unit_of_work(
                    self._engine, tenant_id=tenant_id, project_id=project_id
                ) as uow:
                    verification_run = await self._verification_runs.get_run(
                        uow.connection, candidate.verification_run_id
                    )
                if verification_run is not None and (
                    verification_run.tenant_id != tenant_id
                    or verification_run.project_id != project_id
                ):
                    verification_run = None
            cards.append(
                CandidateCardSnapshot(
                    candidate_id=str(candidate.candidate_id),
                    title=candidate.title,
                    state=candidate.state,
                    origin=candidate.origin,
                    workspace_id=(
                        str(candidate.workspace_id) if candidate.workspace_id else None
                    ),
                    base_pxg_revision=candidate.base_pxg_revision,
                    current_pxg_revision=view.current_pxg_revision,
                    stale=view.stale,
                    scope_keys=tuple(candidate.scope_keys),
                    preview_session_id=(
                        str(preview.preview_session_id) if preview else None
                    ),
                    preview_state=preview.state if preview else None,
                    preview_state_detail=preview.state_detail if preview else None,
                    verification_request_id=(
                        str(verification_request.verification_request_id)
                        if verification_request
                        else None
                    ),
                    verification_request_state=(
                        verification_request.state if verification_request else None
                    ),
                    verification_request_reason=(
                        verification_request.reason if verification_request else None
                    ),
                    verification_required_kinds=(
                        tuple(verification_request.required_kinds)
                        if verification_request
                        else ()
                    ),
                    verification_run_id=(
                        str(verification_run.verification_run_id)
                        if verification_run
                        else None
                    ),
                    verification_run_status=(
                        verification_run.status if verification_run else None
                    ),
                    verification_confidence=(
                        float(verification_run.confidence) if verification_run else None
                    ),
                    verification_checks=(
                        tuple(
                            VerificationCheckSnapshot(
                                check_ref=check.check_ref,
                                kind=check.kind,
                                status=check.status,
                                detail=(check.stderr or None),
                            )
                            for check in verification_run.check_results
                        )
                        if verification_run
                        else ()
                    ),
                    verification_evidence_refs=(
                        tuple(str(item) for item in verification_run.evidence_refs)
                        if verification_run
                        else ()
                    ),
                )
            )
        return CandidateBoardSnapshot(
            cards=tuple(cards), count=CountValue.of(len(cards))
        )


def build_source_workspace_inventory(
    rows: tuple[Workspace, ...] | list[Workspace],
) -> SourceWorkspaceInventory:
    admitted = tuple(
        row
        for row in rows
        if row.status == "READY"
        and row.current_revision is not None
        and row.policy.get("purpose") != "frontend_candidate_preview"
    )
    options = tuple(
        SourceWorkspaceOption(
            workspace_id=str(row.workspace_id),
            current_revision=str(row.current_revision),
            mission_id=str(row.mission_id) if row.mission_id else None,
            purpose=(
                str(row.policy.get("purpose"))
                if isinstance(row.policy.get("purpose"), str)
                else None
            ),
            created_at=row.created_at,
        )
        for row in admitted
    )
    if not options:
        return SourceWorkspaceInventory(
            options=(),
            selection_state="EMPTY",
            auto_selected_workspace_id=None,
            availability=Availability.EMPTY,
            reason=(
                "No READY non-candidate project workspace with a durable "
                "revision is available."
            ),
        )
    if len(options) == 1:
        return SourceWorkspaceInventory(
            options=options,
            selection_state="UNIQUE",
            auto_selected_workspace_id=options[0].workspace_id,
            availability=Availability.AVAILABLE,
        )
    return SourceWorkspaceInventory(
        options=options,
        selection_state="AMBIGUOUS",
        auto_selected_workspace_id=None,
        availability=Availability.AVAILABLE,
        reason=(
            "Multiple READY source workspaces exist; explicit selection is required."
        ),
    )


def screen_tree(graph: PxgGraph) -> tuple[ScreenNode, ...]:
    return tuple(
        ScreenNode(
            pxg_key=screen.pxg_key,
            title=screen.title,
            route=_str_or_none(screen.attributes.get("route")),
            child_keys=tuple(
                child.pxg_key for child in graph.children_of(screen.pxg_key)
            ),
        )
        for screen in graph.nodes_of_kind("screen")
    )


def explorer_snapshot(project_id: UUID, graph: PxgGraph) -> ProjectExplorerSnapshot:
    """Counts come from the graph; groups without a domain say UNKNOWN."""
    groups: list[ExplorerGroup] = [
        ExplorerGroup(
            key="screens",
            title="Screens",
            count=CountValue.of(len(graph.nodes_of_kind("screen"))),
        ),
        ExplorerGroup(
            key="journeys",
            title="Journeys",
            count=CountValue.of(len(graph.nodes_of_kind("journey"))),
        ),
        ExplorerGroup(
            key="components",
            title="Components",
            count=CountValue.of(len(graph.nodes_of_kind("component"))),
        ),
    ]
    groups.extend(
        ExplorerGroup(
            key=key,
            title=title,
            count=CountValue.unknown(Availability.NOT_IMPLEMENTED, reason),
        )
        for key, title, reason in _UNIMPLEMENTED_GROUPS
    )
    return ProjectExplorerSnapshot(
        project_id=project_id,
        pxg_revision=graph.revision,
        groups=tuple(groups),
    )


def _coverage_summary(read: CoverageRead) -> CoverageSummary:
    if read.snapshot is None:
        return CoverageSummary(
            summary_state="UNASSESSED",
            weighted_percent=None,
            contract_version=None,
            pxg_revision=None,
            current_pxg_revision=read.current_pxg_revision,
            stale=False,
            dimension_states=(),
            blocking_finding_count=0,
            availability=Availability.NOT_CONFIGURED,
            reason=read.unavailable_reason or "no coverage snapshot has been computed",
        )
    snapshot = read.snapshot
    # A stale snapshot describes a graph the project no longer has, so
    # its percentage is withheld rather than shown as current.
    percent = None if read.stale else snapshot.weighted_percent
    return CoverageSummary(
        summary_state=snapshot.summary_state,
        weighted_percent=percent,
        contract_version=snapshot.contract_version,
        pxg_revision=snapshot.pxg_revision,
        current_pxg_revision=read.current_pxg_revision,
        stale=read.stale,
        dimension_states=tuple(
            (item.dimension, item.state) for item in snapshot.dimensions
        ),
        blocking_finding_count=sum(
            1 for item in snapshot.findings if item.finding_kind == "MISSING"
        ),
        availability=Availability.DEGRADED if read.stale else Availability.AVAILABLE,
        reason=(
            f"snapshot describes PXG revision {snapshot.pxg_revision}; the "
            f"project is at {read.current_pxg_revision}"
            if read.stale
            else None
        ),
    )


def _attention_from(read: CoverageRead, graph: PxgGraph) -> AttentionCenterSnapshot:
    items: list[AttentionItemView] = []
    if read.stale:
        items.append(
            AttentionItemView(
                category="coverage_stale",
                detail=(
                    "coverage was computed against an older PXG revision and "
                    "needs recomputing"
                ),
                pxg_key=None,
            )
        )
    if read.snapshot is not None:
        items.extend(
            AttentionItemView(
                category="coverage_missing",
                detail=finding.detail,
                pxg_key=finding.pxg_key,
            )
            for finding in read.snapshot.findings
            if finding.finding_kind == "MISSING"
        )
    items.extend(
        AttentionItemView(
            category="pxg_orphan",
            detail=f"node names a parent that does not exist: {node.parent_key}",
            pxg_key=node.pxg_key,
        )
        for node in graph.orphan_nodes()
    )
    return AttentionCenterSnapshot(
        items=tuple(items),
        count=CountValue.of(len(items)),
        availability=Availability.AVAILABLE,
    )


def _orchestrator_status() -> OrchestratorFrontendStatus:
    """No orchestrator runtime is wired to the Studio in this build.

    Reporting NOT_IMPLEMENTED with an UNATTESTED serving identity is the
    honest answer; an 'ACTIVE' dot with a model name next to it would be
    exactly the overclaim Blueprint Rev 3 section 5.10 forbids.
    """
    return OrchestratorFrontendStatus(
        runtime_state="UNKNOWN",
        roles=(
            ModelRoleView(
                role="manager_chair",
                desired=None,
                configured=None,
                serving=None,
                serving_confidence="UNATTESTED",
            ),
            ModelRoleView(
                role="design_director",
                desired=None,
                configured=None,
                serving=None,
                serving_confidence="UNATTESTED",
            ),
        ),
        design_director=None,
        activity_event_count=CountValue.unknown(
            Availability.NOT_IMPLEMENTED,
            "no frontend activity projection is wired yet",
        ),
        availability=Availability.NOT_IMPLEMENTED,
        reason=(
            "no ModelServingEvidence source is implemented (Blueprint Rev 3 "
            "section 5.4); serving identity stays unattested"
        ),
    )


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def component_inventory(graph: PxgGraph) -> tuple[PxgNode, ...]:
    return graph.nodes_of_kind("component")
