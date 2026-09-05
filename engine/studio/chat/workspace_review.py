"""Real isolated-workspace diff, patch and review operations for Chat."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_chat_change_review import FrontendChatChangeReview
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.chat.activity import FrontendChatActivityService
from engine.studio.tables import (
    frontend_chat_change_reviews,
    frontend_chat_checkpoints,
    frontend_conversations,
)
from engine.truth.db import open_unit_of_work
from engine.workspaces import git
from engine.workspaces.paths import resolve_within_workspace
from engine.workspaces.repository import WorkspaceRepository

MAX_PATCH_BYTES = 2 * 1024 * 1024
_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")


@dataclass(frozen=True)
class WorkspaceChange:
    path: str
    diff_text: str
    diff_hash: str
    review_decision: str


@dataclass(frozen=True)
class WorkspaceChanges:
    workspace_id: UUID
    base_revision: str
    workspace_revision: str | None
    diff_hash: str
    changes: tuple[WorkspaceChange, ...]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _snapshot_hash(changes: list[tuple[str, str]]) -> str:
    canonical = json.dumps(changes, sort_keys=True, ensure_ascii=False)
    return _hash_text(canonical)


def _patch_paths(patch_text: str) -> tuple[str, ...]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        match = _DIFF_HEADER.match(line)
        if match:
            paths.extend((match.group(1), match.group(2)))
    if not paths:
        raise DdeError(
            "VALIDATION_FAILED",
            "Chat workspace patch contains no diff --git path headers",
            retryable=False,
        )
    return tuple(dict.fromkeys(paths))


class FrontendChatWorkspaceReviewService:
    """Workspace-local code changes; never accepted-project mutation."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        activities: FrontendChatActivityService | None = None,
    ) -> None:
        self._engine = engine
        self._activities = activities or FrontendChatActivityService(engine)

    async def _conversation_workspace(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        workspace_id: UUID | None = None,
    ) -> Workspace:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            conversation = (
                (
                    await uow.connection.execute(
                        select(frontend_conversations).where(
                            frontend_conversations.c.conversation_id == conversation_id,
                            frontend_conversations.c.tenant_id == tenant_id,
                            frontend_conversations.c.project_id == project_id,
                            frontend_conversations.c.status == "OPEN",
                        )
                    )
                )
                .mappings()
                .first()
            )
            if conversation is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown open Chat conversation", retryable=False
                )
            active = conversation["active_workspace_id"]
            resolved = workspace_id or active
            if resolved is None:
                raise DdeError(
                    "WORKSPACE_UNAVAILABLE",
                    "Chat conversation has no active workspace",
                    retryable=False,
                )
            if active is not None and resolved != active:
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "Chat operation may address only the conversation's "
                    "active workspace",
                    retryable=False,
                )
            workspace = await WorkspaceRepository().get_workspace(
                uow.connection, resolved
            )
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
        if workspace.status not in {"READY", "IN_USE"} or not workspace.workspace_path:
            raise DdeError(
                "WORKSPACE_UNAVAILABLE",
                "Chat active workspace is not readable",
                retryable=False,
                details={"status": workspace.status},
            )
        if not workspace.base_revision:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "Chat workspace has no base revision for diff review",
                retryable=False,
            )
        return workspace

    @staticmethod
    def _root(workspace: Workspace) -> Path:
        if not workspace.workspace_path:
            raise DdeError("WORKSPACE_UNAVAILABLE", "workspace path is absent")
        return Path(workspace.workspace_path)

    @staticmethod
    def _validate_path(workspace: Workspace, relative_path: str) -> str:
        clean = relative_path.strip().replace("\\", "/")
        if not clean:
            raise DdeError("VALIDATION_FAILED", "workspace path is required")
        resolve_within_workspace(
            FrontendChatWorkspaceReviewService._root(workspace), clean
        )
        return clean

    async def changes(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
    ) -> WorkspaceChanges:
        workspace = await self._conversation_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        root = self._root(workspace)
        base_revision = workspace.base_revision
        if base_revision is None:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "Chat workspace has no base revision for diff review",
                retryable=False,
            )
        paths = git.changed_paths(root)
        pairs: list[tuple[str, str]] = []
        for path in paths:
            self._validate_path(workspace, path)
            pairs.append(
                (path, git.unified_diff(root, workspace.base_revision or "HEAD", path))
            )
        snapshot_hash = _snapshot_hash(pairs)
        reviews = await self._reviews(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace_id=workspace.workspace_id,
        )
        latest: dict[tuple[str, str], str] = {
            (item.path, item.diff_hash): item.decision for item in reviews
        }
        result = WorkspaceChanges(
            workspace_id=workspace.workspace_id,
            base_revision=base_revision,
            workspace_revision=workspace.current_revision,
            diff_hash=snapshot_hash,
            changes=tuple(
                WorkspaceChange(
                    path=path,
                    diff_text=diff_text,
                    diff_hash=_hash_text(diff_text),
                    review_decision=latest.get(
                        (path, _hash_text(diff_text)), "PENDING"
                    ),
                )
                for path, diff_text in pairs
            ),
        )
        return result

    async def apply_patch(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        patch_text: str,
        expected_diff_hash: str | None = None,
    ) -> WorkspaceChanges:
        if len(patch_text.encode("utf-8")) > MAX_PATCH_BYTES:
            raise DdeError(
                "VALIDATION_FAILED",
                "Chat patch exceeds workspace patch policy",
                retryable=False,
                details={"max_bytes": MAX_PATCH_BYTES},
            )
        workspace = await self._conversation_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        before = await self.changes(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        if expected_diff_hash is not None and expected_diff_hash != before.diff_hash:
            raise DdeError(
                "DIFF_STALE",
                "Chat workspace changed after this patch was prepared",
                retryable=False,
                details={"expected": expected_diff_hash, "actual": before.diff_hash},
            )
        for path in _patch_paths(patch_text):
            self._validate_path(workspace, path)
        try:
            git.apply_patch(self._root(workspace), patch_text)
        except git.GitCommandError as exc:
            raise DdeError(
                "VALIDATION_FAILED",
                "Chat workspace patch failed git apply validation",
                retryable=False,
                details={"reason": exc.stderr.strip()},
            ) from exc
        after = await self.changes(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace_id=workspace.workspace_id,
            kind="TOOL_RESULT",
            state="COMPLETED",
            label="Applied Chat workspace patch",
            refs={"before_diff_hash": before.diff_hash, "diff_hash": after.diff_hash},
        )
        return after

    async def accept_file(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        path: str,
        expected_diff_hash: str,
        principal_id: UUID,
    ) -> FrontendChatChangeReview:
        current = await self.changes(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        change = next((item for item in current.changes if item.path == path), None)
        if change is None or change.diff_hash != expected_diff_hash:
            raise DdeError(
                "DIFF_STALE",
                "file diff no longer matches the review target",
                retryable=False,
            )
        workspace = await self._conversation_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        return await self._write_review(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace=workspace,
            path=path,
            diff_hash=change.diff_hash,
            decision="ACCEPTED",
            principal_id=principal_id,
        )

    async def revert_file(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        path: str,
        expected_diff_hash: str,
        principal_id: UUID,
    ) -> WorkspaceChanges:
        current = await self.changes(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        change = next((item for item in current.changes if item.path == path), None)
        if change is None or change.diff_hash != expected_diff_hash:
            raise DdeError(
                "DIFF_STALE", "file diff changed before revert", retryable=False
            )
        workspace = await self._conversation_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        clean = self._validate_path(workspace, path)
        git.restore_path(
            self._root(workspace), workspace.base_revision or "HEAD", clean
        )
        await self._write_review(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace=workspace,
            path=path,
            diff_hash=change.diff_hash,
            decision="REVERTED",
            principal_id=principal_id,
        )
        after = await self.changes(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace_id=workspace.workspace_id,
            kind="FILE_REVERTED",
            state="COMPLETED",
            label=f"Reverted {path}",
            refs={"path": path, "old_diff_hash": expected_diff_hash},
        )
        return after

    async def revert_all(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        checkpoint_id: UUID,
        principal_id: UUID,
    ) -> WorkspaceChanges:
        current = await self.changes(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        workspace = await self._conversation_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            checkpoint = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_checkpoints).where(
                            frontend_chat_checkpoints.c.checkpoint_id == checkpoint_id,
                            frontend_chat_checkpoints.c.conversation_id
                            == conversation_id,
                            frontend_chat_checkpoints.c.workspace_id
                            == workspace.workspace_id,
                            frontend_chat_checkpoints.c.tenant_id == tenant_id,
                            frontend_chat_checkpoints.c.project_id == project_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
        if checkpoint is None or checkpoint["diff_hash"] != current.diff_hash:
            raise DdeError(
                "CHECKPOINT_STALE",
                "revert-all requires a checkpoint of the exact current diff",
                retryable=False,
            )
        for change in current.changes:
            clean = self._validate_path(workspace, change.path)
            git.restore_path(
                self._root(workspace), workspace.base_revision or "HEAD", clean
            )
            await self._write_review(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                workspace=workspace,
                path=change.path,
                diff_hash=change.diff_hash,
                decision="REVERTED",
                principal_id=principal_id,
            )
        after = await self.changes(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace_id=workspace.workspace_id,
            kind="FILE_REVERTED",
            state="COMPLETED",
            label="Reverted all Chat workspace changes",
            refs={"checkpoint_id": str(checkpoint_id), "paths": len(current.changes)},
        )
        return after

    async def _write_review(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        workspace: Workspace,
        path: str,
        diff_hash: str,
        decision: str,
        principal_id: UUID,
    ) -> FrontendChatChangeReview:
        now = datetime.now(UTC)
        record = FrontendChatChangeReview(
            review_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace_id=workspace.workspace_id,
            path=path,
            base_revision=workspace.base_revision,
            workspace_revision=workspace.current_revision,
            diff_hash=diff_hash,
            decision=decision,
            reviewed_by=principal_id,
            reviewed_at=now,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            prior = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_change_reviews).where(
                            frontend_chat_change_reviews.c.conversation_id
                            == conversation_id,
                            frontend_chat_change_reviews.c.workspace_id
                            == workspace.workspace_id,
                            frontend_chat_change_reviews.c.path == path,
                            frontend_chat_change_reviews.c.diff_hash == diff_hash,
                        )
                    )
                )
                .mappings()
                .first()
            )
            if prior is None:
                await uow.connection.execute(
                    frontend_chat_change_reviews.insert().values(**record.model_dump())
                )
            else:
                await uow.connection.execute(
                    update(frontend_chat_change_reviews)
                    .where(
                        frontend_chat_change_reviews.c.review_id == prior["review_id"]
                    )
                    .values(
                        decision=decision,
                        reviewed_by=principal_id,
                        reviewed_at=now,
                        lock_version=frontend_chat_change_reviews.c.lock_version + 1,
                        updated_at=now,
                    )
                )
                row = (
                    (
                        await uow.connection.execute(
                            select(frontend_chat_change_reviews).where(
                                frontend_chat_change_reviews.c.review_id
                                == prior["review_id"]
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                record = FrontendChatChangeReview.model_validate(dict(row))
            await uow.commit()
        return record

    async def _reviews(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        workspace_id: UUID,
    ) -> tuple[FrontendChatChangeReview, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_change_reviews)
                        .where(
                            frontend_chat_change_reviews.c.conversation_id
                            == conversation_id,
                            frontend_chat_change_reviews.c.workspace_id == workspace_id,
                            frontend_chat_change_reviews.c.tenant_id == tenant_id,
                            frontend_chat_change_reviews.c.project_id == project_id,
                        )
                        .order_by(frontend_chat_change_reviews.c.updated_at)
                    )
                )
                .mappings()
                .all()
            )
        return tuple(FrontendChatChangeReview.model_validate(dict(row)) for row in rows)
