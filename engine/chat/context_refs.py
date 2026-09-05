"""Normalized Cursor-class Chat context references and visible budget assembly."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.attachments import FrontendChatAttachmentService
from engine.chat.plans import FrontendChatPlanService
from engine.core.errors import DdeError
from engine.fabric.memory import MemoryService
from engine.studio.candidates.service import CandidateService
from engine.studio.pxg.service import PxgService
from engine.truth.db import open_unit_of_work
from engine.truth.repository import TruthRepository
from engine.workspaces.paths import resolve_within_workspace
from engine.workspaces.repository import WorkspaceRepository

DEFAULT_CONTEXT_BUDGET_TOKENS = 32_000
MAX_CONTEXT_FILE_BYTES = 256_000
MAX_FOLDER_ENTRIES = 200
_REF = re.compile(
    r"(?<!\w)@(?P<kind>file|folder|screen|candidate|component|finding|plan|workspace|"
    r"attachment|memory|requirement|edr):(?P<value>[^\s,;]+)",
    re.IGNORECASE,
)
SUPPORTED_CONTEXT_KINDS = frozenset(
    {
        "file",
        "folder",
        "screen",
        "candidate",
        "component",
        "finding",
        "plan",
        "workspace",
        "attachment",
        "memory",
        "requirement",
        "edr",
    }
)


@dataclass(frozen=True)
class ResolvedContextRef:
    ref: str
    kind: str
    state: str
    summary: str
    text: str | None
    estimated_tokens: int
    source_revision: str | None = None


@dataclass(frozen=True)
class ContextBudget:
    estimated_tokens: int
    budget_tokens: int
    included_refs: tuple[str, ...]
    omitted_refs: tuple[str, ...]
    omission_reasons: dict[str, str]
    items: tuple[ResolvedContextRef, ...]


def normalize_ref(raw: str) -> str:
    value = raw.strip()
    if value.startswith("@"):
        value = value[1:]
    kind, sep, target = value.partition(":")
    kind = kind.lower().strip()
    target = target.strip()
    if not sep or kind not in SUPPORTED_CONTEXT_KINDS or not target:
        raise DdeError(
            "VALIDATION_FAILED",
            "Chat context ref must be kind:value with an admitted kind",
            retryable=False,
            details={"context_ref": raw},
        )
    return f"{kind}:{target}"


def parse_inline_refs(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            normalize_ref(f"{match.group('kind')}:{match.group('value')}")
            for match in _REF.finditer(text)
        )
    )


def _tokens(text: str | None) -> int:
    return math.ceil(len(text or "") / 4)


class FrontendChatContextService:
    """Resolve all Chat context through existing scoped authorities."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        attachments: FrontendChatAttachmentService | None = None,
        plans: FrontendChatPlanService | None = None,
        memory: MemoryService | None = None,
    ) -> None:
        self._engine = engine
        self._attachments = attachments or FrontendChatAttachmentService(engine)
        self._plans = plans or FrontendChatPlanService(engine)
        self._memory = memory or MemoryService(engine)
        self._pxg = PxgService(engine)
        self._candidates = CandidateService(engine, pxg=self._pxg)
        self._truth = TruthRepository()

    async def assemble(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        refs: tuple[str, ...],
        budget_tokens: int = DEFAULT_CONTEXT_BUDGET_TOKENS,
    ) -> ContextBudget:
        if budget_tokens <= 0:
            raise DdeError(
                "VALIDATION_FAILED", "context budget must be positive", retryable=False
            )
        resolved: list[ResolvedContextRef] = []
        for ref in tuple(dict.fromkeys(normalize_ref(item) for item in refs)):
            resolved.append(
                await self.resolve(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    conversation_id=conversation_id,
                    ref=ref,
                )
            )
        included: list[ResolvedContextRef] = []
        omitted: list[str] = []
        reasons: dict[str, str] = {}
        used = 0
        for item in resolved:
            if item.state != "AVAILABLE":
                omitted.append(item.ref)
                reasons[item.ref] = item.summary
                continue
            if used + item.estimated_tokens > budget_tokens:
                omitted.append(item.ref)
                reasons[item.ref] = "CONTEXT_BUDGET_EXCEEDED"
                continue
            included.append(item)
            used += item.estimated_tokens
        return ContextBudget(
            estimated_tokens=used,
            budget_tokens=budget_tokens,
            included_refs=tuple(item.ref for item in included),
            omitted_refs=tuple(omitted),
            omission_reasons=reasons,
            items=tuple(included),
        )

    async def resolve(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        ref: str,
    ) -> ResolvedContextRef:
        normalized = normalize_ref(ref)
        kind, target = normalized.split(":", 1)
        if kind in {"file", "folder", "workspace"}:
            return await self._resolve_workspace_ref(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                kind=kind,
                target=target,
                ref=normalized,
            )
        if kind == "attachment":
            try:
                attachment_id = UUID(target)
            except ValueError as exc:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "invalid attachment context id",
                    retryable=False,
                ) from exc
            records = await self._attachments.require_active_ids(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                attachment_ids=(attachment_id,),
            )
            item = records[0]
            text = item.extracted_text
            state = "AVAILABLE" if text is not None else "UNAVAILABLE"
            summary = (
                f"attachment {item.filename}"
                if state == "AVAILABLE"
                else f"attachment extraction is {item.extraction_state}"
            )
            return ResolvedContextRef(
                ref=normalized,
                kind=kind,
                state=state,
                summary=summary,
                text=text,
                estimated_tokens=_tokens(text),
                source_revision=item.content_hash,
            )
        if kind == "memory":
            try:
                memory_id = UUID(target)
            except ValueError as exc:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "invalid memory context id",
                    retryable=False,
                ) from exc
            memory = await self._memory.get(
                tenant_id=tenant_id, project_id=project_id, memory_id=memory_id
            )
            if memory.status not in {"APPROVED", "CANDIDATE"}:
                return ResolvedContextRef(
                    normalized,
                    kind,
                    "UNAVAILABLE",
                    f"memory is {memory.status.lower()}",
                    None,
                    0,
                    memory.content_hash,
                )
            body = self._memory.read_content(memory, max_bytes=256_000)
            max_chars = 16_000
            truncated = len(body) > max_chars
            text = body[:max_chars]
            if truncated:
                text = (
                    text.rstrip() + "\n… [explicit memory truncated to 4k-token bound]"
                )
            trust_note = f"{memory.trust_class}/{memory.status}"
            if memory.status == "CANDIDATE":
                text = "[UNAPPROVED MEMORY CANDIDATE — advisory context only]\n" + text
            return ResolvedContextRef(
                normalized,
                kind,
                "AVAILABLE",
                f"memory {memory.memory_id} ({trust_note})",
                text,
                _tokens(text),
                memory.content_hash,
            )
        if kind == "plan":
            plan = await self._plans.get(
                tenant_id=tenant_id, project_id=project_id, plan_id=UUID(target)
            )
            text = "\n".join(
                [f"Plan: {plan.title}", plan.objective]
                + [
                    f"{step.sequence}. [{step.state}] {step.title}: {step.description}"
                    for step in plan.steps
                ]
            )
            return ResolvedContextRef(
                normalized,
                kind,
                "AVAILABLE",
                f"plan {plan.title} ({plan.state})",
                text,
                _tokens(text),
                str(plan.lock_version),
            )
        if kind in {"screen", "component"}:
            graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
            node = graph.node_by_key(target)
            if node is None:
                return ResolvedContextRef(
                    normalized,
                    kind,
                    "UNAVAILABLE",
                    "PXG key does not exist",
                    None,
                    0,
                    str(graph.revision),
                )
            text = (
                f"{node.node_kind} {node.pxg_key}: {node.title}\n"
                f"attributes={node.attributes}\n"
                f"provenance={node.provenance}"
            )
            return ResolvedContextRef(
                normalized,
                kind,
                "AVAILABLE",
                f"{node.node_kind} {node.title}",
                text,
                _tokens(text),
                str(graph.revision),
            )
        if kind == "candidate":
            try:
                candidate_id = UUID(target)
            except ValueError as exc:
                raise DdeError(
                    "VALIDATION_FAILED", "invalid candidate context id", retryable=False
                ) from exc
            view = await self._candidates.view(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
            )
            candidate = view.candidate
            text = (
                f"candidate={candidate.candidate_id} state={candidate.state} "
                f"scope={candidate.scope_keys} "
                f"base_pxg_revision={candidate.base_pxg_revision} "
                f"verification_run_id={candidate.verification_run_id}"
            )
            return ResolvedContextRef(
                normalized,
                kind,
                "AVAILABLE",
                f"candidate {candidate.title} ({candidate.state})",
                text,
                _tokens(text),
                str(view.current_pxg_revision),
            )
        if kind in {"requirement", "edr"}:
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                if kind == "requirement":
                    requirement = await self._truth.get_requirement_by_slug(
                        uow.connection, project_id, target
                    )
                    payload = (
                        requirement.model_dump(mode="json") if requirement else None
                    )
                else:
                    edr = await self._truth.get_edr_by_slug(
                        uow.connection, project_id, target
                    )
                    payload = edr.model_dump(mode="json") if edr else None
            if payload is None:
                return ResolvedContextRef(
                    normalized, kind, "UNAVAILABLE", f"{kind} not found", None, 0
                )
            text = json_dumps(payload)
            return ResolvedContextRef(
                normalized,
                kind,
                "AVAILABLE",
                f"{kind} {target}",
                text,
                _tokens(text),
                str(payload.get("version") or payload.get("updated_at") or ""),
            )
        if kind == "finding":
            # Screen Audit is an adopted DDE-069 dependency. Until its stashed
            # Packet C is restored after this Chat checkpoint, fail closed here.
            return ResolvedContextRef(
                normalized,
                kind,
                "UNAVAILABLE",
                "Screen Audit finding projection is not yet active in this checkpoint",
                None,
                0,
            )
        raise DdeError("VALIDATION_FAILED", "unsupported Chat context ref")

    async def _resolve_workspace_ref(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        kind: str,
        target: str,
        ref: str,
    ) -> ResolvedContextRef:
        from sqlalchemy import select

        from engine.chat.tables import frontend_conversations

        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            conversation = (
                await uow.connection.execute(
                    select(frontend_conversations.c.active_workspace_id).where(
                        frontend_conversations.c.conversation_id == conversation_id,
                        frontend_conversations.c.tenant_id == tenant_id,
                        frontend_conversations.c.project_id == project_id,
                    )
                )
            ).scalar_one_or_none()
            if conversation is None:
                return ResolvedContextRef(
                    ref, kind, "UNAVAILABLE", "no active Chat workspace", None, 0
                )
            workspace = await WorkspaceRepository().get_workspace(
                uow.connection, conversation
            )
        if (
            workspace is None
            or workspace.tenant_id != tenant_id
            or workspace.project_id != project_id
            or not workspace.workspace_path
        ):
            return ResolvedContextRef(
                ref, kind, "UNAVAILABLE", "active Chat workspace unavailable", None, 0
            )
        root = Path(workspace.workspace_path)
        if kind == "workspace":
            if target not in {str(workspace.workspace_id), "active"}:
                return ResolvedContextRef(
                    ref,
                    kind,
                    "UNAVAILABLE",
                    "workspace ref is not the active workspace",
                    None,
                    0,
                )
            text = (
                f"workspace={workspace.workspace_id} status={workspace.status} "
                f"base_revision={workspace.base_revision} "
                f"current_revision={workspace.current_revision}"
            )
            return ResolvedContextRef(
                ref,
                kind,
                "AVAILABLE",
                f"active workspace {workspace.workspace_id}",
                text,
                _tokens(text),
                workspace.current_revision,
            )
        path = resolve_within_workspace(root, target)
        if kind == "file":
            if not path.is_file():
                return ResolvedContextRef(
                    ref, kind, "UNAVAILABLE", "workspace file does not exist", None, 0
                )
            size = path.stat().st_size
            if size > MAX_CONTEXT_FILE_BYTES:
                return ResolvedContextRef(
                    ref,
                    kind,
                    "UNAVAILABLE",
                    f"workspace file exceeds {MAX_CONTEXT_FILE_BYTES} "
                    "byte context bound",
                    None,
                    0,
                    workspace.current_revision,
                )
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return ResolvedContextRef(
                    ref,
                    kind,
                    "UNAVAILABLE",
                    "workspace file is not UTF-8 text",
                    None,
                    0,
                )
            return ResolvedContextRef(
                ref,
                kind,
                "AVAILABLE",
                f"workspace file {target}",
                text,
                _tokens(text),
                workspace.current_revision,
            )
        if not path.is_dir():
            return ResolvedContextRef(
                ref, kind, "UNAVAILABLE", "workspace folder does not exist", None, 0
            )
        entries = sorted(
            child.relative_to(root).as_posix()
            for child in path.rglob("*")
            if child.is_file()
        )
        truncated = len(entries) > MAX_FOLDER_ENTRIES
        visible = entries[:MAX_FOLDER_ENTRIES]
        text = "\n".join(visible)
        summary = f"workspace folder {target}: {len(entries)} files"
        if truncated:
            summary += f"; first {MAX_FOLDER_ENTRIES} included"
        return ResolvedContextRef(
            ref,
            kind,
            "AVAILABLE",
            summary,
            text,
            _tokens(text),
            workspace.current_revision,
        )


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def budget_dict(value: ContextBudget) -> dict[str, object]:
    return {
        "estimated_tokens": value.estimated_tokens,
        "budget_tokens": value.budget_tokens,
        "included_refs": list(value.included_refs),
        "omitted_refs": list(value.omitted_refs),
        "omission_reasons": dict(value.omission_reasons),
        "items": [asdict(item) for item in value.items],
    }
