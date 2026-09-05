"""Production Workspace lifecycle — the sole writer of `workspaces` rows in
PostgreSQL (Chapter 3.5, 3.8, 7.5).

`WorkspaceService.create()` performs Chapter 7.5's `create(base_revision,
policy)` as a real `git worktree add` against this repository's own working
tree (`engine.context.repo.repo_root()` — Stage 1's only real corpus, per
this mission's scoping: DDE does not manage a separate product repository
yet). `execute()`, `capture_revision()`, `read()`/`write()` and `cleanup()`
implement the rest of Chapter 7.5's operation surface; `snapshot()` is a
pure read with no persisted side effect.

Deliberately out of this mission's scope: binding to the Ch.10.2 mission
integration branch (Ch.10/DDE-013 does not exist yet — worktrees branch
directly from a caller-supplied revision instead) and any isolation beyond
a workspace-root path jail (Chapter 7.2's other T2 guarantees need
container/microVM isolation the `local_process` backend does not have).

**DDE-017 addition.** `snapshot()` is the one call site in this module that
performs a real `capability.git_operations` *read* (`engine.
workspaces.git.rev_parse_head`/`status_porcelain`) on behalf of an in-flight
`WorkerRun` (`engine.workers.scripted_adapter.ScriptedWorkerAdapter.start`
calls it after writing a worker's files) — so it is this module's
Chapter 7.2 T1 enforcement point: a `require_active(...)` guard against a
real, granted `CapabilityLease` before the real git subprocess calls run.
`create()`/`cleanup()`/`capture_revision()` also invoke `engine.
workspaces.git`, but on DDE's own behalf as workspace *lifecycle*
management (Chapter 3.9 places workspace allocation at step 9, before any
`CapabilityLease` can exist at step 11) rather than as an operation a
worker's run requested — they are deliberately left ungated; gating DDE's
own infrastructure bookkeeping would either contradict Chapter 3.9's
creation order or require inventing a lease phase the blueprint does not
describe. This is a flagged, narrower scope than "every git operation";
see the mission summary.

**DDE-020 correction.** `snapshot()` may still journal those git *reads*
as optional extra audit (`operation=git_snapshot`). That is NOT the
Chapter 12.4 EXTERNAL_IDEMPOTENT mutation proof — a `rev-parse` /
`status --porcelain` pair mutates nothing. The production git mutation
that is journaled is `IntegrationQueueService.submit`'s `update-ref` of
the task branch. Workspace `worktree add`/`remove` are not journaled:
they run before a `WorkerRun`/`CapabilityLease` exist.

**Future-state scrubbing (comparable-systems adoption #6).** `create()`
scrubs the freshly-provisioned worktree's *future state* before it ever
becomes READY: reflogs expired, every branch/tag/remote-tracking ref that
does not point at the checked-out commit deleted, and the object store
pruned (`gc --prune=now`). A generator worker must never be able to read
its own solution history out of a workspace a verifier will later share,
and a verifier must never see branches/tags naming candidate solutions.
Like `worktree add`, this runs on DDE's own behalf during Chapter 3.9's
step-9 provisioning — before any `WorkerRun`/`CapabilityLease` can exist —
so it is deliberately left ungated for the same reason the module
docstring already records.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import side_effect_class_for
from engine.context.repo import repo_root
from engine.contracts.workspace import Workspace
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.environments.backends.base import CommandResult, EnvironmentBackend
from engine.environments.backends.local_process import LocalProcessBackend
from engine.events.service import EventService
from engine.recovery.hashing import effect_response_hash
from engine.recovery.service import ExternalEffectService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.workspaces import git
from engine.workspaces.paths import resolve_within_workspace
from engine.workspaces.repository import WorkspaceRepository
from engine.workspaces.states import WORKSPACE_TRANSITIONS

T = TypeVar("T")

DEFAULT_EXECUTE_TIMEOUT_SECONDS = 60.0

#: DDE-016's real, seeded `capability_id` this module's `snapshot()` performs
#: -- see the module docstring's DDE-017 addition.
CAPABILITY_GIT_OPERATIONS = "capability.git_operations"


class WorkspaceService:
    """Async, PostgreSQL-backed writer for `workspaces` (Chapter 3.8). Each
    public method opens and commits its own unit of work unless one is
    supplied, so a caller composing a cross-module transaction (Chapter
    3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: WorkspaceRepository | None = None,
        clock: Clock | None = None,
        backend: EnvironmentBackend | None = None,
        root: Path | None = None,
        leases: CapabilityLeaseService | None = None,
        effects: ExternalEffectService | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or WorkspaceRepository()
        self._clock = clock or SystemClock()
        self._backend: EnvironmentBackend = backend or LocalProcessBackend()
        self._root = root or repo_root()
        self._leases = leases or CapabilityLeaseService(engine, clock=self._clock)
        self._effects = effects or ExternalEffectService(engine, clock=self._clock)

    @property
    def effects(self) -> ExternalEffectService:
        """Shared with `engine.workers.scripted_adapter.ScriptedWorkerAdapter`
        so both journal through the same `ExternalEffectService` instance.
        Snapshot journaling is optional extra audit of a git read, not the
        Chapter 12.4 mutation proof."""
        return self._effects

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            try:
                result = await body(owned)
            except Exception:
                # A genuine provisioning failure already persisted its own
                # real FAILED row and event inside this same transaction
                # (Chapter 19.1's "captured as a real, persisted row" negative
                # test requirement) — commit that durable evidence instead of
                # discarding it, then let the typed error propagate.
                await owned.commit()
                raise
            await owned.commit()
            return result

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        task_id: UUID | None,
        execution_environment_id: UUID | None,
        base_revision: str | None,
        policy: dict[str, object],
        uow: PostgresUnitOfWork | None = None,
    ) -> Workspace:
        """Chapter 7.5's `create(base_revision, policy)`: insert a real
        `PROVISIONING` row, resolve `base_revision` (defaulting to this
        repository's current `HEAD`) against a real git ref, then create a
        real detached worktree there. A bad ref or a `git worktree add`
        failure is caught, persisted as a real `FAILED` row, and re-raised
        as a typed `ENVIRONMENT_FAILED` — never an unhandled exception."""

        async def _op(active: PostgresUnitOfWork) -> Workspace:
            workspace_id = uuid7()
            now = self._clock.now()
            provisioning = Workspace(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
                execution_environment_id=execution_environment_id,
                base_revision=base_revision,
                current_revision=None,
                workspace_path=None,
                policy=policy,
                status="PROVISIONING",
                lock_version=1,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_workspace(active.connection, provisioning)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="WorkspaceProvisioning",
                aggregate_type="workspace",
                aggregate_id=workspace_id,
                mission_id=mission_id,
                task_id=task_id,
                payload={"base_revision": base_revision},
                uow=active,
            )

            requested_revision = base_revision or "HEAD"
            try:
                resolved_revision = git.rev_parse(self._root, requested_revision)
            except git.GitCommandError as exc:
                await self._fail(active, workspace_id, reason=str(exc))
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    "Workspace base_revision does not resolve to a real commit",
                    details={
                        "workspace_id": str(workspace_id),
                        "base_revision": requested_revision,
                        "reason": exc.stderr.strip(),
                    },
                ) from exc

            target_dir = (
                Path(tempfile.gettempdir())
                / "dde-workspaces"
                / f"ws-{workspace_id.hex}"
            )
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            scrub_policy = bool(policy.get("scrub_future_state", False))
            try:
                git.worktree_add(self._root, target_dir, resolved_revision)
                scrubbed_refs: list[str] = []
                if scrub_policy:
                    # Opt-in (workspace policy `scrub_future_state: true`)
                    # because the scrub mutates the SHARED object store
                    # backing this worktree: reflog expiry and gc --prune
                    # would destroy the host repo's own recovery history
                    # and collide with concurrent git operations. Safe
                    # only against isolated clone-based stores.
                    scrubbed_refs = git.scrub_future_state(
                        target_dir, keep_revision=resolved_revision
                    )
            except git.GitCommandError as exc:
                shutil.rmtree(target_dir, ignore_errors=True)
                await self._fail(active, workspace_id, reason=str(exc))
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    "git worktree add failed",
                    details={
                        "workspace_id": str(workspace_id),
                        "reason": exc.stderr.strip(),
                    },
                ) from exc

            current_revision = git.rev_parse_head(target_dir)
            ready_at = self._clock.now()
            rowcount = await self._repository.update_workspace(
                active.connection,
                workspace_id,
                expected_lock_version=1,
                updated_at=ready_at,
                fields={
                    "base_revision": resolved_revision,
                    "current_revision": current_revision,
                    "workspace_path": str(target_dir),
                    "status": "READY",
                },
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Workspace lock_version mismatch during provisioning",
                    retryable=True,
                    details={"workspace_id": str(workspace_id)},
                )
            updated = await self._require_workspace(active, workspace_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="WorkspaceReady",
                aggregate_type="workspace",
                aggregate_id=workspace_id,
                mission_id=mission_id,
                task_id=task_id,
                payload={
                    "workspace_path": updated.workspace_path,
                    "revision": current_revision,
                    "scrubbed_refs": scrubbed_refs,
                },
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def _fail(
        self, active: PostgresUnitOfWork, workspace_id: UUID, *, reason: str
    ) -> None:
        current = await self._require_workspace(active, workspace_id)
        failed_at = self._clock.now()
        await self._repository.update_workspace(
            active.connection,
            workspace_id,
            expected_lock_version=current.lock_version,
            updated_at=failed_at,
            fields={"status": "FAILED"},
        )
        await self._events.append(
            tenant_id=current.tenant_id,
            project_id=current.project_id,
            event_type="WorkspaceFailed",
            aggregate_type="workspace",
            aggregate_id=workspace_id,
            mission_id=current.mission_id,
            task_id=current.task_id,
            payload={"reason": reason},
            uow=active,
        )

    async def _apply_transition(
        self, active: PostgresUnitOfWork, current: Workspace, target_status: str
    ) -> Workspace:
        next_status = transition(current.status, target_status, WORKSPACE_TRANSITIONS)
        now = self._clock.now()
        rowcount = await self._repository.update_workspace(
            active.connection,
            current.workspace_id,
            expected_lock_version=current.lock_version,
            updated_at=now,
            fields={"status": next_status},
        )
        if rowcount != 1:
            raise DdeError(
                "VERSION_CONFLICT",
                "Workspace lock_version mismatch",
                retryable=True,
                details={"workspace_id": str(current.workspace_id)},
            )
        updated = await self._require_workspace(active, current.workspace_id)
        await self._events.append(
            tenant_id=current.tenant_id,
            project_id=current.project_id,
            event_type="WorkspaceTransitioned",
            aggregate_type="workspace",
            aggregate_id=current.workspace_id,
            mission_id=current.mission_id,
            task_id=current.task_id,
            payload={"from": current.status, "to": updated.status},
            uow=active,
        )
        return updated

    async def transition(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        workspace_id: UUID,
        target_status: str,
        lock_version: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> Workspace:
        async def _op(active: PostgresUnitOfWork) -> Workspace:
            current = await self._require_workspace(active, workspace_id)
            if current.lock_version != lock_version:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Workspace lock_version mismatch",
                    retryable=True,
                    details={
                        "expected": lock_version,
                        "actual": current.lock_version,
                    },
                )
            return await self._apply_transition(active, current, target_status)

        return await self._run(uow, tenant_id, project_id, _op)

    async def execute(
        self,
        *,
        workspace: Workspace,
        command: list[str],
        timeout_seconds: float = DEFAULT_EXECUTE_TIMEOUT_SECONDS,
        uow: PostgresUnitOfWork | None = None,
    ) -> CommandResult:
        """Chapter 7.5's `execute(command)`: run a real subprocess rooted at
        the real worktree directory, capture its real stdout/stderr/exit
        code, and persist that capture as a `WorkspaceCommandExecuted` event
        — durable evidence a fresh session can read back (Chapter 19.1's
        recovery test type) without adding a dedicated results table for a
        capability Chapter 7.5 does not define a durable object for. A
        non-zero exit or a timeout is captured in `CommandResult`, never
        raised."""

        async def _op(active: PostgresUnitOfWork) -> CommandResult:
            current = await self._require_workspace(active, workspace.workspace_id)
            if current.status != "READY" or current.workspace_path is None:
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    f"Workspace is {current.status}, not ready to execute",
                    details={"workspace_id": str(current.workspace_id)},
                )
            in_use = await self._apply_transition(active, current, "IN_USE")
            result = self._backend.run(
                cwd=Path(current.workspace_path),
                command=command,
                timeout_seconds=timeout_seconds,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="WorkspaceCommandExecuted",
                aggregate_type="workspace",
                aggregate_id=current.workspace_id,
                mission_id=current.mission_id,
                task_id=current.task_id,
                payload={
                    "command": list(result.command),
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "duration_ms": result.duration_ms,
                    "timed_out": result.timed_out,
                },
                uow=active,
            )
            await self._apply_transition(active, in_use, "READY")
            return result

        return await self._run(uow, workspace.tenant_id, workspace.project_id, _op)

    async def capture_revision(
        self,
        *,
        workspace: Workspace,
        uow: PostgresUnitOfWork | None = None,
    ) -> Workspace:
        """Chapter 7.5's `capture_revision()`: read the worktree's real
        current `HEAD` and persist it as `current_revision`."""

        async def _op(active: PostgresUnitOfWork) -> Workspace:
            current = await self._require_workspace(active, workspace.workspace_id)
            if current.workspace_path is None:
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    "Workspace has no path to capture a revision from",
                    details={"workspace_id": str(current.workspace_id)},
                )
            revision = git.rev_parse_head(Path(current.workspace_path))
            now = self._clock.now()
            rowcount = await self._repository.update_workspace(
                active.connection,
                current.workspace_id,
                expected_lock_version=current.lock_version,
                updated_at=now,
                fields={"current_revision": revision},
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Workspace lock_version mismatch",
                    retryable=True,
                    details={"workspace_id": str(current.workspace_id)},
                )
            updated = await self._require_workspace(active, current.workspace_id)
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="WorkspaceRevisionCaptured",
                aggregate_type="workspace",
                aggregate_id=current.workspace_id,
                mission_id=current.mission_id,
                task_id=current.task_id,
                payload={"revision": revision},
                uow=active,
            )
            return updated

        return await self._run(uow, workspace.tenant_id, workspace.project_id, _op)

    def read(self, workspace: Workspace, relative_path: str) -> bytes:
        """Chapter 7.5's `read(path)`, jailed to the workspace root
        (`engine.workspaces.paths.resolve_within_workspace`)."""
        root = self._require_root(workspace)
        return resolve_within_workspace(root, relative_path).read_bytes()

    def write(self, workspace: Workspace, relative_path: str, content: bytes) -> None:
        """Chapter 7.5's `write(path)`, jailed to the workspace root."""
        root = self._require_root(workspace)
        target = resolve_within_workspace(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    async def snapshot(
        self,
        workspace: Workspace,
        *,
        worker_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> dict[str, object]:
        """Chapter 7.5's `snapshot()`: a real, unpersisted read of the
        worktree's current revision and working-tree status.

        DDE-017: gated behind a real, granted `capability.git_operations`
        lease bound to `worker_run_id` (Chapter 7.2's T1 enforcement point
        for this module — see the module docstring). `require_active` fails
        closed before either real git subprocess call runs.

        DDE-020: optional extra journal of these git *reads*, not the
        Chapter 12.4 EXTERNAL_IDEMPOTENT mutation proof. Both real git
        calls here are read commands (`rev-parse`, `status --porcelain`).
        The production git mutation that is journaled is
        `IntegrationQueueService.submit`'s `update-ref`. `mark_confirmed`
        records the observed revision as `external_reference`."""
        root = self._require_root(workspace)
        lease = await self._leases.require_active(
            tenant_id=workspace.tenant_id,
            project_id=workspace.project_id,
            worker_run_id=worker_run_id,
            capability_id=CAPABILITY_GIT_OPERATIONS,
            uow=uow,
        )
        effect = await self._effects.prepare(
            tenant_id=workspace.tenant_id,
            project_id=workspace.project_id,
            mission_id=lease.mission_id,
            worker_run_id=worker_run_id,
            capability_lease_id=lease.lease_id,
            target_system="git",
            target_resource=str(root),
            operation="git_snapshot",
            side_effect_class=side_effect_class_for(CAPABILITY_GIT_OPERATIONS),
            idempotency_key=f"{worker_run_id}:effect:{CAPABILITY_GIT_OPERATIONS}",
            uow=uow,
        )
        if effect.status != "PREPARED":
            # Chapter 12.5 idempotent replay: this exact idempotency key was
            # already carried through the journal by an earlier call. Both
            # real git commands here are read-only (`rev-parse`, `status
            # --porcelain`) -- safe to simply re-issue directly, without a
            # second `mark_sent`/`mark_confirmed` pair against an
            # already-terminal row (which `engine.core.state_machine.
            # transition` would correctly refuse as an illegal transition).
            return {
                "revision": git.rev_parse_head(root),
                "status_porcelain": git.status_porcelain(root),
            }
        await self._effects.mark_sent(
            tenant_id=workspace.tenant_id,
            project_id=workspace.project_id,
            effect_id=effect.effect_id,
            uow=uow,
        )
        try:
            revision = git.rev_parse_head(root)
            status_porcelain = git.status_porcelain(root)
        except git.GitCommandError as exc:
            await self._effects.mark_failed(
                tenant_id=workspace.tenant_id,
                project_id=workspace.project_id,
                effect_id=effect.effect_id,
                reason=str(exc),
                uow=uow,
            )
            raise
        snapshot: dict[str, object] = {
            "revision": revision,
            "status_porcelain": status_porcelain,
        }
        await self._effects.mark_confirmed(
            tenant_id=workspace.tenant_id,
            project_id=workspace.project_id,
            effect_id=effect.effect_id,
            external_reference=revision,
            response_hash=effect_response_hash(snapshot),
            uow=uow,
        )
        return snapshot

    async def cleanup(
        self,
        *,
        workspace: Workspace,
        uow: PostgresUnitOfWork | None = None,
    ) -> Workspace:
        """Chapter 7.5's `cleanup()`, and its rule "Workspace creation,
        cleanup and recovery are performed by DDE, never by the worker":
        removes the real git worktree registration and the real directory,
        then moves the row to `CLEANED_UP`. Idempotent — cleaning up an
        already-`CLEANED_UP` workspace is a no-op, not an error, since
        recovery (Chapter 12) may retry a teardown that partially
        completed."""

        async def _op(active: PostgresUnitOfWork) -> Workspace:
            current = await self._require_workspace(active, workspace.workspace_id)
            if current.status == "CLEANED_UP":
                return current
            if current.workspace_path is not None:
                path = Path(current.workspace_path)
                try:
                    git.worktree_remove(self._root, path)
                except git.GitCommandError:
                    pass  # already removed/never registered; still remove the directory
                try:
                    git.worktree_prune(self._root)
                except git.GitCommandError:
                    pass
                shutil.rmtree(path, ignore_errors=True)
            updated = await self._apply_transition(active, current, "CLEANED_UP")
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="WorkspaceCleanedUp",
                aggregate_type="workspace",
                aggregate_id=current.workspace_id,
                mission_id=current.mission_id,
                task_id=current.task_id,
                payload={"workspace_path": current.workspace_path},
                uow=active,
            )
            return updated

        return await self._run(uow, workspace.tenant_id, workspace.project_id, _op)

    async def list_project_workspaces(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> tuple[Workspace, ...]:
        """Return real project workspaces in repository order.

        This is intentionally generic. Frontend Studio decides which READY
        rows are admissible as preview sources; the workspace owner does not
        encode Frontend-specific policy.
        """

        async def _op(active: PostgresUnitOfWork) -> tuple[Workspace, ...]:
            return await self._repository.list_project_workspaces(
                active.connection, project_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_workspace(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        workspace_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Workspace:
        async def _op(active: PostgresUnitOfWork) -> Workspace:
            return await self._require_workspace(active, workspace_id)

        return await self._run(uow, tenant_id, project_id, _op)

    def _require_root(self, workspace: Workspace) -> Path:
        if workspace.workspace_path is None:
            raise DdeError(
                "ENVIRONMENT_FAILED",
                "Workspace has no filesystem path",
                details={"workspace_id": str(workspace.workspace_id)},
            )
        return Path(workspace.workspace_path)

    async def _require_workspace(
        self, active: PostgresUnitOfWork, workspace_id: UUID
    ) -> Workspace:
        record = await self._repository.get_workspace(active.connection, workspace_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown workspace")
        return record
