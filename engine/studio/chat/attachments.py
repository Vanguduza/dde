"""Cursor-class Chat attachment lifecycle and bounded text extraction."""

from __future__ import annotations

import hashlib
import mimetypes
from datetime import UTC, datetime
from pathlib import PurePath
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_chat_attachment import FrontendChatAttachment
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.chat.activity import FrontendChatActivityService
from engine.studio.chat.storage import ChatObjectStore
from engine.studio.tables import frontend_chat_attachments, frontend_conversations
from engine.truth.db import open_unit_of_work
from engine.workspaces.repository import WorkspaceRepository
from engine.workspaces.service import WorkspaceService

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_TEXT_CHARS = 200_000
_TEXT_MEDIA_PREFIXES = ("text/",)
_TEXT_MEDIA_TYPES = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/yaml",
    "application/x-yaml",
}
_TEXT_EXTENSIONS = {
    ".md",
    ".mdx",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".xml",
    ".csv",
    ".tsv",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".kt",
    ".kts",
    ".java",
    ".rs",
    ".go",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
}


def _safe_filename(value: str) -> str:
    name = value.strip()
    if not name or PurePath(name).name != name or name in {".", ".."}:
        raise DdeError(
            "VALIDATION_FAILED",
            "attachment filename must be a display basename, not a path",
            retryable=False,
        )
    if len(name) > 255:
        raise DdeError(
            "VALIDATION_FAILED", "attachment filename is too long", retryable=False
        )
    return name


def _extract_text(
    filename: str, media_type: str, content: bytes
) -> tuple[str, str | None]:
    suffix = PurePath(filename).suffix.lower()
    textual = (
        media_type.startswith(_TEXT_MEDIA_PREFIXES)
        or media_type in _TEXT_MEDIA_TYPES
        or suffix in _TEXT_EXTENSIONS
    )
    if not textual:
        return "UNSUPPORTED", None
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        return "FAILED", None
    if len(decoded) > MAX_EXTRACTED_TEXT_CHARS:
        decoded = decoded[:MAX_EXTRACTED_TEXT_CHARS]
    return "EXTRACTED", decoded


