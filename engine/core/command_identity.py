"""Canonical logical-command fingerprinting shared by Gateway and Chat plans.

The identity deliberately excludes attempt-specific envelope fields so an
idempotent retry hashes exactly like the first request. Secret redaction remains
the caller's responsibility because only the owning command knows which fields
are secret.
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID


def logical_command_hash(
    *,
    command_type: str,
    target_type: str,
    target_id: UUID,
    parameters: dict[str, object],
    protocol_version: str,
) -> str:
    canonical = json.dumps(
        {
            "command_type": command_type,
            "target_type": target_type,
            "target_id": str(target_id),
            "parameters": parameters,
            "protocol_version": protocol_version,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
