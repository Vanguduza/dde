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

from engine.core.errors import DdeError

WORM_CONTROL = "worm_retention"


class ScopeViolationError(Exception):
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
        """Raise `ScopeViolationError` unless `key` is exactly the canonical
        key for `(tenant_id, project_id)` -- any other tenant's or project's
        prefix fails closed."""
        expected = f"{self.root}/{tenant_id}/{project_id}/"
        if not key.startswith(expected):
            raise ScopeViolationError(
                "storage key is outside the authorized scope",
                {"key": key, "expected_prefix": expected},
            )

    def delete(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        key: str,
        evidence_linked: bool,
    ) -> None:
        """Chapter 17.5 object-layer WORM. Every byte delete must pass
        through this mediator. Evidence-linked keys are refused for the
        retention window; there is no overwrite/delete bypass."""

        self.verify_key(tenant_id=tenant_id, project_id=project_id, key=key)
        if evidence_linked:
            raise DdeError(
                "POLICY_DENIED",
                "WORM: evidence-linked object cannot be deleted during "
                "the retention window",
                retryable=False,
                details={"key": key, "control": WORM_CONTROL},
            )