class FrontendChatAttachmentService:
    """Sole writer of attachment metadata; bytes live in managed storage."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        store: ChatObjectStore | None = None,
        workspaces: WorkspaceService | None = None,
        activities: FrontendChatActivityService | None = None,
    ) -> None:
        self._engine = engine
        self._store = store or ChatObjectStore()
        self._workspaces = workspaces or WorkspaceService(engine)
        self._activities = activities or FrontendChatActivityService(engine)

    async def reserve(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        filename: str,
        media_type: str,
        size_bytes: int,
        created_by: UUID | None,
        source_kind: str = "UPLOAD",
        workspace_path: str | None = None,
    ) -> FrontendChatAttachment:
        filename = _safe_filename(filename)
        if size_bytes < 0 or size_bytes > MAX_ATTACHMENT_BYTES:
            raise DdeError(
                "ATTACHMENT_TOO_LARGE",
                "attachment exceeds Chat upload policy",
                retryable=False,
                details={"size_bytes": size_bytes, "max_bytes": MAX_ATTACHMENT_BYTES},
            )
        now = datetime.now(UTC)
        record = FrontendChatAttachment(
            attachment_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            turn_id=None,
            source_kind=source_kind,
            filename=filename,
            media_type=(media_type.strip() or "application/octet-stream"),
            size_bytes=size_bytes,
            content_hash=None,
            storage_key=None,
            workspace_path=workspace_path,
            extraction_state="PENDING",
            extracted_text=None,
            status="RESERVED",
            created_by=created_by,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            exists = await uow.connection.scalar(
                select(frontend_conversations.c.conversation_id).where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                    frontend_conversations.c.status == "OPEN",
                )
            )
            if exists is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "attachment target is not an open Chat conversation",
                    retryable=False,
                )
            await uow.connection.execute(
                frontend_chat_attachments.insert().values(**record.model_dump())
            )
            await uow.commit()
        return record

    async def complete_upload(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        attachment_id: UUID,
        content: bytes,
    ) -> FrontendChatAttachment:
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise DdeError(
                "ATTACHMENT_TOO_LARGE",
                "attachment exceeds Chat upload policy",
                retryable=False,
                details={"size_bytes": len(content), "max_bytes": MAX_ATTACHMENT_BYTES},
            )
        content_hash = hashlib.sha256(content).hexdigest()
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_attachments)
                        .where(
                            frontend_chat_attachments.c.attachment_id == attachment_id,
                            frontend_chat_attachments.c.conversation_id
                            == conversation_id,
                            frontend_chat_attachments.c.tenant_id == tenant_id,
                            frontend_chat_attachments.c.project_id == project_id,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown Chat attachment", retryable=False
                )
            current = FrontendChatAttachment.model_validate(dict(row))
            if current.status == "ACTIVE":
                if current.content_hash == content_hash and current.size_bytes == len(
                    content
                ):
                    return current
                raise DdeError(
                    "VERSION_CONFLICT",
                    "attachment upload already completed with different bytes",
                    retryable=False,
                )
            if current.status != "RESERVED":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "attachment is not uploadable in its current state",
                    retryable=False,
                    details={"status": current.status},
                )
            if current.size_bytes != len(content):
                raise DdeError(
                    "VERSION_CONFLICT",
                    "uploaded byte count does not match reservation",
                    retryable=False,
                    details={"reserved": current.size_bytes, "actual": len(content)},
                )
            storage_key = self._store.put(
                tenant_id=tenant_id,
                project_id=project_id,
                content_hash=content_hash,
                content=content,
            )
            extraction_state, extracted_text = _extract_text(
                current.filename, current.media_type, content
            )
            await uow.connection.execute(
                update(frontend_chat_attachments)
                .where(frontend_chat_attachments.c.attachment_id == attachment_id)
                .values(
                    content_hash=content_hash,
                    storage_key=storage_key,
                    extraction_state=extraction_state,
                    extracted_text=extracted_text,
                    status="ACTIVE",
                    lock_version=frontend_chat_attachments.c.lock_version + 1,
                    updated_at=now,
                )
            )
            updated = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_attachments).where(
                            frontend_chat_attachments.c.attachment_id == attachment_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            await uow.commit()
        record = FrontendChatAttachment.model_validate(dict(updated))
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            kind="ATTACHMENT_ADDED",
            state="COMPLETED",
            label=f"Attached {record.filename}",
            refs={
                "attachment_id": str(record.attachment_id),
                "content_hash": content_hash,
            },
        )
        return record

    async def import_workspace_file(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        workspace_id: UUID,
        relative_path: str,
        created_by: UUID | None,
    ) -> FrontendChatAttachment:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            workspace = await WorkspaceRepository().get_workspace(
                uow.connection, workspace_id
            )
        workspace = self._require_workspace_scope(
            workspace, tenant_id=tenant_id, project_id=project_id
        )
        content = self._workspaces.read(workspace, relative_path)
        media_type = (
            mimetypes.guess_type(relative_path)[0] or "application/octet-stream"
        )
        reserved = await self.reserve(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            filename=PurePath(relative_path).name,
            media_type=media_type,
            size_bytes=len(content),
            created_by=created_by,
            source_kind="WORKSPACE_FILE",
            workspace_path=relative_path,
        )
        return await self.complete_upload(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            attachment_id=reserved.attachment_id,
            content=content,
        )

    @staticmethod
    def _require_workspace_scope(
        workspace: Workspace | None, *, tenant_id: UUID, project_id: UUID
    ) -> Workspace:
        if (
            workspace is None
            or workspace.tenant_id != tenant_id
            or workspace.project_id != project_id
        ):
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "workspace is outside Chat project scope",
                retryable=False,
            )
        if workspace.status not in {"READY", "IN_USE"}:
            raise DdeError(
                "WORKSPACE_UNAVAILABLE",
                "workspace is not available for Chat file context",
                retryable=False,
                details={"status": workspace.status},
            )
        return workspace

    async def list_for_conversation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        include_removed: bool = False,
    ) -> tuple[FrontendChatAttachment, ...]:
        conditions = [
            frontend_chat_attachments.c.conversation_id == conversation_id,
            frontend_chat_attachments.c.tenant_id == tenant_id,
            frontend_chat_attachments.c.project_id == project_id,
        ]
        if not include_removed:
            conditions.append(frontend_chat_attachments.c.status != "REMOVED")
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_attachments)
                        .where(*conditions)
                        .order_by(frontend_chat_attachments.c.created_at)
                    )
                )
                .mappings()
                .all()
            )
        return tuple(FrontendChatAttachment.model_validate(dict(row)) for row in rows)

    async def require_active_ids(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        attachment_ids: tuple[UUID, ...],
    ) -> tuple[FrontendChatAttachment, ...]:
        if not attachment_ids:
            return ()
        records = await self.list_for_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        by_id = {
            item.attachment_id: item for item in records if item.status == "ACTIVE"
        }
        missing = [str(item) for item in attachment_ids if item not in by_id]
        if missing:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "one or more Chat attachments are not active in this conversation",
                retryable=False,
                details={"attachment_ids": missing},
            )
        return tuple(by_id[item] for item in attachment_ids)

    async def bind_to_turn(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        turn_id: UUID,
        attachment_ids: tuple[UUID, ...],
    ) -> None:
        if not attachment_ids:
            return
        await self.require_active_ids(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            attachment_ids=attachment_ids,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            for attachment_id in attachment_ids:
                await uow.connection.execute(
                    update(frontend_chat_attachments)
                    .where(
                        frontend_chat_attachments.c.attachment_id == attachment_id,
                        frontend_chat_attachments.c.turn_id.is_(None),
                    )
                    .values(
                        turn_id=turn_id,
                        lock_version=frontend_chat_attachments.c.lock_version + 1,
                        updated_at=datetime.now(UTC),
                    )
                )
            await uow.commit()

    async def remove(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        attachment_id: UUID,
    ) -> FrontendChatAttachment:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        update(frontend_chat_attachments)
                        .where(
                            frontend_chat_attachments.c.attachment_id == attachment_id,
                            frontend_chat_attachments.c.conversation_id
                            == conversation_id,
                            frontend_chat_attachments.c.tenant_id == tenant_id,
                            frontend_chat_attachments.c.project_id == project_id,
                            frontend_chat_attachments.c.status != "REMOVED",
                        )
                        .values(
                            status="REMOVED",
                            lock_version=frontend_chat_attachments.c.lock_version + 1,
                            updated_at=now,
                        )
                        .returning(frontend_chat_attachments)
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown active Chat attachment", retryable=False
                )
            await uow.commit()
        return FrontendChatAttachment.model_validate(dict(row))
