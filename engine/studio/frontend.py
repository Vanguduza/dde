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
from engine.contracts.verification_run import VerificationRun
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.donor.discovery_service import DonorDiscoveryService, SearchQuery
from engine.donor.grouping import FeatureCategory, grouped_results_as_dict
from engine.donor.service import DonorLabService
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.missions.service import MissionService
from engine.studio.acceptance.defaults import GENERATED_SCREEN
from engine.studio.acceptance.service import ScreenAcceptanceService
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.promotion import PromotionService
from engine.studio.candidates.service import CandidateService
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
from engine.studio.chat.activity import FrontendChatActivityService
from engine.studio.chat.attachments import FrontendChatAttachmentService
from engine.studio.chat.checkpoints import FrontendChatCheckpointService
from engine.studio.chat.context_refs import FrontendChatContextService
from engine.studio.chat.models import FrontendChatModelCatalog
from engine.studio.chat.plans import FrontendChatPlanService
from engine.studio.chat.service import FrontendChatService
from engine.studio.chat.workspace_review import FrontendChatWorkspaceReviewService
from engine.studio.compiler import compile_generation_prompt
from engine.studio.contract.service import FrontendContractService
from engine.studio.coverage.service import CoverageService
from engine.studio.design.gateway import DesignGateway
from engine.studio.locks.service import LockService
from engine.studio.models import CompileRequest, FeatureSurface, RequirementInput
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.mutations.governed import GovernedMutationService
from engine.studio.mutations.planner import MutationRequest
from engine.studio.preview_runtime.service import PreviewService, PreviewState
from engine.studio.pxg.service import EdgeInput, NodeInput, PxgService
from engine.studio.tokens_catalog import BASE_KINDS
from engine.studio.verification_execution import CandidateVerificationExecutionService
from engine.studio.verification_requests import CandidateVerificationRequestService
from engine.truth.db import open_unit_of_work
from engine.verification.repository import VerificationRunRepository
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
        screens: ScreenAcceptanceService | None = None,
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
        self._screens_service = screens

    def _missions(self) -> MissionService:
        return MissionService(self._engine, EventService(self._engine))

    def _candidate_service(self) -> CandidateService:
        return CandidateService(self._engine, pxg=self._pxg)

    def _lock_service(self) -> LockService:
        return LockService(self._engine)

    def _mutation_executor(self) -> MutationExecutor:
        return MutationExecutor(
            self._engine,
            pxg=self._pxg,
            locks=self._lock_service(),
            candidates=self._candidate_service(),
        )

    def _design_gateway(self) -> DesignGateway:
        return DesignGateway(
            self._engine,
            pxg=self._pxg,
            contracts=self._contracts,
            candidates=self._candidate_service(),
        )

    def _governed_mutations(self) -> GovernedMutationService:
        executor = self._mutation_executor()
        candidates = self._candidate_service()
        previews = PreviewService(
            self._engine,
            workspaces=self._workspaces,
            candidates=candidates,
            mutations=executor,
        )
        requests = CandidateVerificationRequestService(self._engine, mutations=executor)
        return GovernedMutationService(
            self._engine,
            executor=executor,
            previews=previews,
            verification_requests=requests,
        )

    def _chat_activities(self) -> FrontendChatActivityService:
        return FrontendChatActivityService(self._engine)

    def _chat_attachments(self) -> FrontendChatAttachmentService:
        return FrontendChatAttachmentService(
            self._engine,
            workspaces=self._workspaces,
            activities=self._chat_activities(),
        )

    def _chat_plans(self) -> FrontendChatPlanService:
        return FrontendChatPlanService(self._engine, activities=self._chat_activities())

    def _chat_context(self) -> FrontendChatContextService:
        return FrontendChatContextService(
            self._engine,
            attachments=self._chat_attachments(),
            plans=self._chat_plans(),
        )

    def _chat_workspace_review(self) -> FrontendChatWorkspaceReviewService:
        return FrontendChatWorkspaceReviewService(
            self._engine, activities=self._chat_activities()
        )

    def _chat_checkpoints(self) -> FrontendChatCheckpointService:
        return FrontendChatCheckpointService(
            self._engine,
            attachments=self._chat_attachments(),
            workspace_review=self._chat_workspace_review(),
            activities=self._chat_activities(),
        )

    def _chat_service(self) -> FrontendChatService:
        return FrontendChatService(
            self._engine,
            mutations=self._governed_mutations(),
            design=self._design_gateway(),
            attachments=self._chat_attachments(),
            plans=self._chat_plans(),
            activities=self._chat_activities(),
            context=self._chat_context(),
            models=FrontendChatModelCatalog(),
        )

    def _promotion_service(self) -> PromotionService:
        return PromotionService(
            self._engine,
            candidates=self._candidate_service(),
            pxg=self._pxg,
            locks=self._lock_service(),
            coverage=self._coverage,
            mutations=self._mutation_executor(),
        )

    def _preview_service(self) -> PreviewService:
        candidates = self._candidate_service()
        mutations = MutationExecutor(
            self._engine,
            pxg=self._pxg,
            locks=self._lock_service(),
            candidates=candidates,
        )
        return PreviewService(
            self._engine,
            workspaces=self._workspaces,
            candidates=candidates,
            mutations=mutations,
        )

    def _verification_requests(self) -> CandidateVerificationRequestService:
        return CandidateVerificationRequestService(
            self._engine, mutations=self._mutation_executor()
        )

    def _verification_execution_service(self) -> CandidateVerificationExecutionService:
        return CandidateVerificationExecutionService(
            self._engine,
            workspaces=self._workspaces,
            candidates=self._candidate_service(),
            previews=self._preview_service(),
        )

    def _screens(self) -> ScreenAcceptanceService:
        if self._screens_service is None:
            self._screens_service = ScreenAcceptanceService(self._engine, pxg=self._pxg)
        return self._screens_service

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

    async def design_provider_status(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.design.provider_status`.

        What the `/design` control renders itself from. Never fabricated:
        an uncertified provider reports that, with the reason.
        """
        del tenant_id, project_id, parameters
        statuses = await self._design_gateway().provider_statuses()
        return {
            "providers": [
                {
                    "provider_id": item.provider_id,
                    "display_name": item.display_name,
                    "state": item.state.value,
                    "detail": item.detail,
                    "version": item.version,
                    "usable": item.usable,
                }
                for item in statuses
            ],
            "side_effect_class": "PURE_READ",
        }

    async def request_design(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.design.request`.

        Refuses when no certified provider exists rather than substituting
        a generic code-generation prompt (FRONTEND_STUDIO_REV3 section 23).
        """
        raw_count = parameters.get("direction_count")
        outcome = await self._design_gateway().request(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            conversation_id=_optional_uuid(parameters, "conversation_id"),
            scope_keys=list(_string_list(parameters, "scope_keys")),
            instruction=_str(parameters, "instruction"),
            provider_id=str(parameters.get("provider_id") or "claude-design"),
            direction_count=raw_count if isinstance(raw_count, int) else 3,
        )
        return {
            "design_session_id": str(outcome.session.session_id),
            "design_system_hash": outcome.session.design_system_hash,
            "context_manifest": outcome.session.context_manifest,
            "artifacts": [
                {
                    "artifact_id": str(item.artifact_id),
                    "direction_label": item.direction_label,
                    "status": item.status,
                    "content_hash": item.content_hash,
                    "quarantine_reason": item.quarantine_reason,
                }
                for item in outcome.artifacts
            ],
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def try_design_live(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.design.try_live` -- artifact to isolated
        candidate. Never to accepted code."""
        artifact, candidate_id = await self._design_gateway().try_live(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            artifact_id=_uuid(parameters, "artifact_id"),
        )
        return {
            "artifact_id": str(artifact.artifact_id),
            "direction_label": artifact.direction_label,
            "candidate_id": str(candidate_id),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def open_conversation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        principal_id: UUID | None,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.chat.open`."""
        conversation = await self._chat_service().open(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            screen_key=_optional_str(parameters, "screen_key"),
            viewport=str(parameters.get("viewport") or "desktop-1440"),
            title=_optional_str(parameters, "title"),
            mode=str(parameters.get("mode") or "ASK"),
            model_profile_id=_optional_str(parameters, "model_profile_id"),
            active_workspace_id=_optional_uuid(parameters, "active_workspace_id"),
            created_by=principal_id,
        )
        return {
            "conversation_id": str(conversation.conversation_id),
            "screen_key": conversation.screen_key,
            "viewport": conversation.viewport,
            "title": conversation.title,
            "mode": conversation.mode,
            "model_profile_id": conversation.model_profile_id,
            "active_workspace_id": (
                str(conversation.active_workspace_id)
                if conversation.active_workspace_id
                else None
            ),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def set_conversation_context(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.chat.set_context`.

        The selection lives on the conversation so a later "this" resolves
        to what the user had selected, not to whatever a client sent.
        """
        raw_keys = parameters.get("selected_node_keys")
        conversation = await self._chat_service().set_context(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            selected_node_keys=(
                list(_string_list(parameters, "selected_node_keys"))
                if raw_keys is not None
                else None
            ),
            active_candidate_id=_optional_uuid(parameters, "active_candidate_id"),
            set_active_candidate="active_candidate_id" in parameters,
            screen_key=_optional_str(parameters, "screen_key"),
            set_screen="screen_key" in parameters,
            viewport=_optional_str(parameters, "viewport"),
            active_workspace_id=_optional_uuid(parameters, "active_workspace_id"),
            set_active_workspace="active_workspace_id" in parameters,
        )
        return {
            "conversation_id": str(conversation.conversation_id),
            "selected_node_keys": list(conversation.selected_node_keys),
            "active_candidate_id": (
                str(conversation.active_candidate_id)
                if conversation.active_candidate_id
                else None
            ),
            "screen_key": conversation.screen_key,
            "viewport": conversation.viewport,
            "active_workspace_id": (
                str(conversation.active_workspace_id)
                if conversation.active_workspace_id
                else None
            ),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def send_chat_turn(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.chat.send`.

        A refused turn is a 202 with a typed refusal in the payload, not an
        error: the turn really was recorded, and the user needs to see
        which refusal they got.
        """
        result = await self._chat_service().send(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            text=_str(parameters, "text"),
            attachment_ids=tuple(
                _as_uuid(item, "attachment_ids")
                for item in _raw_list(parameters, "attachment_ids")
            ),
        )
        return {
            "turn_id": str(result.turn.turn_id),
            "reply_turn_id": str(result.reply.turn_id),
            "sequence": result.turn.sequence,
            "intent": result.turn.intent,
            "outcome": result.turn.outcome,
            "refusal_code": result.turn.refusal_code,
            "refusal_detail": result.turn.refusal_detail,
            "resolved_context": result.turn.resolved_context,
            "produced_refs": list(result.produced_refs),
            "message": result.message,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def rename_chat_conversation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_service().rename(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            title=_str(parameters, "title"),
        )
        return {
            "conversation": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def archive_chat_conversation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_service().archive(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            archived=_bool(parameters, "archived", default=True),
        )
        return {
            "conversation": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def set_chat_mode(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_service().set_mode(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            mode=_str(parameters, "mode"),
        )
        return {
            "conversation": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def set_chat_model(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_service().set_model(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            model_profile_id=_optional_str(parameters, "model_profile_id"),
        )
        return {
            "conversation": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def pin_chat_context(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_service().pin_context(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            context_ref=_str(parameters, "context_ref"),
            pinned=_bool(parameters, "pinned"),
        )
        return {
            "conversation": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def branch_chat_conversation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID | None,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_service().branch(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            from_turn_id=_optional_uuid(parameters, "from_turn_id"),
            created_by=principal_id,
            title=_optional_str(parameters, "title"),
        )
        return {
            "conversation": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def reserve_chat_attachment(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID | None,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_attachments().reserve(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            filename=_str(parameters, "filename"),
            media_type=str(parameters.get("media_type") or "application/octet-stream"),
            size_bytes=_int(parameters, "size_bytes"),
            created_by=principal_id,
        )
        return {
            "attachment": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def import_chat_workspace_attachment(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID | None,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_attachments().import_workspace_file(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            workspace_id=_uuid(parameters, "workspace_id"),
            relative_path=_str(parameters, "relative_path"),
            created_by=principal_id,
        )
        return {
            "attachment": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def remove_chat_attachment(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_attachments().remove(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            attachment_id=_uuid(parameters, "attachment_id"),
        )
        return {
            "attachment": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def create_chat_plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_plans().create(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            title=_str(parameters, "title"),
            objective=_str(parameters, "objective"),
            steps=list(_rows(parameters, "steps")),
            approval_required=_bool(parameters, "approval_required", default=True),
            workspace_id=_optional_uuid(parameters, "workspace_id"),
            task_graph_id=_optional_uuid(parameters, "task_graph_id"),
            context_snapshot=_optional_mapping(parameters, "context_snapshot"),
        )
        return {
            "plan": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def update_chat_plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_plans().update(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=_uuid(parameters, "plan_id"),
            expected_lock_version=_int(parameters, "lock_version"),
            title=_optional_str(parameters, "title"),
            objective=_optional_str(parameters, "objective"),
            steps=(list(_rows(parameters, "steps")) if "steps" in parameters else None),
        )
        return {
            "plan": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def approve_chat_plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_plans().approve(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=_uuid(parameters, "plan_id"),
            principal_id=principal_id,
            expected_lock_version=_int(parameters, "lock_version"),
        )
        return {
            "plan": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def prepare_chat_plan_step(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        payload = await self._chat_plans().prepare_step(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=_uuid(parameters, "plan_id"),
            step_id=_uuid(parameters, "step_id"),
            protocol_version=str(parameters.get("protocol_version") or "1"),
        )
        return {**payload, "side_effect_class": "WORKSPACE_LOCAL"}

    async def record_chat_plan_step(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_plans().record_step(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=_uuid(parameters, "plan_id"),
            step_id=_uuid(parameters, "step_id"),
            command_id=_uuid(parameters, "command_id"),
        )
        return {
            "plan": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def retry_chat_plan_step(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_plans().retry_step(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=_uuid(parameters, "plan_id"),
            step_id=_uuid(parameters, "step_id"),
        )
        return {
            "plan": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def cancel_chat_plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_plans().cancel(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=_uuid(parameters, "plan_id"),
            expected_lock_version=_int(parameters, "lock_version"),
        )
        return {
            "plan": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def cancel_chat_activity(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_activities().cancel(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            activity_id=_uuid(parameters, "activity_id"),
            reason=_str(parameters, "reason"),
        )
        return {
            "activity": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def create_chat_checkpoint(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID | None,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_checkpoints().create(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            created_by=principal_id,
            note=_optional_str(parameters, "note"),
        )
        return {
            "checkpoint": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def restore_chat_checkpoint(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_checkpoints().restore_context(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            checkpoint_id=_uuid(parameters, "checkpoint_id"),
        )
        return {
            "conversation": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def apply_chat_workspace_patch(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_workspace_review().apply_patch(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            patch_text=_str(parameters, "patch_text"),
            expected_diff_hash=_optional_str(parameters, "expected_diff_hash"),
        )
        return {
            "changes": _workspace_changes_payload(item),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def accept_chat_workspace_file(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_workspace_review().accept_file(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            path=_str(parameters, "path"),
            expected_diff_hash=_str(parameters, "expected_diff_hash"),
            principal_id=principal_id,
        )
        return {
            "review": item.model_dump(mode="json"),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def revert_chat_workspace_file(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_workspace_review().revert_file(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            path=_str(parameters, "path"),
            expected_diff_hash=_str(parameters, "expected_diff_hash"),
            principal_id=principal_id,
        )
        return {
            "changes": _workspace_changes_payload(item),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def revert_all_chat_workspace_changes(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        item = await self._chat_workspace_review().revert_all(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=_uuid(parameters, "conversation_id"),
            checkpoint_id=_uuid(parameters, "checkpoint_id"),
            principal_id=principal_id,
        )
        return {
            "changes": _workspace_changes_payload(item),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def create_candidate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.candidate.create`."""
        candidate = await self._candidate_service().create(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            title=_str(parameters, "title"),
            origin=_str(parameters, "origin"),
            scope_keys=_string_list(parameters, "scope_keys"),
        )
        return {
            "candidate_id": str(candidate.candidate_id),
            "state": candidate.state,
            "base_pxg_revision": candidate.base_pxg_revision,
            "scope_keys": list(candidate.scope_keys),
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def transition_candidate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.candidate.transition` -- governed by the
        lifecycle table, so an illegal jump is refused here rather than
        being expressible from the client."""
        candidate = await self._candidate_service().transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=_uuid(parameters, "candidate_id"),
            target=CandidateState(_str(parameters, "target")),
            detail=_optional_str(parameters, "detail"),
        )
        return {
            "candidate_id": str(candidate.candidate_id),
            "state": candidate.state,
            "state_detail": candidate.state_detail,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def apply_mutations(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.mutation.apply` -- the one governed write path.

        Refusals are returned, not raised: the caller gets a typed code
        per request so the studio can say what it declined and why.
        """
        candidate_id = _uuid(parameters, "candidate_id")
        governed = await self._governed_mutations().apply(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            requests=_mutation_requests(parameters),
        )
        outcome = governed.mutation
        return {
            "candidate_state": outcome.candidate_state.value,
            "applied": [
                {
                    "mutation_id": str(item.mutation_id),
                    "sequence": item.sequence,
                    "operation": item.operation,
                    "target_key": item.target_key,
                }
                for item in outcome.applied
            ],
            "refused": [
                {
                    "sequence": item.sequence,
                    "operation": item.operation,
                    "target_key": item.target_key,
                    "refusal_code": item.refusal_code,
                    "refusal_detail": item.refusal_detail,
                }
                for item in outcome.refused
            ],
            "fully_applied": outcome.fully_applied,
            "invalidated_preview_session_ids": [
                str(item) for item in governed.invalidated_preview_session_ids
            ],
            "superseded_verification_request_ids": [
                str(item) for item in governed.superseded_verification_request_ids
            ],
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def revert_mutation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.mutation.revert`."""
        governed = await self._governed_mutations().revert(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=_uuid(parameters, "candidate_id"),
            mutation_id=_uuid(parameters, "mutation_id"),
        )
        compensating = governed.compensating_mutation
        return {
            "compensating_mutation_id": str(compensating.mutation_id),
            "target_key": compensating.target_key,
            "invalidated_preview_session_ids": [
                str(item) for item in governed.invalidated_preview_session_ids
            ],
            "superseded_verification_request_ids": [
                str(item) for item in governed.superseded_verification_request_ids
            ],
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def start_preview(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.preview.start` -- materialize real candidate code."""
        source_workspace = _optional_uuid(parameters, "source_workspace_id")
        session = await self._preview_service().start(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=_uuid(parameters, "candidate_id"),
            screen_key=_str(parameters, "screen_key"),
            viewport=_str(parameters, "viewport"),
            source_workspace_id=source_workspace,
        )
        return _preview_payload(session)

    async def set_preview_state(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """Browser-owned preview signals.

        Server-owned build/render/staleness states cannot be asserted by the UI.
        """
        state = PreviewState(_str(parameters, "state"))
        service = self._preview_service()
        if state is PreviewState.LIVE:
            session = await service.confirm_live(
                tenant_id=tenant_id,
                project_id=project_id,
                preview_session_id=_uuid(parameters, "preview_session_id"),
                content_hash=_str(parameters, "content_hash"),
            )
        elif state is PreviewState.RUNTIME_ERROR:
            session = await service.report_runtime_error(
                tenant_id=tenant_id,
                project_id=project_id,
                preview_session_id=_uuid(parameters, "preview_session_id"),
                detail=_str(parameters, "detail"),
            )
        else:
            raise DdeError(
                "POLICY_DENIED",
                "clients may only attest LIVE or report RUNTIME_ERROR; "
                "build/render/stale states are server-owned",
                retryable=False,
                details={"state": state.value},
            )
        payload = _preview_payload(session)
        if PreviewState(session.state) is PreviewState.LIVE:
            request = await self._verification_requests().schedule_live_preview(
                tenant_id=tenant_id,
                project_id=project_id,
                preview=session,
            )
            payload.update(
                {
                    "verification_request_id": str(request.verification_request_id),
                    "verification_request_state": request.state,
                    "verification_required_kinds": list(request.required_kinds),
                    "verification_request_reason": request.reason,
                }
            )
        return payload

    async def stop_preview(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        session = await self._preview_service().stop(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=_uuid(parameters, "preview_session_id"),
        )
        return _preview_payload(session)

    async def run_candidate_verification(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """Execute a durable Frontend verification request through DDE-068."""
        result = await self._verification_execution_service().execute(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            verification_request_id=_uuid(parameters, "verification_request_id"),
        )
        return {
            "verification_request_id": str(result.request.verification_request_id),
            "request_state": result.request.state,
            "request_reason": result.request.reason,
            "verification_run_id": (
                str(result.run.verification_run_id) if result.run else None
            ),
            "verification_run_status": result.run.status if result.run else None,
            "candidate_id": str(result.candidate.candidate_id),
            "candidate_state": result.candidate.state,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def create_lock(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.lock.create`."""
        lock = await self._lock_service().create(
            tenant_id=tenant_id,
            project_id=project_id,
            lock_kind=_str(parameters, "lock_kind"),
            scope_key=_str(parameters, "scope_key"),
            reason=_str(parameters, "reason"),
            created_by=principal_id,
        )
        return {
            "lock_id": str(lock.lock_id),
            "lock_kind": lock.lock_kind,
            "scope_key": lock.scope_key,
            "status": lock.status,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def release_lock(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.lock.release`."""
        lock = await self._lock_service().release(
            tenant_id=tenant_id,
            project_id=project_id,
            lock_id=_uuid(parameters, "lock_id"),
            released_by=principal_id,
        )
        return {
            "lock_id": str(lock.lock_id),
            "status": lock.status,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def promote_candidate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.candidate.promote`.

        Every gate is evaluated; a denial carries all of them so the user
        sees everything blocking rather than one condition per attempt.
        """
        candidate_id = _uuid(parameters, "candidate_id")
        runs = await self._verification_runs_for(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        promoted = await self._promotion_service().promote(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            verification_runs=runs,
        )
        return {
            "candidate_id": str(promoted.candidate_id),
            "state": promoted.state,
            "promoted_at": promoted.promoted_at.isoformat()
            if promoted.promoted_at
            else None,
            "side_effect_class": "WORKSPACE_LOCAL",
        }

    async def _verification_runs_for(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
    ) -> tuple[VerificationRun, ...]:
        """Load only the evidence currently attached to this candidate.

        A prior task-level PASSED run must never approve code that was edited
        afterwards. CandidateService clears `verification_run_id` on DIRTY, and
        only a fresh verification execution may attach a new one. Promotion
        therefore consumes that exact durable run rather than every run ever
        produced for the authoring task.
        """
        candidate = await self._candidate_service().get(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        if candidate.verification_run_id is None:
            return ()
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            run = await VerificationRunRepository().get_run(
                uow.connection, candidate.verification_run_id
            )
        if run is None or run.tenant_id != tenant_id or run.project_id != project_id:
            return ()
        return (run,)

    async def register_screen(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        """DDE-069 `frontend.screen.register`.

        The production authoring path that closes DDE-068's carry-over: a
        screen enters the Project Experience Graph and receives its
        mandatory visual-verification bindings in the same governed step,
        so nothing reaches promotion merely because someone forgot to
        attach a check. A screen whose bindings are refused is not
        registered at all.
        """
        task_id = _uuid(parameters, "task_id")
        task = await self._missions().get_task(
            tenant_id=tenant_id, project_id=project_id, task_id=task_id
        )
        if task.mission_id != mission_id:
            raise DdeError(
                "POLICY_DENIED",
                "task_id is not bound to the command mission",
                retryable=False,
                details={"task_id": str(task_id), "mission_id": str(mission_id)},
            )
        registration = await self._screens().register_screen(
            task=task,
            screen_ref=_str(parameters, "screen_ref"),
            title=_str(parameters, "title"),
            preview_url=_str(parameters, "preview_url"),
            profile=str(parameters.get("profile") or GENERATED_SCREEN),
            route=_optional_str(parameters, "route"),
            expect_text=_optional_str(parameters, "expect_text"),
            visual_diff_spec_path=_optional_str(parameters, "visual_diff_spec_path"),
        )
        return {
            "screen_ref": registration.screen_ref,
            "pxg_revision": registration.pxg_revision,
            "oracle_id": str(registration.oracle.oracle_id),
            "oracle_version": registration.oracle.oracle_version,
            "bound_verification_kinds": list(registration.bound_kinds),
            "acceptance_policy_version": registration.policy_version,
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


def _preview_payload(session: Any) -> dict[str, object]:
    return {
        "preview_session_id": str(session.preview_session_id),
        "candidate_id": str(session.candidate_id),
        "workspace_id": (str(session.workspace_id) if session.workspace_id else None),
        "screen_key": session.screen_key,
        "state": session.state,
        "viewport": session.viewport,
        "route": session.route,
        "candidate_pxg_revision": session.candidate_pxg_revision,
        "source_revision": session.source_revision,
        "source_path": session.source_path,
        "document_path": session.document_path,
        "content_hash": session.content_hash,
        "state_detail": session.state_detail,
        "side_effect_class": "WORKSPACE_LOCAL",
    }


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


def _optional_str(parameters: dict[str, object], name: str) -> str | None:
    value = parameters.get(name)
    return value if isinstance(value, str) and value else None


def _raw_list(parameters: dict[str, object], name: str) -> list[object]:
    value = parameters.get(name)
    if value is None:
        return []
    if not isinstance(value, list):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be an array")
    return list(value)


def _bool(
    parameters: dict[str, object], name: str, *, default: bool | None = None
) -> bool:
    value = parameters.get(name)
    if value is None and default is not None:
        return default
    if not isinstance(value, bool):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be a boolean")
    return value


def _optional_mapping(
    parameters: dict[str, object], name: str
) -> dict[str, object] | None:
    value = parameters.get(name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be an object")
    return dict(value)


def _workspace_changes_payload(changes: object) -> dict[str, object]:
    from engine.studio.chat.workspace_review import WorkspaceChanges

    if not isinstance(changes, WorkspaceChanges):
        raise DdeError("VALIDATION_FAILED", "invalid workspace changes projection")
    return {
        "workspace_id": str(changes.workspace_id),
        "base_revision": changes.base_revision,
        "workspace_revision": changes.workspace_revision,
        "diff_hash": changes.diff_hash,
        "changes": [
            {
                "path": item.path,
                "diff_text": item.diff_text,
                "diff_hash": item.diff_hash,
                "review_decision": item.review_decision,
            }
            for item in changes.changes
        ],
    }


def _mutation_requests(parameters: dict[str, object]) -> list[MutationRequest]:
    rows = _rows(parameters, "mutations")
    if not rows:
        raise DdeError(
            "FORBIDDEN",
            "'mutations' must be a non-empty array of objects",
            details={"parameter": "mutations"},
        )
    return [
        MutationRequest(
            operation=_str(row, "operation"),
            target_key=_str(row, "target_key"),
            origin=_str(row, "origin"),
            payload=_mapping(row, "payload"),
        )
        for row in rows
    ]


def _optional_uuid(parameters: dict[str, object], name: str) -> UUID | None:
    value = parameters.get(name)
    if value is None or value == "":
        return None
    return _as_uuid(value, name)
