"""Chapter 11.1's mechanical check execution: a real subprocess, rooted at
the real `Workspace` the worker touched, whose real exit code is the
evidence.

`CheckSpec` is a caller-declared, deterministic binding -- exactly like
`engine.workers.adapter.WorkerAction`'s caller-supplied `command`, this
module never invents which command proves an outcome. `run_check` reuses
`engine.workspaces.service.WorkspaceService.execute()` (Chapter 7.5) rather
than reimplementing subprocess execution, matching the mission brief's
explicit instruction: verification is a check *runner*, not a second
process-execution stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from engine.capabilities.browser import BrowserCapability, BrowserProbeSpec
from engine.contracts.verification_run import CheckResult
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.truth.db import PostgresUnitOfWork
from engine.workspaces.service import WorkspaceService

DEFAULT_CHECK_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class CheckSpec:
    """One `ObservableOutcome`'s (or negative case's) executable binding,
    supplied by whoever authors the `AcceptanceOracle` (Chapter 11.2's
    `evidence_binding`). `kind`/`ref` mirror the oracle's own binding fields;
    `command` is the additive, literal argv this Stage 1 runner actually
    invokes (Chapter 11.2's ASCII sketch names the binding but not its
    invocation mechanics)."""

    outcome_id: UUID
    statement: str
    kind: str
    ref: str
    command: list[str]
    is_negative_case: bool = False


def _check_status(*, exit_code: int, timed_out: bool) -> str:
    """`ERRORED` means the check could not produce a truth value (timeout, or
    the backend could not even spawn the process -- `LocalProcessBackend.run`
    reports that as `exit_code=-1`). `PASSED`/`FAILED` are both genuine,
    checked outcomes -- a non-zero exit from ruff/mypy/pytest is real
    evidence the statement does not hold, never an unhandled exception."""
    if timed_out or exit_code < 0:
        return "ERRORED"
    if exit_code == 0:
        return "PASSED"
    return "FAILED"


async def run_check(
    workspaces: WorkspaceService,
    workspace: Workspace,
    spec: CheckSpec,
    *,
    timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
    uow: PostgresUnitOfWork | None = None,
    browser: BrowserCapability | None = None,
) -> CheckResult:
    """Execute one real check. `test`/`invariant` run via
    `WorkspaceService.execute()`. `api_probe` runs via the injected
    `BrowserCapability` (Playwright in `adapters/playwright`) — never a
    second process-execution stack for ordinary commands."""
    if spec.kind == "api_probe":
        return await _run_api_probe(spec, browser=browser)
    result = await workspaces.execute(
        workspace=workspace,
        command=spec.command,
        timeout_seconds=timeout_seconds,
        uow=uow,
    )
    status = _check_status(exit_code=result.exit_code, timed_out=result.timed_out)
    return CheckResult(
        check_ref=spec.ref,
        kind=spec.kind,
        command=list(result.command),
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
        status=status,
    )


async def _run_api_probe(
    spec: CheckSpec, *, browser: BrowserCapability | None
) -> CheckResult:
    if browser is None:
        raise DdeError(
            "POLICY_DENIED",
            "api_probe requires a BrowserCapability (capability.browser); "
            "none was injected on the verification runner",
            details={"check_ref": spec.ref},
        )
    url = spec.command[0]
    expect_text = spec.command[1] if len(spec.command) > 1 else None
    probe = await browser.probe(BrowserProbeSpec(url=url, expect_text=expect_text))
    status = _check_status(exit_code=probe.exit_code, timed_out=probe.timed_out)
    return CheckResult(
        check_ref=spec.ref,
        kind=spec.kind,
        command=list(spec.command),
        exit_code=probe.exit_code,
        stdout=probe.stdout,
        stderr=probe.stderr,
        duration_ms=probe.duration_ms,
        timed_out=probe.timed_out,
        status=status,
    )
