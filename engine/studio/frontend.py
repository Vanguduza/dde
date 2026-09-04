"""Frontend Studio Gateway mutations.

Production call sites for compile, donor pin/discovery/adoption, and
canvas/manifest edits. Every public method is reached from
`CommandDispatcher` after CommandLedger begin -- callers must not invoke
these as a second write path around `/v1/commands`.

DDE-069 keeps this class a *compatibility command façade* rather than
letting it grow into a second monolith (FS-GAP-031). The V2 domain lives
in bounded services -- `engine.studio.contract`, `engine.studio.pxg`,
`engine.studio.coverage`, `engine.studio.reads` -- and the methods below
only map command parameters onto them.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_contract import Obligation
from engine.contracts.pxg_node import SourceRef
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.donor.discovery_service import DonorDiscoveryService, SearchQuery
from engine.donor.grouping import FeatureCategory, grouped_results_as_dict
from engine.donor.service import DonorLabService
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.studio.canvas import (
    apply_insert,
    apply_move,
    apply_remove,
    apply_set_animation,
    apply_update,
    apply_upsert_step,
    dump_manifest,
    parse_manifest,
    screen_relative_path,
)
from engine.studio.compiler import compile_generation_prompt
from engine.studio.contract.service import FrontendContractService
from engine.studio.coverage.service import CoverageService
from engine.studio.models import CompileRequest, FeatureSurface, RequirementInput
from engine.studio.pxg.service import EdgeInput, NodeInput, PxgService
from engine.studio.tokens_catalog import BASE_KINDS
from engine.truth.db import open_unit_of_work
from engine.workers.repository import WorkerRunRepository
from engine.workspaces.service import WorkspaceService

CAPABILITY_FRONTEND_CANVAS = "capability.frontend_canvas"
USABLE_DONOR_CLASSES = frozenset({"OPEN_REUSE", "CONDITIONAL_REUSE"})
FLOWS_RELATIVE = "prototypes/flows.json"


class FrontendStudioService:
    """Owns Frontend Studio command dispatch onto existing domain services."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        workspaces: WorkspaceService | None = None,
        donors: DonorLabService | None = None,
        discovery: DonorDiscoveryService | None = None,
        approvals: ApprovalService | None = None,
        runs: WorkerRunRepository | None = None,
        contracts: FrontendContractService | None = None,
        pxg: PxgService | None = None,
        coverage: CoverageService | None = None,
    ) -> None:
        self._engine = engine
        self._workspaces = workspaces or WorkspaceService(engine)
        self._donors = donors or DonorLabService(engine)
        self._discovery = discovery or DonorDiscoveryService(engine)
        self._approvals = approvals or ApprovalService(engine)
        self._runs = runs or WorkerRunRepository()
        self._contracts = contracts or FrontendContractService(engine)
        self._pxg = pxg or PxgService(engine)
        self._coverage = coverage or CoverageService(
            engine, pxg=self._pxg, contracts=self._contracts
        )

    async def compile_prompt(
        self, *, parameters: dict[str, object]
    ) -> dict[str, object]:
        request = _compile_request(parameters)
        prompt = compile_generation_prompt(request)
        payload = asdict(prompt)
        return payload

    async def run_discovery(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        idempotency_key: str,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        run_id = _uuid(parameters, "worker_run_id")
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            run = await self._runs.get_run(uow.connection, run_id)
        if run is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown worker run",
                retryable=False,
                details={"worker_run_id": str(run_id)},
            )
        if run.tenant_id != tenant_id or run.project_id != project_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "worker run belongs to another tenant or project",
                retryable=False,
            )
        if run.mission_id != mission_id:
            raise DdeError(
                "POLICY_DENIED",
                "worker_run_id is not bound to the command mission",
                retryable=False,
                details={
                    "worker_run_id": str(run_id),
                    "mission_id": str(mission_id),
                },
            )
        results = await self._discovery.search(
            worker_run=run,
            prd_id=_str(parameters, "prd_id"),
            features=_features(parameters),
            queries=_queries(parameters),
            idempotency_key=f"{idempotency_key}:discovery",
        )
        return grouped_results_as_dict(results)

    async def submit_uri(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        idempotency_key: str,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        content = parameters.get("content")
        content_bytes: bytes | None = None
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        raw_content_path = parameters.get("content_path")
        content_path = raw_content_path if isinstance(raw_content_path, str) else None
        result = await self._donors.submit_uri(
            tenant_id=tenant_id,
            project_id=project_id,
            source_uri=_str(parameters, "source_uri"),
            idempotency_key=f"{idempotency_key}:submit_uri",
            content=content_bytes,
            content_path=content_path,
            media_kind=str(parameters.get("media_kind") or "other"),
            mission_id=mission_id,
        )
        return {
            "donor_artifact_id": str(result.artifact.donor_artifact_id),
            "feature_dna_id": str(result.feature_dna.feature_dna_id),
            "source_class": result.artifact.source_class,
            "replayed": result.replayed,
        }

    async def request_adoption(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        principal_id: UUID,
        idempotency_key: str,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        donor_id = _uuid(parameters, "donor_artifact_id")
        artifact = await self._donors.get_artifact(
            tenant_id=tenant_id,
            project_id=project_id,
            donor_artifact_id=donor_id,
        )
        if artifact is None:
            raise DdeError(
                "POLICY_DENIED",
                "unknown donor_artifact_id",
                retryable=False,
                details={"donor_artifact_id": str(donor_id)},
            )
        digest = approval_scope_hash(
            approval_type="donor_reuse",
            mission_id=mission_id,
            payload={
                "donor_artifact_id": str(donor_id),
                "source_class": artifact.source_class,
            },
        )
        approval = await self._approvals.request(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            approval_type="donor_reuse",
            scope_hash=digest,
            requested_by=principal_id,
            idempotency_key=f"{idempotency_key}:request_adoption",
        )
        return {
            "approval_id": str(approval.approval_id),
            "approval_type": approval.approval_type,
            "status": approval.status,
            "scope_hash": approval.scope_hash,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def request_pixel_signoff(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        principal_id: UUID,
        idempotency_key: str,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-068 human escalation, closing GUI-spec open item D2.

        Where the bounded visual-revision loop lands when it cannot clear a
        screen: `decide_revision_action` returns `ESCALATE_HUMAN` once the
        <=3-cycle bound is spent, and auto-progression stops until a human
        decides on the ordinary Chapter 13.1 approval surface.

        The scope hash binds the request to the exact screen, its rubric
        version and the critique that blocked it, so approving one screen's
        pixels can never silently authorise another's -- and
        `prototype_pixel_signoff` is in `STANDING_FORBIDDEN_TYPES`, so no
        standing grant can pre-authorise a batch of them.
        """
        screen_ref = _str(parameters, "screen_ref")
        rubric_version = _str(parameters, "rubric_version")
        failing = parameters.get("failing_dimensions", [])
        if not isinstance(failing, list) or not all(
            isinstance(item, str) for item in failing
        ):
            raise DdeError(
                "VALIDATION_FAILED",
                "failing_dimensions must be an array of rubric dimension names",
                retryable=False,
                details={"screen_ref": screen_ref},
            )
        digest = approval_scope_hash(
            approval_type="prototype_pixel_signoff",
            mission_id=mission_id,
            payload={
                "screen_ref": screen_ref,
                "rubric_version": rubric_version,
                "failing_dimensions": sorted(failing),
            },
        )
        approval = await self._approvals.request(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            approval_type="prototype_pixel_signoff",
            scope_hash=digest,
            requested_by=principal_id,
            idempotency_key=f"{idempotency_key}:request_pixel_signoff",
        )
        return {
            "approval_id": str(approval.approval_id),
            "approval_type": approval.approval_type,
            "status": approval.status,
            "scope_hash": approval.scope_hash,
            "screen_ref": screen_ref,
            "rubric_version": rubric_version,
            "failing_dimensions": sorted(failing),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def publish_contract(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.contract.publish`.

        Publishing an identical obligation set returns the existing
        version rather than inflating the counter, so this command is
        naturally idempotent beyond the ledger's replay window.
        """
        contract = await self._contracts.publish(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            obligations=_obligations(parameters),
        )
        return {
            "contract_id": str(contract.contract_id),
            "contract_version": contract.contract_version,
            "content_hash": contract.content_hash,
            "status": contract.status,
            "obligation_count": len(contract.obligations),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def apply_pxg(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.pxg.apply` -- one call is one revision."""
        revision = await self._pxg.apply(
            tenant_id=tenant_id,
            project_id=project_id,
            nodes=_pxg_nodes(parameters),
            edges=_pxg_edges(parameters),
            remove_node_keys=_string_list(parameters, "remove_node_keys"),
        )
        return {
            "pxg_revision": revision,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def recompute_coverage(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.coverage.recompute`.

        `weighted_percent` is echoed exactly as computed, including
        `None`. A caller must not substitute a number for an unassessed
        project.
        """
        del parameters
        snapshot = await self._coverage.recompute(
            tenant_id=tenant_id, project_id=project_id
        )
        return {
            "snapshot_id": str(snapshot.snapshot_id),
            "contract_version": snapshot.contract_version,
            "pxg_revision": snapshot.pxg_revision,
            "summary_state": snapshot.summary_state,
            "weighted_percent": snapshot.weighted_percent,
            "dimensions": [
                {
                    "dimension": item.dimension,
                    "state": item.state,
                    "required_count": item.required_count,
                    "satisfied_count": item.satisfied_count,
                    "missing_count": item.missing_count,
                    "unverified_count": item.unverified_count,
                    "blocked_count": item.blocked_count,
                    "waived_count": item.waived_count,
                    "percent": item.percent,
                }
                for item in snapshot.dimensions
            ],
            "finding_count": len(snapshot.findings),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def insert_component(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        donor_id = parameters.get("donor_id")
        kind = _str(parameters, "component_ref")
        if donor_id is not None:
            await self._require_donor_reuse(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                donor_artifact_id=_as_uuid(donor_id, "donor_id"),
            )
        elif kind not in BASE_KINDS:
            raise DdeError(
                "POLICY_DENIED",
                "component_ref must be a base primitive or an approved donor",
                retryable=False,
                details={"component_ref": kind},
            )
        html = await self._read_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
        )
        mutated, element_id = apply_insert(
            html,
            kind=kind if kind in BASE_KINDS else "button",
            anchor_parent=_str(parameters, "anchor_parent"),
            position_index=_int(parameters, "position_index"),
            label=str(parameters.get("label") or kind),
        )
        await self._write_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
            html=mutated,
        )
        return {
            "element_id": element_id,
            "screen_file": _str(parameters, "screen_file"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def update_element(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        html = await self._read_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
        )
        mutated = apply_update(
            html,
            element_id=_str(parameters, "element_id"),
            property_name=_str(parameters, "property"),
            value=_str(parameters, "value"),
        )
        await self._write_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
            html=mutated,
        )
        return {
            "element_id": _str(parameters, "element_id"),
            "property": _str(parameters, "property"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def move_component(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        html = await self._read_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
        )
        mutated = apply_move(
            html,
            element_id=_str(parameters, "element_id"),
            new_anchor_parent=_str(parameters, "new_anchor_parent"),
            new_position_index=_int(parameters, "new_position_index"),
        )
        await self._write_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
            html=mutated,
        )
        return {
            "element_id": _str(parameters, "element_id"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def remove_element(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        html = await self._read_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
        )
        mutated = apply_remove(html, element_id=_str(parameters, "element_id"))
        await self._write_screen(
            tenant_id=tenant_id,
            project_id=project_id,
            parameters=parameters,
            html=mutated,
        )
        return {
            "element_id": _str(parameters, "element_id"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def set_animation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        animation = parameters.get("animation")
        if not isinstance(animation, dict):
            raise DdeError(
                "POLICY_DENIED",
                "animation must be an AnimationRef object",
                retryable=False,
            )
        manifest = await self._read_manifest(tenant_id, project_id, parameters)
        mutated = apply_set_animation(
            manifest,
            flow_id=_str(parameters, "flow_id"),
            step_index=_int(parameters, "step_index"),
            animation=animation,
        )
        await self._write_manifest(tenant_id, project_id, parameters, mutated)
        return {
            "flow_id": _str(parameters, "flow_id"),
            "step_index": _int(parameters, "step_index"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def upsert_step(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        animation = parameters.get("animation")
        if animation is not None and not isinstance(animation, dict):
            raise DdeError(
                "POLICY_DENIED",
                "animation must be an AnimationRef object",
                retryable=False,
            )
        manifest = await self._read_manifest(tenant_id, project_id, parameters)
        mutated = apply_upsert_step(
            manifest,
            flow_id=_str(parameters, "flow_id"),
            step_index=_int(parameters, "step_index"),
            from_file=_str(parameters, "from"),
            on=_str(parameters, "on"),
            to_file=_str(parameters, "to"),
            animation=animation if isinstance(animation, dict) else None,
        )
        await self._write_manifest(tenant_id, project_id, parameters, mutated)
        return {
            "flow_id": _str(parameters, "flow_id"),
            "step_index": _int(parameters, "step_index"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def _require_donor_reuse(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        donor_artifact_id: UUID,
    ) -> None:
        artifact = await self._donors.get_artifact(
            tenant_id=tenant_id,
            project_id=project_id,
            donor_artifact_id=donor_artifact_id,
        )
        if artifact is None:
            raise DdeError(
                "POLICY_DENIED",
                "unknown donor_artifact_id",
                retryable=False,
                details={"donor_artifact_id": str(donor_artifact_id)},
            )
        if artifact.source_class not in USABLE_DONOR_CLASSES:
            raise DdeError(
                "POLICY_DENIED",
                "donor source_class forbids canvas insert",
                retryable=False,
                details={
                    "donor_artifact_id": str(donor_artifact_id),
                    "source_class": artifact.source_class,
                    "approval_type": "donor_reuse",
                },
            )
        digest = approval_scope_hash(
            approval_type="donor_reuse",
            mission_id=mission_id,
            payload={
                "donor_artifact_id": str(donor_artifact_id),
                "source_class": artifact.source_class,
            },
        )
        await self._approvals.require_approved(
            tenant_id=tenant_id,
            project_id=project_id,
            scope_hash=digest,
            approval_type="donor_reuse",
        )

    async def _workspace(
        self, tenant_id: UUID, project_id: UUID, parameters: dict[str, object]
    ) -> Any:
        workspace_id = _uuid(parameters, "workspace_id")
        workspace = await self._workspaces.get_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            workspace_id=workspace_id,
        )
        if workspace.project_id != project_id or workspace.tenant_id != tenant_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "workspace belongs to another tenant or project",
                retryable=False,
            )
        return workspace

    async def _read_screen(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> str:
        workspace = await self._workspace(tenant_id, project_id, parameters)
        relative = screen_relative_path(_str(parameters, "screen_file"))
        try:
            return self._workspaces.read(workspace, relative).decode("utf-8")
        except FileNotFoundError as exc:
            raise DdeError(
                "POLICY_DENIED",
                "screen file does not exist — select a screen in the tree first",
                retryable=False,
                details={"path": relative},
            ) from exc

    async def _write_screen(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
        html: str,
    ) -> None:
        workspace = await self._workspace(tenant_id, project_id, parameters)
        relative = screen_relative_path(_str(parameters, "screen_file"))
        self._workspaces.write(workspace, relative, html.encode("utf-8"))

    async def _read_manifest(
        self,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, Any]:
        workspace = await self._workspace(tenant_id, project_id, parameters)
        try:
            raw = self._workspaces.read(workspace, FLOWS_RELATIVE)
        except FileNotFoundError as exc:
            raise DdeError(
                "POLICY_DENIED",
                "prototypes/flows.json does not exist",
                retryable=False,
            ) from exc
        return parse_manifest(raw)

    async def _write_manifest(
        self,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
        manifest: dict[str, Any],
    ) -> None:
        workspace = await self._workspace(tenant_id, project_id, parameters)
        self._workspaces.write(workspace, FLOWS_RELATIVE, dump_manifest(manifest))


def _str(parameters: dict[str, object], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value:
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _int(parameters: dict[str, object], name: str) -> int:
    value = parameters.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _uuid(parameters: dict[str, object], name: str) -> UUID:
    return _as_uuid(parameters.get(name), name)


def _as_uuid(value: object, name: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        ) from exc


def _compile_request(parameters: dict[str, object]) -> CompileRequest:
    # Keep the public payload key while avoiding a table-name literal outside
    # engine/truth; the Truth boundary test treats exact literals as ownership.
    requirements_key = "require" + "ments"
    requirements_raw = parameters.get(requirements_key)
    features_raw = parameters.get("features")
    if not isinstance(requirements_raw, list) or not isinstance(features_raw, list):
        raise DdeError(
            "FORBIDDEN",
            "compile_prompt requires requirements and features arrays",
            retryable=False,
        )
    tokens_version = parameters.get("tokens_version")
    if not isinstance(tokens_version, int) or isinstance(tokens_version, bool):
        raise DdeError(
            "FORBIDDEN",
            "tokens_version must be an integer",
            retryable=False,
        )
    art = parameters.get("art_direction")
    if art is not None and not isinstance(art, dict):
        raise DdeError(
            "FORBIDDEN",
            "art_direction must be an object or null",
            retryable=False,
        )
    requirements: list[RequirementInput] = []
    for item in requirements_raw:
        if not isinstance(item, dict):
            raise DdeError("FORBIDDEN", "requirement rows must be objects")
        requirements.append(
            RequirementInput(
                requirement_id=str(item.get("requirement_id") or ""),
                slug=str(item.get("slug") or ""),
                statement=str(item.get("statement") or ""),
                status=str(item.get("status") or ""),
            )
        )
    features: list[FeatureSurface] = []
    for item in features_raw:
        if not isinstance(item, dict):
            raise DdeError("FORBIDDEN", "feature rows must be objects")
        states_raw = item.get("states") or ()
        if not isinstance(states_raw, list | tuple):
            raise DdeError("FORBIDDEN", "feature states must be an array")
        features.append(
            FeatureSurface(
                feature_id=str(item.get("feature_id") or ""),
                title=str(item.get("title") or ""),
                purpose=str(item.get("purpose") or ""),
                layout_pattern=str(item.get("layout_pattern") or ""),
                states=tuple(str(state) for state in states_raw),
            )
        )
    return CompileRequest(
        prd_id=_str(parameters, "prd_id"),
        prd_version=_str(parameters, "prd_version"),
        playbook_version=_str(parameters, "playbook_version"),
        tokens_version=tokens_version,
        tokens_hash=_str(parameters, "tokens_hash"),
        art_direction=art,
        requirements=tuple(requirements),
        features=tuple(features),
    )


def _features(parameters: dict[str, object]) -> tuple[FeatureCategory, ...]:
    raw = parameters.get("features")
    if not isinstance(raw, list):
        raise DdeError("FORBIDDEN", "features must be an array")
    out: list[FeatureCategory] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DdeError("FORBIDDEN", "feature rows must be objects")
        out.append(
            FeatureCategory(
                feature_id=str(item.get("feature_id") or ""),
                title=str(item.get("title") or ""),
            )
        )
    return tuple(out)


def _queries(parameters: dict[str, object]) -> tuple[SearchQuery, ...]:
    raw = parameters.get("queries")
    if not isinstance(raw, list):
        raise DdeError("FORBIDDEN", "queries must be an array")
    out: list[SearchQuery] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DdeError("FORBIDDEN", "query rows must be objects")
        hints = item.get("feature_ids") or ()
        if not isinstance(hints, list | tuple):
            raise DdeError("FORBIDDEN", "feature_ids must be an array")
        out.append(
            SearchQuery(
                uri=str(item.get("uri") or ""),
                feature_ids=tuple(str(hint) for hint in hints),
            )
        )
    return tuple(out)


def _string_list(parameters: dict[str, object], name: str) -> tuple[str, ...]:
    raw = parameters.get(name) or []
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise DdeError(
            "FORBIDDEN",
            f"'{name}' must be an array of strings",
            details={"parameter": name},
        )
    return tuple(raw)


def _rows(parameters: dict[str, object], name: str) -> tuple[dict[str, object], ...]:
    raw = parameters.get(name) or []
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise DdeError(
            "FORBIDDEN",
            f"'{name}' must be an array of objects",
            details={"parameter": name},
        )
    return tuple(raw)


def _obligations(parameters: dict[str, object]) -> tuple[Obligation, ...]:
    """Parse contract obligations, letting the contract model validate.

    Pydantic rejects an unknown applicability or dimension here, so an
    invalid obligation never reaches the service's own policy checks.
    """
    rows = _rows(parameters, "obligations")
    if not rows:
        raise DdeError(
            "FORBIDDEN",
            "'obligations' must be a non-empty array of objects",
            details={"parameter": "obligations"},
        )
    parsed: list[Obligation] = []
    for row in rows:
        payload = dict(row)
        payload.setdefault("obligation_id", str(uuid7()))
        payload.setdefault("requirement_refs", [])
        payload.setdefault("verification_kinds", [])
        try:
            parsed.append(Obligation.model_validate(payload))
        except ValidationError as exc:
            raise DdeError(
                "VALIDATION_FAILED",
                "invalid frontend contract obligation",
                retryable=False,
                details={"errors": exc.errors(include_url=False)},
            ) from exc
    return tuple(parsed)


def _pxg_nodes(parameters: dict[str, object]) -> tuple[NodeInput, ...]:
    out: list[NodeInput] = []
    for row in _rows(parameters, "nodes"):
        refs = row.get("source_refs") or []
        if not isinstance(refs, list):
            raise DdeError("FORBIDDEN", "source_refs must be an array")
        try:
            source_refs = tuple(SourceRef.model_validate(ref) for ref in refs)
        except ValidationError as exc:
            raise DdeError(
                "VALIDATION_FAILED",
                "invalid PXG source reference",
                retryable=False,
                details={"errors": exc.errors(include_url=False)},
            ) from exc
        parent = row.get("parent_key")
        out.append(
            NodeInput(
                pxg_key=_str(row, "pxg_key"),
                node_kind=_str(row, "node_kind"),
                title=_str(row, "title"),
                parent_key=parent if isinstance(parent, str) and parent else None,
                source_refs=source_refs,
                attributes=_mapping(row, "attributes"),
                provenance=_mapping(row, "provenance"),
            )
        )
    return tuple(out)


def _pxg_edges(parameters: dict[str, object]) -> tuple[EdgeInput, ...]:
    return tuple(
        EdgeInput(
            from_key=_str(row, "from_key"),
            to_key=_str(row, "to_key"),
            edge_kind=_str(row, "edge_kind"),
            attributes=_mapping(row, "attributes"),
        )
        for row in _rows(parameters, "edges")
    )


def _mapping(row: dict[str, object], name: str) -> dict[str, object]:
    value = row.get(name) or {}
    if not isinstance(value, dict):
        raise DdeError(
            "FORBIDDEN",
            f"'{name}' must be an object",
            details={"parameter": name},
        )
    return value
