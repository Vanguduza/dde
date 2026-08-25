"""Chapter 13.9 project-scoped git connections (isolation layer 3).

A git connection is bound to exactly one `(tenant_id, project_id,
remote_url)` triple at creation. `authorize_operation` refuses any URL the
connection was not bound to -- another project's repository on the same
host included -- before a git command can run, so a worker's general
repository capability never reaches another project's repository. Binding
validates the URL shape (scheme + host + non-empty path) and refuses
cross-project re-binding by construction: `bind` derives authorization
from the arguments themselves, so a "re-bind" with someone else's project
id is simply a different connection that their own scope checks would
reject.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from urllib.parse import urlsplit


class ProjectRepoScopeError(Exception):
    """An operation targets a repository outside the connection's scope."""


def _normalize_remote_url(remote_url: str) -> str:
    parts = urlsplit(remote_url)
    if parts.scheme not in ("https", "http", "ssh", "git", "file"):
        raise ProjectRepoScopeError(
            f"unsupported remote scheme: {parts.scheme!r}"
        )
    if not parts.netloc and parts.scheme != "file":
        raise ProjectRepoScopeError("remote URL has no host")
    if not parts.path.strip("/"):
        raise ProjectRepoScopeError("remote URL has no repository path")
    path = "/" + "/".join(segment for segment in parts.path.split("/") if segment)
    return f"{parts.scheme}://{parts.netloc}{path}"


@dataclass(frozen=True)
class GitConnectionScope:
    """One git connection bound to one project's repository."""

    tenant_id: UUID
    project_id: UUID
    remote_url: str

    def __post_init__(self) -> None:
        # Normalized once at bind time so later comparisons are exact.
        object.__setattr__(self, "remote_url", _normalize_remote_url(self.remote_url))

    @classmethod
    def bind(
        cls, *, tenant_id: UUID, project_id: UUID, remote_url: str
    ) -> "GitConnectionScope":
        return cls(tenant_id=tenant_id, project_id=project_id, remote_url=remote_url)

    def authorize_operation(self, operation: str, target_url: str) -> None:
        """Fail closed unless `target_url` is this connection's bound repo.

        `operation` is recorded in the error for audit purposes; fetch,
        push and clone are all governed identically.
        """
        normalized = _normalize_remote_url(target_url)
        if normalized != self.remote_url:
            raise ProjectRepoScopeError(
                f"git {operation} targets a repository outside this "
                "connection's project scope",
                {"bound": self.remote_url, "requested": normalized},
            )
