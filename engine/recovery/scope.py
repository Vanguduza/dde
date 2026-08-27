"""Logical mutation scope for Chapter 12.4's recovery rule.

Chapter 12.4: an UNKNOWN effect is never blind-retried; only a verified
absence permits a new mutation attempt. The journal row does not carry
`task_id` (that lives on `CapabilityLease`), so the tightest scope
expressible from `external_effects` columns is:

    (tenant_id, project_id, mission_id, target_system, target_resource, operation)

`mission_id` is the runtime bound Chapter 3.2 already requires on this
table. `target_system` + `target_resource` + `operation` identify one
external mutation (a local-process argv inside one workspace, or a git
`update-ref` of one named ref). A new `WorkerRun` or a new
`idempotency_key` does not change this scope -- that is the gap 94c9d28
left open.

Statuses that refuse a new prepare/mutate until reconciled or verified
absent: `SENT` (crash-abandoned, no observed outcome), `UNKNOWN`,
`RECONCILING`, and `RECONCILED` whose `confirmed_at` is set (verified
presence -- the original attempt was the one true execution).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from engine.contracts.workspace import Workspace

BLOCKING_STATUSES: Final[frozenset[str]] = frozenset({"SENT", "UNKNOWN", "RECONCILING"})

LOCAL_PROCESS_SYSTEM: Final[str] = "local_process"
GIT_SYSTEM: Final[str] = "git"
BROWSER_SYSTEM: Final[str] = "browser"
DONOR_SEARCH_SYSTEM: Final[str] = "donor_search"
GIT_UPDATE_REF_OPERATION: Final[str] = "update-ref"
DONOR_SEARCH_GET_OPERATION: Final[str] = "GET"
GIT_SNAPSHOT_OPERATION: Final[str] = "git_snapshot"
BROWSER_GOTO_OPERATION: Final[str] = "goto"

LOCAL_PROCESS_RESOLVER_METHOD: Final[str] = "workspace_artifact_stat"
GIT_REF_RESOLVER_METHOD: Final[str] = "git_ref_stat"


def local_process_resource(workspace: Workspace) -> str:
    return workspace.workspace_path or str(workspace.workspace_id)


def local_process_operation(command: Sequence[str]) -> str:
    return " ".join(command)


def browser_resource(url: str) -> str:
    return url


def donor_search_resource(uri: str) -> str:
    return uri


def git_ref_resource(branch_or_ref: str) -> str:
    if branch_or_ref.startswith("refs/"):
        return branch_or_ref
    return f"refs/heads/{branch_or_ref}"


def scope_key(
    *,
    mission_id: UUID,
    target_system: str,
    target_resource: str,
    operation: str,
) -> str:
    return f"{mission_id}:{target_system}:{target_resource}:{operation}"
