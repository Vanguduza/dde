"""Machine-readable DDE-061 chaos inventory.

Named files must exist. Production call sites are mutations (or the
live schedulable gate on `invoke_run`), not recovery-test helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

CHAOS_SCENARIO_NAMES: tuple[str, ...] = (
    "Drain / failed not schedulable",
    "Replacement mid-run",
    "Killed worker replaced",
    "Core restart then replace",
)


@dataclass(frozen=True)
class ChaosScenario:
    scenario: str
    named_tests: tuple[str, ...]
    production_call_sites: tuple[str, ...]
    deferred: str | None = None


SCENARIOS: tuple[ChaosScenario, ...] = (
    ChaosScenario(
        scenario="Drain / failed not schedulable",
        named_tests=("tests/unit/test_chaos_suite.py",),
        production_call_sites=(
            "engine.workers.service.WorkerManagerService.invoke_run",
            "engine.environments.service.ExecutionEnvironmentService.assert_schedulable",
        ),
    ),
    ChaosScenario(
        scenario="Replacement mid-run",
        named_tests=("tests/unit/test_chaos_suite.py",),
        production_call_sites=(
            "engine.environments.service.ExecutionEnvironmentService.replace",
            "engine.execution.service.ExecutionPlanService.provision_workspace",
            "engine.workers.service.WorkerManagerService.resume_run",
        ),
    ),
    ChaosScenario(
        scenario="Killed worker replaced",
        named_tests=("tests/unit/test_chaos_suite.py",),
        production_call_sites=(
            "engine.workers.service.WorkerManagerService.invoke_run",
            "engine.workers.service.WorkerManagerService.resume_run",
        ),
    ),
    ChaosScenario(
        scenario="Core restart then replace",
        named_tests=("tests/unit/test_chaos_suite.py",),
        production_call_sites=(
            "engine.workers.service.WorkerManagerService.resume_run",
        ),
        deferred="Full Core OS process-crash remains EDR-0027",
    ),
)


def assert_chaos_inventory_complete() -> None:
    names = tuple(item.scenario for item in SCENARIOS)
    if names != CHAOS_SCENARIO_NAMES:
        missing = set(CHAOS_SCENARIO_NAMES) - set(names)
        extra = set(names) - set(CHAOS_SCENARIO_NAMES)
        raise AssertionError(f"chaos inventory drift missing={missing} extra={extra}")
