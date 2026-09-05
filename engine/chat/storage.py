"""Managed, scoped object storage for universal DDE Chat attachments.

The public Chat store preserves the historical API while delegating byte IO to
DDE's shared durable object layer. In ``auto`` mode R2 is selected when fully
configured; otherwise the local content-addressed backend is used. ``r2`` mode
fails closed if credentials are incomplete.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from engine.core.errors import DdeError
from engine.object_store.durable import (
    ScopedObjectStore,
    scoped_content_key,
    scoped_object_store_from_env,
)

CHAT_OBJECT_ROOT_ENV = "DDE_CHAT_OBJECT_ROOT"
DEFAULT_CHAT_OBJECT_ROOT = Path.home() / ".dde" / "chat-objects"


def storage_key_for_chat_object(
    *, tenant_id: UUID, project_id: UUID, content_hash: str
) -> str:
    return scoped_content_key(
        namespace="chat",
        tenant_id=tenant_id,
        project_id=project_id,
        content_hash=content_hash,
    )


@dataclass(frozen=True)
class ChatObjectStore:
    root: Path | None = None
    backend: ScopedObjectStore | None = None

    def _backend(self) -> ScopedObjectStore:
        if self.backend is not None:
            return self.backend
        root = self.root or Path(
            os.environ.get(CHAT_OBJECT_ROOT_ENV, str(DEFAULT_CHAT_OBJECT_ROOT))
        )
        return scoped_object_store_from_env(namespace="chat", local_root=root)

    @property
    def backend_name(self) -> str:
        return self._backend().backend_name

    def put(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        content_hash: str,
        content: bytes,
    ) -> str:
        return self._backend().put(
            tenant_id=tenant_id,
            project_id=project_id,
            content_hash=content_hash,
            content=content,
        )

    def read(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        key: str,
        max_bytes: int | None = None,
    ) -> bytes:
        try:
            return self._backend().read(
                tenant_id=tenant_id,
                project_id=project_id,
                key=key,
                max_bytes=max_bytes,
            )
        except DdeError as exc:
            if exc.error_code == "RESOURCE_EXHAUSTION":
                raise DdeError(
                    "ATTACHMENT_TOO_LARGE",
                    "Chat attachment exceeds the configured read bound",
                    retryable=False,
                    details=exc.details,
                ) from exc
            raise
