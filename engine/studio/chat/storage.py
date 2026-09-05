"""Managed, scoped object storage for DDE-069 Chat attachments.

The local filesystem adapter is intentionally content-addressed and scope-jail
verified. It is the current production implementation for DDE Code; a future
R2/S3 adapter must preserve this key contract rather than exposing provider
paths to Chat.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from engine.core.errors import DdeError

CHAT_OBJECT_ROOT_ENV = "DDE_CHAT_OBJECT_ROOT"
DEFAULT_CHAT_OBJECT_ROOT = Path.home() / ".dde" / "chat-objects"


def storage_key_for_chat_object(
    *, tenant_id: UUID, project_id: UUID, content_hash: str
) -> str:
    return f"chat/{tenant_id}/{project_id}/{content_hash}"


@dataclass(frozen=True)
class ChatObjectStore:
    root: Path | None = None

    def _root(self) -> Path:
        configured = self.root or Path(
            os.environ.get(CHAT_OBJECT_ROOT_ENV, str(DEFAULT_CHAT_OBJECT_ROOT))
        )
        return configured.expanduser().resolve()

    def _path_for_key(self, *, tenant_id: UUID, project_id: UUID, key: str) -> Path:
        expected = f"chat/{tenant_id}/{project_id}/"
        if not key.startswith(expected):
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Chat object key is outside the authorized project scope",
                retryable=False,
                details={"key": key, "expected_prefix": expected},
            )
        relative = Path(*key.split("/"))
        target = (self._root() / relative).resolve()
        root = self._root()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Chat object path escaped managed storage",
                retryable=False,
            ) from exc
        return target

    def put(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        content_hash: str,
        content: bytes,
    ) -> str:
        key = storage_key_for_chat_object(
            tenant_id=tenant_id, project_id=project_id, content_hash=content_hash
        )
        target = self._path_for_key(tenant_id=tenant_id, project_id=project_id, key=key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != content:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Content-addressed Chat object hash collision",
                    retryable=False,
                    details={"content_hash": content_hash},
                )
            return key
        fd, temporary = tempfile.mkstemp(prefix="dde-chat-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
        return key

    def read(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        key: str,
        max_bytes: int | None = None,
    ) -> bytes:
        target = self._path_for_key(tenant_id=tenant_id, project_id=project_id, key=key)
        if not target.is_file():
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "Chat attachment object is missing from managed storage",
                retryable=False,
                details={"storage_key": key},
            )
        if max_bytes is not None and target.stat().st_size > max_bytes:
            raise DdeError(
                "ATTACHMENT_TOO_LARGE",
                "Chat attachment exceeds the requested read bound",
                retryable=False,
                details={"size_bytes": target.stat().st_size, "max_bytes": max_bytes},
            )
        return target.read_bytes()
