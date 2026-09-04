"""AcceptanceOracle (Chapter 11.2) -- the immutable acceptance definition a
`VerificationRun` is judged against, and the pure evaluation function that
does the judging ("AcceptanceOracle evaluation" in Chapter 11.1's chain).

Chapter 3.8 does not give `AcceptanceOracle` its own ownership-matrix row (it
appears only in Chapter 3.10's list of immutable definitions); Chapter 3.6's
repository layout puts "oracle, runners, product envs" under
`engine.verification`, which is this module's home.

**Stage 1+5 scope, stated explicitly:** deterministic bindings plus the
DDE-043 `api_probe` browser probe, DDE-044 `visual_diff` pixel check,
DDE-068 `silhouette` layout-fingerprint gate, DDE-048 `android_scan`, and
DDE-049's `db_assertion`.
`judge`/`human` are rejected by `validate_definition`.
`test`/`invariant` remain command-exit evidence;
`api_probe` is a Playwright navigation whose argv is `[url, expect_text?]`;
`visual_diff` argv is `[visual/*.json]` (Chapter 11.2);
`silhouette` argv is `[url, expect_text?]` (playbook §10.3: renders the
page, fingerprints its coarse layout occupancy grid, and blocks on a
near-match against the self-generated generic-layout corpus);
`security_scan` argv is `[sast]` (DDE-045 in-process SAST);
`android_scan` argv is `[static]` (DDE-048 in-process APK analysis);
`db_assertion` argv is `[datastore_url, assertion_sql...]`
(DDE-049 read-only SQL assertions).

Mission-level oracles (`scope = "mission"`, Chapter 11.3) are authored
through `define_mission()`; `task_id` is null on those rows. `evaluate()`
of a mission oracle lives in `engine.verification.mission_oracle`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.acceptance_oracle import (
    AcceptanceOracle,
    EvidenceBinding,
    ObservableOutcome,
)
from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.hashing import oracle_version_hash
from engine.verification.repository import AcceptanceOracleRepository

#: Kinds this runner can genuinely execute. `judge`/`human` remain valid
#: enum members but have no executor here (DDE-068 for VLM critique).
#: `api_probe` is DDE-043; `visual_diff` is DDE-044 (pixel goldens);
#: `silhouette` is DDE-068 (layout-fingerprint gate, playbook §10.3);
#: `android_scan` is DDE-048; `db_assertion` is DDE-049.
EXECUTABLE_KINDS: frozenset[str] = frozenset(
    {
        "test",
        "invariant",
        "api_probe",
        "visual_diff",
        "silhouette",
        "security_scan",
        "android_scan",
        "db_assertion",
    }
)

#: Chapter 4.4's granularity policy: "Success criteria: 1-5 observable
#: criteria" -- `validate` rejects outside this range.
MIN_OBSERVABLE_OUTCOMES = 1
MAX_OBSERVABLE_OUTCOMES = 5

#: Chapter 11.2's "Oracle-first rule": a task at or above this risk class
#: cannot be auto-approved; `define()` requires an explicit `approved_by`.
APPROVAL_REQUIRED_RISK_CLASSES: frozenset[str] = frozenset({"high", "critical"})

AUTO_APPROVER = "system:acceptance_oracle_v1"


def _binding(spec: CheckSpec) -> EvidenceBinding:
    return EvidenceBinding(kind=spec.kind, ref=spec.ref, command=list(spec.command))


def _outcome(spec: CheckSpec) -> ObservableOutcome:
    return ObservableOutcome(
        outcome_id=spec.outcome_id,
        statement=spec.statement,
        evidence_binding=_binding(spec),
    )


def validate_definition(
    *,
    scope: str,
    observable_outcomes: list[CheckSpec],
    negative_cases: list[CheckSpec],
    minimum_confidence: float,
) -> None:
    """Chapter 11.2: "Every `observable_outcome` must bind to at least one
    evidence producer... A prose statement with no binding is not an
    acceptance criterion -- `validate` rejects the oracle." Extended here
    with this Stage 1 runner's executability constraints."""
    if scope not in {"task", "mission"}:
        raise DdeError(
            "ORACLE_UNSATISFIED",
            "scope must be 'task' or 'mission'",
            details={"scope": scope},
        )
    if not (
        MIN_OBSERVABLE_OUTCOMES <= len(observable_outcomes) <= MAX_OBSERVABLE_OUTCOMES
    ):
        raise DdeError(
            "ORACLE_UNSATISFIED",
            "Chapter 4.4 requires 1-5 observable success criteria",
            details={"count": len(observable_outcomes)},
        )
    if not (0.0 <= minimum_confidence <= 1.0):
        raise DdeError(
            "ORACLE_UNSATISFIED",
            "minimum_confidence must be within [0, 1]",
            details={"minimum_confidence": minimum_confidence},
        )
    for spec in [*observable_outcomes, *negative_cases]:
        if spec.kind in {"judge", "human"}:
            raise DdeError(
                "ORACLE_UNSATISFIED",
                f"kind={spec.kind!r} needs infrastructure Stage 1 does not "
                "have (certified judge capability / human review UI) -- "
                "deferred, not silently accepted",
                details={"outcome_id": str(spec.outcome_id), "kind": spec.kind},
            )
        if spec.kind not in EXECUTABLE_KINDS:
            raise DdeError(
                "ORACLE_UNSATISFIED",
                f"kind={spec.kind!r} has no Stage 1 executor "
                f"(only {sorted(EXECUTABLE_KINDS)} are runnable today)",
                details={"outcome_id": str(spec.outcome_id), "kind": spec.kind},
            )
        if not spec.ref:
            raise DdeError(
                "ORACLE_UNSATISFIED",
                "evidence_binding.ref is required (Chapter 11.2)",
                details={"outcome_id": str(spec.outcome_id)},
            )
        if not spec.command:
            raise DdeError(
                "ORACLE_UNSATISFIED",
                "a deterministic binding must carry a real, runnable command",
                details={"outcome_id": str(spec.outcome_id)},
            )


