"""Chapter 11.5 domain invariant engine — the production mutation site.

Owner of `domain_invariants` and `invariant_evaluations` rows (Chapter
3.6/3.8: the verification domain's datastore-check arm). Three public
mutations, each the single call site for its rule:

- `define()` — registers a named, versioned, content-hashed invariant.
  Idempotent on `definition_version` (Chapter 3.10: immutable definition,
  a material change is a NEW version, never an overwrite).
- `retire()` — the one lifecycle mutation, guarded by
  `engine.invariants.states.DEFINITION_TRANSITIONS` at THIS call site;
  illegal transitions are refused with a typed Chapter 15.5 error and the
  row is left untouched.
- `evaluate()` — evaluates a definition's compiled deterministic predicate
  against the REAL rows of a REAL ProductEnvironment datastore and records
  ONE append-only `InvariantEvaluation`. Chapter 11.5's rules wired here:
  * the environment must be READY/IN_USE (an invariant runs against a
    provisioned, seeded datastore — never against a half-built row);
  * the declared `product_env_class` must match the environment's class;
  * every violation carries concrete evidence text, never fabricated from
    absence of data;
  * a FAILED financial-state evaluation records the human-visibility
    marker on the row itself — Chapter 11.5: an invariant failure over
    financial state is never auto-repaired without a repair task; the row
    keeps the named repair-task slot for that workflow to fill.

Idempotency (Chapter 12.5): `evaluate()` is guarded by the existing
CommandLedger on the caller-supplied idempotency key; a repeated
invocation with the same key returns the first call's stored, completed
evaluation instead of re-executing — re-running an invariant evaluation
with the same inputs yields the same recorded outcome. The predicate layer
(`engine.invariants.predicates`) is pure over its rows, so the replayed
outcome equals what a genuine re-run would have produced.

Evaluation reads the PRODUCT datastore through its own engine built from
the caller-supplied `datastore_url` (the ProductEnvironment's own
datastore), not through DDE's control-plane connection pool.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.domain_invariant import DomainInvariant, PredicateSpec
from engine.contracts.invariant_evaluation import InvariantEvaluation, Violation
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.invariants.hashing import definition_version_hash
from engine.invariants.predicates import compile_predicate, judge_rows
from engine.invariants.repository import InvariantRepository
from engine.invariants.states import assert_transition
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

#: Environment states against which evaluation is meaningful: the seed and
#: migration halves of Chapter 11.6 must have landed before rows can be
#: trusted to speak for the product.
EVALUABLE_ENV_STATES = frozenset({"READY", "IN_USE"})

T = TypeVar("T")

#: Violation `kind` per compiled predicate kind — recorded evidence, never
#: a free-form string (Chapter 11.5: violations carry concrete, typed
#: evidence).
VIOLATION_KINDS = {
    "unique_columns": "duplicate_group",
    "inclusion_column": "excluded_value",
    "tuple_condition": "condition_violated",
}


class DomainInvariantService:
    """Async, PostgreSQL-backed writer for the two Chapter 11.5 tables.
    Each public method opens and commits its own unit of work unless one
    is supplied, matching every sibling service in this codebase."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: InvariantRepository | None = None,
        events: EventService | None = None,
        clock: Clock | None = None,
        commands: CommandLedger | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or InvariantRepository()
        self._events = events or EventService(engine)
        self._clock = clock or SystemClock()
        self._commands = commands or CommandLedger(engine)

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

    # --- define -------------------------------------------------------------

    async def define(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        name: str,
        description: str,
        predicate: dict[str, object],
        financial_state: bool,
        required_fixture_class: str,
        product_env_class: str,
        created_by: str,
        mission_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> DomainInvariant:
        """Register (or idempotently return) one named invariant version."""
        spec = PredicateSpec.model_validate(predicate)
        if not name:
            raise DdeError(
                "POLICY_DENIED",
                "An invariant declares a stable name it is governed by",
                details={"name": name},
            )
        version = definition_version_hash(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            description=description,
            predicate=spec,
            financial_state=financial_state,
            required_fixture_class=required_fixture_class,
            product_env_class=product_env_class,
        )

        async def _op(active: PostgresUnitOfWork) -> DomainInvariant:
            existing = await self._repository.get_by_version(
                active.connection,
                project_id=project_id,
                name=name,
                definition_version=version,
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            invariant = DomainInvariant(
                invariant_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                name=name,
                description=description,
                predicate=spec,
                financial_state=financial_state,
                required_fixture_class=required_fixture_class,
                product_env_class=product_env_class,
                definition_version=version,
                status="ACTIVE",
                created_by=created_by,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_invariant(active.connection, invariant)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="DomainInvariantDefined",
                aggregate_type="domain_invariant",
                aggregate_id=invariant.invariant_id,
                mission_id=mission_id,
                payload={
                    "name": name,
                    "definition_version": version,
                    "predicate_kind": spec.kind,
                    "financial_state": financial_state,
                },
                uow=active,
            )
            return invariant

        return await self._run(uow, tenant_id, project_id, _op)

    # --- retire -------------------------------------------------------------

    async def retire(
        self,
        record: DomainInvariant,
        *,
        uow: PostgresUnitOfWork | None = None,
    ) -> DomainInvariant:
        """The single lifecycle mutation: ACTIVE -> RETIRED at this call
        site, terminal thereafter."""

        async def _op(active: PostgresUnitOfWork) -> DomainInvariant:
            current = await self._require(active, record.invariant_id)
            assert_transition(current.status, "RETIRED")
            now = self._clock.now()
            await self._repository.update_status(
                active.connection,
                current.invariant_id,
                status="RETIRED",
                updated_at=now,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="DomainInvariantRetired",
                aggregate_type="domain_invariant",
                aggregate_id=current.invariant_id,
                mission_id=current.mission_id,
                payload={
                    "name": current.name,
                    "definition_version": current.definition_version,
                },
                uow=active,
            )
            return await self._require(active, current.invariant_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    # --- evaluate -------------------------------------------------------------

    async def evaluate(
        self,
        record: DomainInvariant,
        *,
        product_env: object,
        datastore_url: str,
        idempotency_key: str,
        repair_task_ref: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> InvariantEvaluation:
        """Evaluate one invariant against the real rows of one
        ProductEnvironment and record the outcome (append-only).

        Guarded by the command ledger on `idempotency_key`: same key in,
        same recorded outcome out, no second execution.
        """
        env_class = getattr(product_env, "class_", None)
        env_status = getattr(product_env, "status", None)
        env_id: UUID = product_env.product_env_id  # type: ignore[attr-defined]
        if env_class != record.product_env_class:
            raise DdeError(
                "POLICY_DENIED",
                "Each invariant declares the ProductEnvironment class it "
                "must run in (Chapter 11.5); refusing a mismatched "
                "environment",
                details={
                    "declared": record.product_env_class,
                    "environment": env_class,
                },
            )
        if env_status not in EVALUABLE_ENV_STATES:
            raise DdeError(
                "POLICY_DENIED",
                "Invariants evaluate against provisioned, seeded, "
                "migration-verified datastores only",
                details={
                    "status": env_status,
                    "evaluable": sorted(EVALUABLE_ENV_STATES),
                },
            )

        spec = record.predicate
        sql, params = compile_predicate(spec)
        request_hash = sha256_hex(
            canonical_json(
                {
                    "invariant_id": str(record.invariant_id),
                    "definition_version": record.definition_version,
                    "product_env_id": str(env_id),
                    "predicate": spec.model_dump(),
                }
            )
        )

        async def _op(active: PostgresUnitOfWork) -> InvariantEvaluation:
            ledger_record, is_new = await self._commands.begin(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(ledger_record)

            violation_rows, rows_examined = await _execute_predicate(
                datastore_url, sql, params
            )
            status, rows_checked = judge_rows(rows_examined, len(violation_rows))

            sequence = await self._repository.next_sequence(
                active.connection,
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                invariant_id=record.invariant_id,
                product_env_id=env_id,
            )
            now = self._clock.now()
            evaluation = InvariantEvaluation(
                evaluation_id=uuid7(),
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                mission_id=record.mission_id,
                invariant_id=record.invariant_id,
                definition_version=record.definition_version,
                product_env_id=env_id,
                datastore_ref=getattr(product_env, "datastore_ref", None),
                sequence=sequence,
                status=status,
                violations=[
                    Violation(
                        kind=VIOLATION_KINDS[spec.kind],
                        detail=f"group={row!r}",
                    )
                    for row in violation_rows
                ],
                rows_checked=rows_checked,
                financial_state=record.financial_state,
                repair_task_ref=repair_task_ref,
                seed_dataset_id=getattr(product_env, "seed_dataset_id", None),
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_evaluation(active.connection, evaluation)
            await self._events.append(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                event_type="DomainInvariantEvaluated",
                aggregate_type="invariant_evaluation",
                aggregate_id=evaluation.evaluation_id,
                mission_id=record.mission_id,
                payload={
                    "invariant_name": record.name,
                    "definition_version": record.definition_version,
                    "status": status,
                    "violation_count": len(violation_rows),
                    "rows_checked": rows_checked,
                    "financial_state": record.financial_state,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                command_id=ledger_record.command_id,
                result=evaluation.model_dump(mode="json"),
                uow=active,
            )
            return evaluation

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    def _replay_or_raise(self, record: CommandIdempotency) -> InvariantEvaluation:
        if record.status == "completed" and record.result is not None:
            return InvariantEvaluation.model_validate(record.result)
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

    async def _require(
        self, active: PostgresUnitOfWork, invariant_id: UUID
    ) -> DomainInvariant:
        found = await self._repository.get_invariant(active.connection, invariant_id)
        if found is None:
            raise DdeError("POLICY_DENIED", "Unknown domain invariant")
        return found


async def _execute_predicate(
    datastore_url: str, sql: str, params: dict[str, object]
) -> tuple[list[object], int]:
    """Run the compiled predicate over the PRODUCT datastore.

    Returns `(violation_rows, rows_examined_lower_bound)`. The examined-row
    count is the violating groups actually returned plus the companion
    scanned-row count; it feeds observability only — `judge_rows` turns it
    into the verdict, never the other way round.
    """
    engine = create_async_engine(datastore_url)
    try:
        async with engine.connect() as connection:
            violation_rows = (await connection.execute(text(sql), params)).fetchall()
            count_sql = _companion_count_sql(sql)
            scanned = (
                await connection.execute(text(count_sql), params)
            ).scalar_one_or_none()
    finally:
        await engine.dispose()
    return list(violation_rows), int(scanned or 0) + len(violation_rows)


def _companion_count_sql(compiled_sql: str) -> str:
    """A conservative rows-examined companion for one compiled predicate:
    the same FROM/WHERE with COUNT(*). Group-by predicates cannot report a
    meaningful per-row count, so their companion reports the group count
    they themselves returned (the caller adds the violation rows)."""
    head, sep, rest = compiled_sql.partition(" FROM ")
    if not sep:
        return "SELECT 0"
    tail = rest
    for marker in (" GROUP BY ", " HAVING ", " LIMIT "):
        index = tail.upper().find(marker)
        if index >= 0:
            tail = tail[:index]
    return f"SELECT COUNT(*) FROM {tail}"  # noqa: S608 - tail is the
    # already-validated FROM/WHERE of a compiled predicate, never raw input
