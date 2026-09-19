"""Deterministic discovery-candidate identity.

Independent discoveries of the same thing must merge evidence rather than create
duplicate candidates, so identity is derived from a normalised locator instead of
from the URL a discovery happened to arrive on. For GitHub, `owner/repository` is
the source identity and tree/blob/issues/pull URLs are views of it.
"""

from __future__ import annotations

import re
import uuid
from urllib.parse import urlsplit

from engine.core.errors import DdeError

# Stable namespace for EDR-0019 discovery identity. Changing it re-identifies every
# candidate, so it is a constant, never a configurable.
DISCOVERY_NAMESPACE = uuid.UUID("6f0f9d3a-9a0b-5f7a-9c4e-9a1d0c7b5e21")

_GITHUB_HOSTS = {"github.com", "www.github.com", "codeload.github.com"}
_PACKAGE_HOSTS = {
    "pypi.org": "pypi",
    "registry.npmjs.org": "npm",
    "www.npmjs.com": "npm",
    "crates.io": "cargo",
}
_GITHUB_VIEW_SEGMENTS = {
    "tree",
    "blob",
    "issues",
    "pull",
    "pulls",
    "releases",
    "commit",
    "commits",
    "discussions",
    "actions",
    "wiki",
    "archive",
}
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DdeError("VALIDATION_FAILED", message, retryable=False)


def normalize_locator(locator: str) -> tuple[str, str]:
    """Return `(identity_scheme, normalized_identity_key)` for a raw locator."""
    _require(bool(locator and locator.strip()), "discovery locator must not be empty")
    raw = locator.strip()
    split = urlsplit(raw if "://" in raw else f"https://{raw}")
    _require(
        split.scheme in {"http", "https"},
        f"unsupported discovery locator scheme: {split.scheme}",
    )
    host = split.netloc.lower().split("@")[-1].split(":")[0]
    _require(bool(host), "discovery locator must carry a host")
    segments = [segment for segment in split.path.split("/") if segment]

    if host in _GITHUB_HOSTS:
        _require(
            len(segments) >= 2,
            "a GitHub discovery locator must name owner/repository",
        )
        owner, repository = segments[0], segments[1]
        if repository.endswith(".git"):
            repository = repository[: -len(".git")]
        _require(
            bool(_SAFE_SEGMENT.match(owner) and _SAFE_SEGMENT.match(repository)),
            "GitHub owner/repository carries unsupported characters",
        )
        return "GITHUB_REPOSITORY", f"github:{owner.lower()}/{repository.lower()}"

    ecosystem = _PACKAGE_HOSTS.get(host)
    if ecosystem and segments:
        name = segments[1] if segments[0] in {"project", "package"} else segments[0]
        _require(bool(name), "a package discovery locator must name a package")
        return "PACKAGE_COORDINATE", f"{ecosystem}:{name.lower()}"

    path = "/".join(segments)
    if path:
        return "HTTP_ORIGIN_PATH", f"https://{host}/{path.lower()}"
    return "HTTP_ORIGIN_PATH", f"https://{host}"


def candidate_id_for(project_id: uuid.UUID, normalized_identity_key: str) -> uuid.UUID:
    """Deterministic, project-scoped candidate identity.

    Two discoveries of the same normalised key inside one project resolve to the
    same candidate, which is what makes evidence merge instead of duplicating.
    """
    return uuid.uuid5(DISCOVERY_NAMESPACE, f"{project_id}:{normalized_identity_key}")