class AcceptanceOracleService:
    """Async, PostgreSQL-backed writer for `acceptance_oracles` (Chapter
    3.10: immutable definition). Each public method opens and commits its
    own unit of work unless one is supplied, so a caller composing a
    cross-module transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: AcceptanceOracleRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or AcceptanceOracleRepository()
        self._clock = clock or SystemClock()

    async def define(
        self,
        *,
        task: Task,
        outcomes: list[CheckSpec],
        minimum_confidence: float = 1.0,
        approved_by: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> AcceptanceOracle:
        """Chapter 11.2's oracle definition, deterministically derived from
        `task.success_criteria`'s intent (`task.success_criteria` is free
        text -- Chapter 4.2: "success_criteria[] -- observable, becomes
        AcceptanceOracle input" -- so the caller, not this method, supplies
        the real, checkable `CheckSpec` that makes each criterion
        observable; Stage 1 has no NLP step that derives a runnable command
        from prose)."""
        observable_outcomes = [spec for spec in outcomes if not spec.is_negative_case]
        negative_cases = [spec for spec in outcomes if spec.is_negative_case]
        validate_definition(
            scope="task",
            observable_outcomes=observable_outcomes,
            negative_cases=negative_cases,
            minimum_confidence=minimum_confidence,
        )
        if task.risk_class in APPROVAL_REQUIRED_RISK_CLASSES and approved_by is None:
            raise DdeError(
                "POLICY_DENIED",
                "Chapter 11.2's oracle-first rule: risk_class >= high "
                "requires a governance-approved oracle or a recorded "
                "human-approved exception; none was supplied",
                details={"task_id": str(task.task_id), "risk_class": task.risk_class},
            )

        outcome_dicts = [
            _outcome(spec).model_dump(mode="json") for spec in observable_outcomes
        ]
        negative_dicts = [
            _outcome(spec).model_dump(mode="json") for spec in negative_cases
        ]
        version = oracle_version_hash(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            mission_id=task.mission_id,
            task_id=task.task_id,
            scope="task",
            requirement_refs=list(task.requirement_refs),
            feature_refs=list(task.feature_refs),
            observable_outcomes=outcome_dicts,
            domain_invariants=[],
            negative_cases=negative_dicts,
            minimum_confidence=minimum_confidence,
            human_assertions=[],
        )

        async def _op(active: PostgresUnitOfWork) -> AcceptanceOracle:
            existing = await self._repository.get_by_version(
                active.connection, task.task_id, version
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            oracle = AcceptanceOracle(
                oracle_id=uuid7(),
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                oracle_version=version,
                scope="task",
                requirement_refs=list(task.requirement_refs),
                feature_refs=list(task.feature_refs),
                observable_outcomes=[_outcome(spec) for spec in observable_outcomes],
                domain_invariants=[],
                negative_cases=[_outcome(spec) for spec in negative_cases],
                minimum_confidence=minimum_confidence,
                human_assertions=[],
                approved_by=approved_by or AUTO_APPROVER,
                approved_at=now,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_oracle(active.connection, oracle)
            return oracle

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=task.tenant_id, project_id=task.project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def define_mission(
        self,
        *,
        mission: Mission,
        outcomes: list[CheckSpec],
        minimum_confidence: float = 1.0,
        approved_by: str | None = None,
        requirement_refs: list[str] | None = None,
        feature_refs: list[str] | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> AcceptanceOracle:
        """Chapter 11.3 mission-scope oracle. `task_id` is null -- never a
        fabricated task identity. Bindings remain the Stage 1 executable
        set (`test`/`invariant`); user-visible ProductEnvironment probes
        are DDE-038 and are named in evaluation `disclosed_gaps`."""
        observable_outcomes = [spec for spec in outcomes if not spec.is_negative_case]
        negative_cases = [spec for spec in outcomes if spec.is_negative_case]
        validate_definition(
            scope="mission",
            observable_outcomes=observable_outcomes,
            negative_cases=negative_cases,
            minimum_confidence=minimum_confidence,
        )
        if requirement_refs is not None:
            refs = list(requirement_refs)
        else:
            refs = list(mission.requirement_refs)
        features = list(feature_refs or [])
        outcome_dicts = [
            _outcome(spec).model_dump(mode="json") for spec in observable_outcomes
        ]
        negative_dicts = [
            _outcome(spec).model_dump(mode="json") for spec in negative_cases
        ]
        version = oracle_version_hash(
            tenant_id=mission.tenant_id,
            project_id=mission.project_id,
            mission_id=mission.mission_id,
            task_id=None,
            scope="mission",
            requirement_refs=refs,
            feature_refs=features,
            observable_outcomes=outcome_dicts,
            domain_invariants=[],
            negative_cases=negative_dicts,
            minimum_confidence=minimum_confidence,
            human_assertions=[],
        )

        async def _op(active: PostgresUnitOfWork) -> AcceptanceOracle:
            existing = await self._repository.get_mission_by_version(
                active.connection, mission.mission_id, version
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            oracle = AcceptanceOracle(
                oracle_id=uuid7(),
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                mission_id=mission.mission_id,
                task_id=None,
                oracle_version=version,
                scope="mission",
                requirement_refs=refs,
                feature_refs=features,
                observable_outcomes=[_outcome(spec) for spec in observable_outcomes],
                domain_invariants=[],
                negative_cases=[_outcome(spec) for spec in negative_cases],
                minimum_confidence=minimum_confidence,
                human_assertions=[],
                approved_by=approved_by or AUTO_APPROVER,
                approved_at=now,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_oracle(active.connection, oracle)
            return oracle

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=mission.tenant_id, project_id=mission.project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def get_oracle(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        oracle_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> AcceptanceOracle:
        async def _op(active: PostgresUnitOfWork) -> AcceptanceOracle:
            record = await self._repository.get_oracle(active.connection, oracle_id)
            if record is None:
                raise DdeError("POLICY_DENIED", "Unknown acceptance oracle")
            return record

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result
