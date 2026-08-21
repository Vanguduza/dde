"""Production `ExternalEffect` journal (Chapter 12.4) -- the sole writer of
`external_effects` rows in PostgreSQL (Chapter 3.5, 3.8).

**Enforced now.** `prepare()` queries live `external_effects` for the
logical mutation scope (`engine.recovery.scope`) and refuses a NEW
mutation (`EFFECT_CONFLICT`) while any `SENT` / `UNKNOWN` / `RECONCILING`
row, or a `RECONCILED` verified-present row (`confirmed_at` set), exists
for that scope. A new `WorkerRun` / new `idempotency_key` does not bypass
this: `WorkerManagerService.invoke_run` checks the same scope before
creating a run, and `ScriptedWorkerAdapter._journaled_execute` /
`IntegrationQueueService.submit` check again at `prepare()`. Same-key
ledger replay (Chapter 12.5) still returns the stored row without a second
mutation. Timeout of a journaled subprocess is `mark_unknown` AND
`WorkerRun.failure_class=SIDE_EFFECT_UNKNOWN` (Chapter 12.3), not only
`WORKER_COMMAND_TIMEOUT`. Crash-abandoned `SENT` is recovered by
`abandon_sent` (`SENT -> UNKNOWN`). `reconcile_journaled` dispatches a
real resolver for `run_local_process` and git `update-ref` (see
`engine.recovery.resolvers`). `IRREVERSIBLE` reconciliation failure emits
`ExternalEffectIrreversibleEscalated` and raises `EFFECT_IRREVERSIBLE` --
distinct from the generic `EFFECT_UNKNOWN` fail-closed path.

**Journaled production mutations.** `capability.run_local_process` (the
scripted adapter's real subprocess) and `capability.git_operations`
`update-ref` / `create_branch` in `IntegrationQueueService.submit` (the
Stage 1 EXTERNAL_IDEMPOTENT git mutation). `WorkspaceService.snapshot` may
still journal `git_snapshot` as optional extra audit of a git *read*; that
row is not the Chapter 12.4 mutation proof.

**Deferred.** Seeded `IRREVERSIBLE` capabilities remain absent from the
catalog; per-invocation approval is still enforced at `prepare()` when
the class is used (DDE-026). Workspace `git worktree
add`/`remove` happen before a `WorkerRun`/`CapabilityLease` exist
(Chapter 3.9 steps 9 vs 10/11) so they cannot be journaled against
Chapter 12.4's required `worker_run_id`/`capability_lease_id` without a
schema divergence -- that is not silently faked. T2 egress-proxy effect
records (Chapter 12.4 last paragraph) are out of scope. Checkpoints (12.1)
and replay beyond `CommandLedger` reuse (12.5/12.6) are out of scope.

**Journaling scope (flagged interpretation).** Chapter 9.3 marks
`WORKSPACE_LOCAL` "Journal: No". `run_local_process` is still journaled so
the recovery rule has a reachable UNKNOWN path; that is a superset of the
mandatory EXTERNAL_* / IRREVERSIBLE minimum, not a substitute for
journaling the git mutation.

**Reconciliation.** Caller-supplied `resolver` remains the generic
Chapter 12.4 hook. Production call sites should use `reconcile_journaled`.
Verified-present sets `confirmed_at` so the recovery gate can refuse a
duplicate without a second status value the chapter never names.
Undeterminable outcomes leave the row `RECONCILING`. For `IRREVERSIBLE`,
that failure is the distinguishable escalation above; for every other
class it is `EFFECT_UNKNOWN`.

**Idempotency (Chapter 12.5).** `prepare()` is still guarded by
`CommandLedger` on the caller-supplied key. That ledger is not the
recovery rule: a different key for the same logical scope is a new
mutation attempt and is refused while the scope is blocked.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.taxonomy import SIDE_EFFECT_CLASSES
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.external_effect import ExternalEffect
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.governance.service import ApprovalService
from engine.recovery.hashing import effect_request_hash
from engine.recovery.outcomes import ReconciliationOutcome, ReconciliationResult
from engine.recovery.repository import ExternalEffectRepository
from engine.recovery.scope import (
    GIT_REF_RESOLVER_METHOD,
    GIT_SYSTEM,
    LOCAL_PROCESS_RESOLVER_METHOD,
    LOCAL_PROCESS_SYSTEM,
)
from engine.recovery.states import EXTERNAL_EFFECT_TRANSITIONS
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: Chapter 9.3's `IRREVERSIBLE` class -- reconciliation failure Chapter
#: 12.4 names as escalating to a human rather than resolving automatically.
IRREVERSIBLE = "IRREVERSIBLE"

EFFECT_CONFLICT = "EFFECT_CONFLICT"
EFFECT_UNKNOWN = "EFFECT_UNKNOWN"
EFFECT_IRREVERSIBLE = "EFFECT_IRREVERSIBLE"


class ExternalEffectService:
    """Async, PostgreSQL-backed writer for `external_effects` (Chapter
    3.8: "Status only"). Each public method opens and commits its own unit
    of work unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead -- and so that
    `prepare()`/`mark_sent()` are each durably committed BEFORE the real
    external side effect they bracket actually runs, which is the entire
    point of a `PREPARED`/`SENT` row surviving a crash mid-effect."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ExternalEffectRepository | None = None,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        clock: Clock | None = None,
        approvals: ApprovalService | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or ExternalEffectRepository()
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._clock = clock or SystemClock()
        self._approvals = approvals or ApprovalService(engine)

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
            result = await body(owned)
            await owned.commit()
            return result

    async def prepare(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        worker_run_id: UUID,
        capability_lease_id: UUID,
        target_system: str,
        target_resource: str,
        operation: str,
        side_effect_class: str,
        idempotency_key: str,
        evidence_ref: str | None = None,
        approval_scope_hash: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        """Chapter 12.4's initial `PREPARED` row -- inserted BEFORE the
        real side effect runs, so a crash between `prepare()` and the
        actual subprocess/git call leaves durable evidence recovery can
        reconcile. Idempotent on `idempotency_key`: a repeated call with
        the same key never inserts a second row (Chapter 12.5). A NEW key
        for a blocked logical scope raises `EFFECT_CONFLICT` rather than
        preparing a second mutation."""
        if side_effect_class not in SIDE_EFFECT_CLASSES:
            raise DdeError(
                "POLICY_DENIED",
                f"Unknown side_effect_class {side_effect_class!r}",
                details={"side_effect_class": side_effect_class},
            )
        if side_effect_class == IRREVERSIBLE and approval_scope_hash is None:
            raise DdeError(
                "POLICY_DENIED",
                "IRREVERSIBLE effects require per-invocation approval",
                retryable=False,
                details={"side_effect_class": side_effect_class},
            )
        digest = effect_request_hash(
            worker_run_id=worker_run_id,
            capability_lease_id=capability_lease_id,
            target_system=target_system,
            target_resource=target_resource,
            operation=operation,
        )

        async def _op(active: PostgresUnitOfWork) -> ExternalEffect:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                uow=active,
            )
            if not is_new:
                return await self._replay_or_raise(active, record)

            if side_effect_class == IRREVERSIBLE:
                if approval_scope_hash is None:
                    raise DdeError(
                        "POLICY_DENIED",
                        "IRREVERSIBLE effects require per-invocation approval",
                        retryable=False,
                    )
                await self._approvals.require_approved(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scope_hash=approval_scope_hash,
                    approval_type="irreversible_effect",
                    uow=active,
                )

            await self._refuse_if_blocked(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                target_system=target_system,
                target_resource=target_resource,
                operation=operation,
            )

            now = self._clock.now()
            effect = ExternalEffect(
                effect_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                worker_run_id=worker_run_id,
                capability_lease_id=capability_lease_id,
                command_id=record.command_id,
                target_system=target_system,
                target_resource=target_resource,
                operation=operation,
                side_effect_class=side_effect_class,
                idempotency_key=idempotency_key,
                request_hash=digest,
                status="PREPARED",
                external_reference=evidence_ref,
                response_hash=None,
                reconciliation_method=None,
                created_at=now,
                confirmed_at=None,
                updated_at=now,
            )
            await self._repository.insert_effect(active.connection, effect)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ExternalEffectPrepared",
                aggregate_type="external_effect",
                aggregate_id=effect.effect_id,
                mission_id=mission_id,
                task_id=None,
                payload={
                    "target_system": target_system,
                    "target_resource": target_resource,
                    "operation": operation,
                    "side_effect_class": side_effect_class,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=effect.model_dump(mode="json"),
                uow=active,
            )
            return effect

        return await self._run(uow, tenant_id, project_id, _op)

    async def mark_sent(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        """Chapter 12.4's `PREPARED -> SENT`: called right as the real
        subprocess/git command is about to launch. A crash after this
        commits but before the outcome is observed is exactly the
        `SENT -> UNKNOWN` gap Chapter 12.4 describes -- recover with
        `abandon_sent`."""

        async def _op(active: PostgresUnitOfWork) -> ExternalEffect:
            current = await self._require_effect(active, effect_id)
            return await self._transition(
                active, current, "SENT", event_type="ExternalEffectSent", payload={}
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def mark_confirmed(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        external_reference: str | None = None,
        response_hash: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        """Chapter 12.4's `SENT -> CONFIRMED`: a clean, definitely-observed
        success."""

        async def _op(active: PostgresUnitOfWork) -> ExternalEffect:
            current = await self._require_effect(active, effect_id)
            now = self._clock.now()
            fields: dict[str, object] = {
                "response_hash": response_hash,
                "confirmed_at": now,
            }
            if external_reference is not None:
                fields["external_reference"] = external_reference
            return await self._transition(
                active,
                current,
                "CONFIRMED",
                event_type="ExternalEffectConfirmed",
                payload={"external_reference": external_reference},
                extra_fields=fields,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def mark_failed(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        reason: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        """Chapter 12.4's `SENT -> FAILED`: a definitely-observed failure
        -- a non-zero exit from a process that ran to completion, or a
        spawn-level error where nothing ever started. Never used for a
        genuinely ambiguous outcome; see `mark_unknown`."""

        async def _op(active: PostgresUnitOfWork) -> ExternalEffect:
            current = await self._require_effect(active, effect_id)
            return await self._transition(
                active,
                current,
                "FAILED",
                event_type="ExternalEffectFailed",
                payload={"reason": reason},
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def mark_unknown(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        reason: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        """Chapter 12.4's `SENT -> UNKNOWN`: the external system's true
        state after this effect is genuinely undetermined (Chapter 12.3's
        `SIDE_EFFECT_UNKNOWN` failure class) -- never blind-retried; must
        go through `reconcile()`."""

        async def _op(active: PostgresUnitOfWork) -> ExternalEffect:
            current = await self._require_effect(active, effect_id)
            return await self._transition(
                active,
                current,
                "UNKNOWN",
                event_type="ExternalEffectUnknown",
                payload={"reason": reason},
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def abandon_sent(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        reason: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        """Production recovery path for a crash that left `SENT` with no
        observed outcome (Chapter 12.4 diagram: `SENT -> UNKNOWN`).
        Refuses any status other than `SENT` so a caller cannot launder a
        `CONFIRMED`/`FAILED` row into `UNKNOWN`."""

        async def _op(active: PostgresUnitOfWork) -> ExternalEffect:
            current = await self._require_effect(active, effect_id)
            if current.status != "SENT":
                raise DdeError(
                    "VERSION_CONFLICT",
                    f"abandon_sent requires status SENT (got {current.status})",
                    details={
                        "effect_id": str(effect_id),
                        "status": current.status,
                    },
                )
            return await self._transition(
                active,
                current,
                "UNKNOWN",
                event_type="ExternalEffectUnknown",
                payload={"reason": reason, "abandoned_from": "SENT"},
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def reconcile(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        method: str,
        resolver: Callable[[], Awaitable[ReconciliationOutcome]],
        uow: PostgresUnitOfWork | None = None,
    ) -> ReconciliationResult:
        """Chapter 12.4's recovery rule, in full: `UNKNOWN -> RECONCILING`,
        then `resolver()` (the idempotency key / external reference /
        read-after-write / provider-specific check Chapter 12.4 names) is
        the one and only source of truth. See module docstring for why an
        undeterminable outcome always raises rather than resolving, and
        why `verified_absent` -- not a second status value -- is how a
        caller learns whether a retry is permitted."""
        if method.strip() == "":
            raise DdeError("POLICY_DENIED", "reconciliation method must not be empty")

        async def _enter(active: PostgresUnitOfWork) -> ExternalEffect:
            current = await self._require_effect(active, effect_id)
            if current.status == "UNKNOWN":
                return await self._transition(
                    active,
                    current,
                    "RECONCILING",
                    event_type="ExternalEffectReconciling",
                    payload={"method": method},
                    extra_fields={"reconciliation_method": method},
                )
            if current.status == "RECONCILING":
                return current
            # Same fail-closed shape as every other illegal-transition
            # attempt in this codebase (Chapter 19.1's negative test
            # type) -- reconciling a PREPARED/SENT/terminal effect is
            # not a real recovery scenario.
            transition(current.status, "RECONCILING", EXTERNAL_EFFECT_TRANSITIONS)
            raise AssertionError("unreachable")

        # Commit RECONCILING before the provider check so an undeterminable
        # outcome (or a crash mid-resolver) leaves the durable row in
        # RECONCILING rather than rolling back to UNKNOWN -- matching this
        # module's documented recovery rule.
        current = await self._run(uow, tenant_id, project_id, _enter)
        outcome = await resolver()
        if not outcome.verified:
            await self._escalate_undeterminable(
                current,
                method=method,
                detail=outcome.detail,
                uow=uow,
            )

        extra_fields: dict[str, object] = {}
        if outcome.present:
            extra_fields["confirmed_at"] = self._clock.now()
            if current.external_reference is None and outcome.detail:
                extra_fields["external_reference"] = outcome.detail[:512]

        async def _finish(active: PostgresUnitOfWork) -> ReconciliationResult:
            live = await self._require_effect(active, effect_id)
            reconciled = await self._transition(
                active,
                live,
                "RECONCILED",
                event_type="ExternalEffectReconciled",
                payload={"present": outcome.present, "detail": outcome.detail},
                extra_fields=extra_fields or None,
            )
            return ReconciliationResult(
                effect=reconciled, verified_absent=not outcome.present
            )

        return await self._run(uow, tenant_id, project_id, _finish)

    async def reconcile_journaled(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        repo_root: Path | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ReconciliationResult:
        """Production reconcile: pick the real resolver for this row's
        `target_system` rather than requiring a test-supplied callable."""
        from engine.context.repo import repo_root as default_repo_root
        from engine.recovery.resolvers import (
            resolve_git_ref,
            resolve_local_process_artifact,
        )

        effect = await self.get_effect(
            tenant_id=tenant_id, project_id=project_id, effect_id=effect_id, uow=uow
        )
        if effect.target_system == LOCAL_PROCESS_SYSTEM:

            async def local_resolver() -> ReconciliationOutcome:
                return resolve_local_process_artifact(
                    workspace_root=Path(effect.target_resource),
                    expected_artifact=effect.external_reference,
                )

            method = LOCAL_PROCESS_RESOLVER_METHOD
            resolver: Callable[[], Awaitable[ReconciliationOutcome]] = local_resolver
        elif effect.target_system == GIT_SYSTEM:
            root = repo_root if repo_root is not None else default_repo_root()

            async def git_resolver() -> ReconciliationOutcome:
                return resolve_git_ref(repo_root=root, ref_name=effect.target_resource)

            method = GIT_REF_RESOLVER_METHOD
            resolver = git_resolver
        else:
            raise DdeError(
                "POLICY_DENIED",
                "No production resolver for this target_system",
                details={"target_system": effect.target_system},
            )
        return await self.reconcile(
            tenant_id=tenant_id,
            project_id=project_id,
            effect_id=effect_id,
            method=method,
            resolver=resolver,
            uow=uow,
        )

    async def assert_clear_to_mutate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        target_system: str,
        target_resource: str,
        operation: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        """Refuse a new mutation of this logical scope while an
        unreconciled or verified-present effect exists. Called from
        `prepare()` and from `WorkerManagerService.invoke_run`."""

        async def _op(active: PostgresUnitOfWork) -> None:
            await self._refuse_if_blocked(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                target_system=target_system,
                target_resource=target_resource,
                operation=operation,
            )

        await self._run(uow, tenant_id, project_id, _op)

    async def list_unreconciled(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[ExternalEffect]:
        """`SENT` / `UNKNOWN` / `RECONCILING` rows for a mission -- the
        inventory production recovery walks before `abandon_sent` /
        `reconcile_journaled`."""

        async def _op(active: PostgresUnitOfWork) -> list[ExternalEffect]:
            return await self._repository.list_unreconciled_for_mission(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_for_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[ExternalEffect]:
        async def _op(active: PostgresUnitOfWork) -> list[ExternalEffect]:
            return await self._repository.list_for_run(active.connection, worker_run_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_effect(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        async def _op(active: PostgresUnitOfWork) -> ExternalEffect:
            return await self._require_effect(active, effect_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _escalate_undeterminable(
        self,
        current: ExternalEffect,
        *,
        method: str,
        detail: str,
        uow: PostgresUnitOfWork | None,
    ) -> None:
        if current.side_effect_class == IRREVERSIBLE:

            async def _event(active: PostgresUnitOfWork) -> None:
                await self._events.append(
                    tenant_id=current.tenant_id,
                    project_id=current.project_id,
                    event_type="ExternalEffectIrreversibleEscalated",
                    aggregate_type="external_effect",
                    aggregate_id=current.effect_id,
                    mission_id=current.mission_id,
                    task_id=None,
                    payload={
                        "method": method,
                        "detail": detail,
                        "escalation": "human",
                    },
                    uow=active,
                )

            await self._run(uow, current.tenant_id, current.project_id, _event)
            raise DdeError(
                EFFECT_IRREVERSIBLE,
                "IRREVERSIBLE effect could not be reconciled -- "
                "escalating to a human rather than resolving "
                f"(side_effect_class={current.side_effect_class!r}): {detail}",
                retryable=False,
                details={
                    "effect_id": str(current.effect_id),
                    "side_effect_class": current.side_effect_class,
                    "method": method,
                    "escalation": "human",
                },
            )
        raise DdeError(
            EFFECT_UNKNOWN,
            "Reconciliation could not determine the true external "
            "state -- escalating rather than resolving "
            f"(side_effect_class={current.side_effect_class!r}): {detail}",
            retryable=False,
            details={
                "effect_id": str(current.effect_id),
                "side_effect_class": current.side_effect_class,
                "method": method,
            },
        )

    async def _refuse_if_blocked(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        target_system: str,
        target_resource: str,
        operation: str,
    ) -> None:
        blockers = await self._repository.list_blocking_for_scope(
            active.connection,
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            target_system=target_system,
            target_resource=target_resource,
            operation=operation,
        )
        if not blockers:
            return
        lead = blockers[0]
        raise DdeError(
            EFFECT_CONFLICT,
            "Refusing a new mutation while an unreconciled or "
            "verified-present external effect exists for this scope "
            f"(status={lead.status}, effect_id={lead.effect_id})",
            retryable=False,
            details={
                "effect_id": str(lead.effect_id),
                "status": lead.status,
                "target_system": target_system,
                "target_resource": target_resource,
                "operation": operation,
                "blocking_effect_ids": [str(row.effect_id) for row in blockers],
            },
        )

    async def _transition(
        self,
        active: PostgresUnitOfWork,
        current: ExternalEffect,
        target_status: str,
        *,
        event_type: str,
        payload: dict[str, object],
        extra_fields: dict[str, object] | None = None,
    ) -> ExternalEffect:
        next_status = transition(
            current.status, target_status, EXTERNAL_EFFECT_TRANSITIONS
        )
        now = self._clock.now()
        fields: dict[str, object] = {
            "status": next_status,
            "updated_at": now,
            **(extra_fields or {}),
        }
        rowcount = await self._repository.update_fields(
            active.connection, current.effect_id, fields=fields
        )
        if rowcount != 1:
            raise DdeError(
                "VERSION_CONFLICT",
                "Unknown external effect",
                details={"effect_id": str(current.effect_id)},
            )
        updated = await self._require_effect(active, current.effect_id)
        await self._events.append(
            tenant_id=updated.tenant_id,
            project_id=updated.project_id,
            event_type=event_type,
            aggregate_type="external_effect",
            aggregate_id=updated.effect_id,
            mission_id=updated.mission_id,
            task_id=None,
            payload=payload,
            uow=active,
        )
        return updated

    async def _replay_or_raise(
        self, active: PostgresUnitOfWork, record: CommandIdempotency
    ) -> ExternalEffect:
        # CommandLedger stores the PREPARED snapshot (prepare() is the
        # guarded mutation). Status after SENT/CONFIRMED/FAILED/UNKNOWN
        # lives only on the live row -- a replay must return that, not
        # the stale PREPARED copy, or snapshot()/start() would treat an
        # already-terminal effect as freshly PREPARED and attempt an
        # illegal second transition (Chapter 12.5: never a second mutation).
        if record.status == "completed" and record.result is not None:
            stored = ExternalEffect.model_validate(record.result)
            return await self._require_effect(active, stored.effect_id)
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )

    async def _require_effect(
        self, active: PostgresUnitOfWork, effect_id: UUID
    ) -> ExternalEffect:
        record = await self._repository.get_by_id(active.connection, effect_id)
        if record is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown external effect",
                details={"effect_id": str(effect_id)},
            )
        return record
