"""Canonical hashes for Chapter 13.1 scope_hash."""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def approval_scope_hash(
    *,
    approval_type: str,
    mission_id: UUID,
    payload: dict[str, object],
    task_id: UUID | None = None,
) -> str:
    """Identity of the exact plan/action an Approval binds to.

    A re-planned action with a different payload produces a different hash
    and cannot consume a prior approval (Chapter 13.1).
    """
    return sha256_hex(
        canonical_json(
            {
                "approval_type": approval_type,
                "mission_id": str(mission_id),
                "task_id": None if task_id is None else str(task_id),
                "payload": payload,
            }
        )
    )
