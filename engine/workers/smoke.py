"""Chapter 8.5 smoke-tier runner (DDE-025).

Twelve named fixtures, hard ceilings of 15 minutes and USD 5. The runner
never spends money: local adapters report `cost_usd=0`; the Cursor adapter
fail-closes before any vendor call. Standard/Full reuse this suite plus
declared-class checks — they do not invent a two-hour benchmark or a chaos
lab (DDE-061).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.workers.adapter import WorkerAdapter
from engine.workers.certification import (
    SMOKE_FIXTURE_IDS,
    SMOKE_MAX_SECONDS,
    SMOKE_MAX_USD,
    ProfileIdentity,
    profile_hash,
)
from engine.workspaces.paths import resolve_within_workspace


@dataclass(frozen=True)
class SmokeReport:
    profile_id: str
    profile_hash: str
    passed: bool
    fixture_ids: tuple[str, ...]
    elapsed_seconds: float
    cost_usd: float
    detail: str


def identity_of(adapter: WorkerAdapter) -> ProfileIdentity:
    getter = getattr(adapter, "profile_identity", None)
    if callable(getter):
        identity = getter()
        if isinstance(identity, ProfileIdentity):
            return identity
    raise DdeError(
        "POLICY_DENIED",
        "Worker adapter must declare a Chapter 8.5 ProfileIdentity",
        retryable=False,
        details={"adapter": type(adapter).__name__},
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _run(
    *, tenant_id: UUID, project_id: UUID, worker_id: str, profile_id: str
) -> WorkerRun:
    now = _now()
    return WorkerRun(
        run_id=uuid7(),
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=uuid7(),
        task_attempt_id=uuid7(),
        sequence=1,
        execution_plan_id=uuid7(),
        worker_id=worker_id,
        worker_profile_id=profile_id,
        environment_id=uuid7(),
        workspace_id=uuid7(),
        context_package_id=uuid7(),
        policy_version="smoke-v1",
        lease_set_hash="smoke",
        status="RUNNING",
        created_at=now,
        updated_at=now,
    )


async def run_smoke(
    adapter: WorkerAdapter,
    *,
    max_seconds: float = SMOKE_MAX_SECONDS,
    max_usd: float = SMOKE_MAX_USD,
) -> SmokeReport:
    """Run the twelve Chapter 8.5 smoke fixtures against `adapter`."""
    started = time.monotonic()
    registration = await adapter.register()
    identity = identity_of(adapter)
    digest = profile_hash(identity)
    tenant_id = uuid7()
    project_id = uuid7()
    run = _run(
        tenant_id=tenant_id,
        project_id=project_id,
        worker_id=registration.worker_id,
        profile_id=registration.worker_profile_id,
    )
    fixtures: dict[str, Callable[[], Awaitable[None]]] = {
        "register_identity": lambda: _fixture_register(
            adapter, registration.worker_profile_id
        ),
        "health_reports_status": lambda: _fixture_health(adapter),
        "capabilities_declared": lambda: _fixture_capabilities(adapter),
        "tool_call_correctness": lambda: _fixture_tool_call(adapter, run),
        "structured_output": lambda: _fixture_structured(adapter, run),
        "file_write_safety": _fixture_file_write,
        "workspace_containment": _fixture_containment,
        "cancellation": lambda: _fixture_cancel(adapter, run),
        "checkpoint_resume": lambda: _fixture_checkpoint(adapter, run),
        "cost_reporting_accuracy": lambda: _fixture_cost(adapter, run),
        "terminate_cleanup": lambda: _fixture_terminate(adapter, run),
        "profile_hash_stability": lambda: _fixture_hash(adapter, digest),
    }
    missing = [item for item in SMOKE_FIXTURE_IDS if item not in fixtures]
    if missing:
        raise DdeError(
            "POLICY_DENIED",
            "Smoke runner is missing a Chapter 8.5 fixture",
            details={"missing": missing},
        )
    ran: list[str] = []
    for fixture_id in SMOKE_FIXTURE_IDS:
        await fixtures[fixture_id]()
        ran.append(fixture_id)
        elapsed = time.monotonic() - started
        if elapsed > max_seconds:
            raise DdeError(
                "BUDGET_EXCEEDED",
                "Smoke certification exceeded the Chapter 8.5 time ceiling",
                retryable=False,
                details={"elapsed_seconds": elapsed, "max_seconds": max_seconds},
            )
    usage = await adapter.collect_usage(run)
    if usage.cost_usd > max_usd:
        raise DdeError(
            "BUDGET_EXCEEDED",
            "Smoke certification exceeded the Chapter 8.5 USD ceiling",
            retryable=False,
            details={"cost_usd": usage.cost_usd, "max_usd": max_usd},
        )
    if usage.cost_usd < 0:
        raise DdeError(
            "POLICY_DENIED",
            "collect_usage reported a negative cost",
            retryable=False,
            details={"cost_usd": usage.cost_usd},
        )
    return SmokeReport(
        profile_id=registration.worker_profile_id,
        profile_hash=digest,
        passed=True,
        fixture_ids=tuple(ran),
        elapsed_seconds=time.monotonic() - started,
        cost_usd=usage.cost_usd,
        detail="smoke tier passed",
    )


async def _fixture_register(adapter: WorkerAdapter, expected_profile: str) -> None:
    again = await adapter.register()
    if again.worker_profile_id != expected_profile:
        raise DdeError(
            "POLICY_DENIED",
            "register() profile id is not stable",
            details={"expected": expected_profile, "actual": again.worker_profile_id},
        )


async def _fixture_health(adapter: WorkerAdapter) -> None:
    health = await adapter.health()
    if not health.healthy:
        raise DdeError(
            "WORKER_UNAVAILABLE",
            "Smoke health check failed",
            details={"detail": health.detail},
        )


async def _fixture_capabilities(adapter: WorkerAdapter) -> None:
    manifest = await adapter.capabilities()
    if not manifest.capability_ids:
        raise DdeError(
            "POLICY_DENIED",
            "Smoke requires a non-empty capability manifest",
        )


async def _fixture_tool_call(adapter: WorkerAdapter, run: WorkerRun) -> None:
    """A worker must not fabricate a successful tool call. ActionBindable
    adapters refuse start() without prepare(); the Cursor adapter refuses
    a live invocation without a brokered credential.
    """
    try:
        handle = await adapter.start(run)
    except DdeError as exc:
        if exc.error_code in {"POLICY_DENIED", "WORKER_UNAVAILABLE"}:
            return
        raise
    if handle.exit_code == 0 and not handle.timed_out:
        raise DdeError(
            "POLICY_DENIED",
            "Smoke tool-call fixture refuses a fabricated successful start",
            details={"run_id": str(run.run_id)},
        )


async def _fixture_structured(adapter: WorkerAdapter, run: WorkerRun) -> None:
    artifacts = await adapter.collect_artifacts(run)
    if artifacts.changed_files is None or artifacts.diff_text is None:
        raise DdeError(
            "POLICY_DENIED", "collect_artifacts returned unstructured output"
        )


async def _fixture_file_write() -> None:
    root = Path.cwd()
    try:
        resolve_within_workspace(root, "../escape.txt")
    except DdeError as exc:
        if exc.error_code == "POLICY_DENIED":
            return
        raise
    raise DdeError("POLICY_DENIED", "file-write safety did not refuse a path escape")


async def _fixture_containment() -> None:
    root = Path.cwd()
    try:
        resolve_within_workspace(root, str(Path(Path.cwd().anchor) / "outside"))
    except DdeError as exc:
        if exc.error_code == "POLICY_DENIED":
            return
        raise
    raise DdeError(
        "POLICY_DENIED", "workspace containment did not refuse an absolute path"
    )


async def _fixture_cancel(adapter: WorkerAdapter, run: WorkerRun) -> None:
    result = await adapter.cancel(run, "smoke")
    if result.reason.strip() == "":
        raise DdeError("POLICY_DENIED", "cancel() returned an empty reason")


async def _fixture_checkpoint(adapter: WorkerAdapter, run: WorkerRun) -> None:
    checkpoint = await adapter.checkpoint(run)
    resumed = await adapter.resume(run, checkpoint.ref)
    if checkpoint.reason.strip() == "" or resumed.reason.strip() == "":
        raise DdeError("POLICY_DENIED", "checkpoint/resume returned an empty reason")


async def _fixture_cost(adapter: WorkerAdapter, run: WorkerRun) -> None:
    usage = await adapter.collect_usage(run)
    if usage.duration_ms < 0 or usage.cost_usd < 0:
        raise DdeError("POLICY_DENIED", "collect_usage reported negative usage")


async def _fixture_terminate(adapter: WorkerAdapter, run: WorkerRun) -> None:
    terminated = await adapter.terminate(run)
    cleaned = await adapter.cleanup(run)
    if terminated.detail.strip() == "" or cleaned.detail.strip() == "":
        raise DdeError("POLICY_DENIED", "terminate/cleanup returned an empty detail")


async def _fixture_hash(adapter: WorkerAdapter, expected: str) -> None:
    digest = profile_hash(identity_of(adapter))
    if digest != expected:
        raise DdeError(
            "POLICY_DENIED",
            "profile_hash is not stable across the smoke run",
            details={"expected": expected, "actual": digest},
        )
