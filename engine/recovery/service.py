"""Production `ExternalEffect` journal (Chapter 12.4) -- the sole writer of
`external_effects` rows in PostgreSQL (Chapter 3.5, 3.8), wired around DDE's
two already-real, lease-gated side effects: `engine.workers.
scripted_adapter.ScriptedWorkerAdapter.start`'s local-process subprocess
spawn (`capability.run_local_process`) and `engine.workspaces.service.
WorkspaceService.snapshot`'s real git commands (`capability.git_operations`)
-- see both modules' own docstrings for the exact call-site wiring. Unlike
DDE-019's Credential Broker, which had no real caller to wire (no capability
needed a credential), this journal has two genuine, already-shipped
side-effecting call sites and is wired into both, not merely built and left
unused.

**Journaling scope (flagged interpretation).** Chapter 9.3's taxonomy table
marks `WORKSPACE_LOCAL` (`capability.run_local_process`'s own declared
class, `engine.capabilities.seed.SEED_CAPABILITIES`) "Journal: No" --
mandatory journaling is reserved for `EXTERNAL_IDEMPOTENT`,
`EXTERNAL_NON_IDEMPOTENT` and `IRREVERSIBLE`. This mission's own brief
explicitly directs wiring the journal around BOTH real call sites
regardless -- a superset of the mandatory minimum, not a violation of it:
every `EXTERNAL_IDEMPOTENT`/`EXTERNAL_NON_IDEMPOTENT`/`IRREVERSIBLE` effect
Chapter 9.3 requires is still journaled, and `capability.run_local_process`
additionally gets a real, reconciliable audit trail even though the
taxonomy does not strictly require one for a workspace-local mutation. Nothing
in Chapter 9.3 forbids journaling more than the mandatory subset.

**A genuine, reachable `UNKNOWN` path -- not a synthesized one in
production code.** `engine.workspaces.service.WorkspaceService.execute`
already distinguishes three real, observably different subprocess outcomes:
a clean exit (`exit_code == 0`), a definite non-zero exit or a spawn-level
`OSError` (`timed_out is False` -- the process either ran to completion and
failed, in a genuinely-known way, or never started at all, which is also a
genuinely-known "nothing happened"), and a real `subprocess.TimeoutExpired`
(`timed_out is True` -- Python killed the process after it was already
spawned, and the exit code the backend fabricates for this case, `-1`, is
not a real observed exit status). Only the last of these is genuine
ambiguity about whether the external mutation happened before the kill
signal landed -- so `ScriptedWorkerAdapter.start` maps `timed_out=True` to
`mark_unknown`, a non-zero-but-not-timed-out exit to `mark_failed`, and
`exit_code == 0` to `mark_confirmed`. This is a real path through
production code, reachable with a real, short `timeout_seconds` and a
real command that outlives it (`tests/unit/test_external_effects_postgres.
py`'s `test_state_transition_unknown_reconciling_reconciled_via_real_timeout`)
-- not a state machine exercised only through a mock.

**Reconciliation (`reconcile`).** Chapter 12.4's recovery rule -- "the
capability adapter reconciles using the idempotency key, the external
reference, a read-after-write query, or a provider-specific method" -- is
generic across providers, so this service accepts the actual check as a
caller-supplied async `resolver` rather than hard-coding one provider's
query. A `ReconciliationOutcome` distinguishes three real answers:
genuinely verified present, genuinely verified absent, or genuinely
undeterminable (`verified=False`). Only the first two ever move the row to
`RECONCILED` -- Chapter 12.4 names exactly one resolved status for both a
present and an absent finding, so which one occurred is carried on the
return value (`ReconciliationResult.verified_absent`), the caller-facing
fact that governs whether a NEW mutation attempt (Chapter 12.4: "only a
verified absence permits a new mutation attempt") is safe, not a second
`ExternalEffect.status` value the chapter never names. An undeterminable
outcome always raises `DdeError("EFFECT_UNKNOWN", ...)` (Chapter 15.5's
SIDE_EFFECT family) rather than resolving. Chapter 12.3's own
`SIDE_EFFECT_UNKNOWN` failure class already states this as the general
escalation condition ("Reconciliation impossible -> human"), and
Chapter 12.4 restates
it specifically for `IRREVERSIBLE` effects; this service does not treat
`IRREVERSIBLE` as a special case needing different code, only as the class
this mission's own negative test exercises. The row itself is left
`RECONCILING` (not reset to `UNKNOWN`) so a later, better-informed
`reconcile()` call can retry without losing the fact that reconciliation is
already in progress.

**Idempotency (Chapter 12.5).** `prepare()` is guarded by `engine.events.
idempotency.CommandLedger` on a caller-supplied `idempotency_key`, exactly
as `engine.capabilities.broker.service.CredentialBrokerService.issue` and
`engine.capabilities.lease_service.CapabilityLeaseService.request` already
do -- not a second idempotency mechanism. `command_id` on the persisted row
IS that ledger record's own identity.

**Standard columns.** `tenant_id`/`project_id`/`updated_at` are added per
this mission's own brief (not named in Chapter 12.4's literal field list,
but every Stage 1/2 durable row carries them, per `engine.capabilities.
broker.tables.credential_handles`'s identical addition). `mission_id` is
added because Chapter 3.2 mandates it for "every runtime/execution table"
-- an `ExternalEffect` is exactly that, bound to a `WorkerRun`. No
`lock_version`: Chapter 3.5 does not name `external_effects` among the
tables carrying one, and neither `capability_leases` nor `credential_
handles` (the two closest sibling "status only" lifecycle tables) use one
either -- a plain rowcount check on the transitioning `UPDATE` is this
codebase's established pattern for that gap.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
from engine.recovery.hashing import effect_request_hash
from engine.recovery.repository import ExternalEffectRepository
from engine.recovery.states import EXTERNAL_EFFECT_TRANSITIONS
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: Chapter 9.3's `IRREVERSIBLE` class -- the one whose reconciliation
#: failure Chapter 12.4 explicitly names as escalating rather than
#: resolving. See module docstring: every class escalates identically;
#: this constant exists only to name the class in the one place a
#: docstring/test needs to refer to it, not to branch on it specially.
IRREVERSIBLE = "IRREVERSIBLE"


@dataclass(frozen=True)
class ReconciliationOutcome:
    """A provider-specific `resolver`'s real answer to "did the external
    mutation actually happen?". `verified=False` means the resolver could
    not determine either answer with confidence -- the only condition
    under which `reconcile()` raises rather than resolving. `present` is
    meaningful only when `verified=True`."""

    verified: bool
    present: bool
    detail: str


@dataclass(frozen=True)
class ReconciliationResult:
    """`reconcile()`'s return value. `verified_absent` is the Chapter
    12.4-governing fact a caller needs: `True` only when reconciliation
    positively confirmed the mutation never happened, the one condition
    under which a NEW mutation attempt is permitted."""

    effect: ExternalEffect
    verified_absent: bool


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
    ) -> None:
        self._engine = engine
        self._repository = repository or ExternalEffectRepository()
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._clock = clock or SystemClock()

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
        uow: PostgresUnitOfWork | None = None,
    ) -> ExternalEffect:
        """Chapter 12.4's initial `PREPARED` row -- inserted BEFORE the
        real side effect runs, so a crash between `prepare()` and the
        actual subprocess/git call leaves durable evidence recovery can
        reconcile. Idempotent on `idempotency_key`: a repeated call with
        the same key never inserts a second row (Chapter 12.5)."""
        if side_effect_class not in SIDE_EFFECT_CLASSES:
            raise DdeError(
                "POLICY_DENIED",
                f"Unknown side_effect_class {side_effect_class!r}",
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
                external_reference=None,
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
        `SENT -> UNKNOWN` gap Chapter 12.4 describes."""

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
            return await self._transition(
                active,
                current,
                "CONFIRMED",
                event_type="ExternalEffectConfirmed",
                payload={"external_reference": external_reference},
                extra_fields={
                    "external_reference": external_reference,
                    "response_hash": response_hash,
                    "confirmed_at": now,
                },
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
            raise DdeError(
                "EFFECT_UNKNOWN",
                "Reconciliation could not determine the true external "
                "state -- escalating rather than resolving "
                f"(side_effect_class={current.side_effect_class!r}): "
                f"{outcome.detail}",
                retryable=False,
                details={
                    "effect_id": str(effect_id),
                    "side_effect_class": current.side_effect_class,
                    "method": method,
                },
            )

        async def _finish(active: PostgresUnitOfWork) -> ReconciliationResult:
            live = await self._require_effect(active, effect_id)
            reconciled = await self._transition(
                active,
                live,
                "RECONCILED",
                event_type="ExternalEffectReconciled",
                payload={"present": outcome.present, "detail": outcome.detail},
            )
            return ReconciliationResult(
                effect=reconciled, verified_absent=not outcome.present
            )

        return await self._run(uow, tenant_id, project_id, _finish)

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
