"""Chapter 13.9 object-storage key prefixes (isolation layer 2).

Artifact bytes are content-addressed by SHA-256, but the storage KEY is
scope-derived: `<root>/<tenant_id>/<project_id>/<content_hash>`. The
mediator (`ArtifactObjectStore.verify_key`) rejects any key outside the
caller's scope even when every id inside it is individually valid --
Chapter 13.9's "rejects cross-scope references" at the object layer. A
future R2/S3 adapter must route every byte operation through this module;
no caller may construct artifact keys by string concatenation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


class ScopeViolation(Exception):
    """A storage key references a scope the caller is not authorized for."""


def storage_key_for_artifact(
    *, tenant_id: UUID, project_id: UUID, content_hash: str
) -> str:
    """Derive the canonical storage key from scope + content hash."""
    return f"artifacts/{tenant_id}/{project_id}/{content_hash}"


@dataclass(frozen=True)
class ArtifactObjectStore:
    """Mediated access to artifact keys under one root prefix."""

    root: str = "artifacts"

    def verify_key(self, *, tenant_id: UUID, project_id: UUID, key: str) -> None:
        """Raise `ScopeViolation` unless `key` is exactly the canonical key
        for `(tenant_id, project_id)` -- any other tenant's or project's
        prefix fails closed."""
        expected = (
            f"{self.root}/{tenant_id}/{project_id}/"
        )
        if not key.startswith(expected):
            raise ScopeViolation(
                "storage key is outside the authorized scope",
                {"key": key, "expected_prefix": expected},
            )
