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

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from engine.capabilities.browser import (
    BrowserCapability,
    BrowserCaptureSpec,
    BrowserProbeSpec,
)
from engine.capabilities.security import SecurityCapability, SecurityScanSpec
from engine.contracts.verification_run import CheckResult
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.truth.db import PostgresUnitOfWork
from engine.verification.pixel_compare import compare_pngs
from engine.verification.visual_spec import load_visual_diff_spec
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


def _workspace_root(workspace: Workspace) -> Path:
    if not workspace.workspace_path:
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff requires a workspace with a filesystem path",
            details={"workspace_id": str(workspace.workspace_id)},
        )
    return Path(workspace.workspace_path)


async def run_check(
    workspaces: WorkspaceService,
    workspace: Workspace,
    spec: CheckSpec,
    *,
    timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
    uow: PostgresUnitOfWork | None = None,
    browser: BrowserCapability | None = None,
    security: SecurityCapability | None = None,
) -> CheckResult:
    """Execute one real check. `test`/`invariant` run via
    `WorkspaceService.execute()`. `api_probe`/`visual_diff` run via the
    injected `BrowserCapability`. `security_scan` runs via the injected
    `SecurityCapability`."""
    if spec.kind == "api_probe":
        return await _run_api_probe(spec, browser=browser)
    if spec.kind == "visual_diff":
        return await _run_visual_diff(workspace, spec, browser=browser)
    if spec.kind == "security_scan":
        return await _run_security_scan(workspace, spec, security=security)
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


async def _run_visual_diff(
    workspace: Workspace,
    spec: CheckSpec,
    *,
    browser: BrowserCapability | None,
) -> CheckResult:
    if browser is None:
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff requires a BrowserCapability (capability.browser); "
            "none was injected on the verification runner",
            details={"check_ref": spec.ref},
        )
    if not spec.command:
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff command[0] must be the workspace path to the "
            "visual/*.json spec (Chapter 11.2)",
            details={"check_ref": spec.ref},
        )
    root = _workspace_root(workspace)
    spec_path = (root / spec.command[0]).resolve()
    if not str(spec_path).startswith(str(root.resolve())):
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff spec path escapes the workspace",
            details={"path": spec.command[0]},
        )
    visual = load_visual_diff_spec(spec_path)
    golden_path = (root / visual.golden_path).resolve()
    if not str(golden_path).startswith(str(root.resolve())):
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff golden_path escapes the workspace",
            details={"golden_path": visual.golden_path},
        )
    if not golden_path.is_file():
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff golden PNG is missing",
            details={"golden_path": str(golden_path)},
        )

    capture = await browser.screenshot(
        BrowserCaptureSpec(
            url=visual.url,
            viewport_width=visual.viewport_width,
            viewport_height=visual.viewport_height,
            expect_text=visual.expect_text,
        )
    )
    if capture.exit_code != 0 or capture.timed_out:
        status = _check_status(exit_code=capture.exit_code, timed_out=capture.timed_out)
        return CheckResult(
            check_ref=spec.ref,
            kind=spec.kind,
            command=list(spec.command),
            exit_code=capture.exit_code,
            stdout="",
            stderr=capture.stderr,
            duration_ms=capture.duration_ms,
            timed_out=capture.timed_out,
            status=status,
        )

    golden_bytes = golden_path.read_bytes()
    compare = compare_pngs(
        actual=capture.png_bytes,
        golden=golden_bytes,
        max_diff_pixel_ratio=visual.max_diff_pixel_ratio,
    )
    actual_rel = visual.actual_path or f".dde/visual/{spec.ref.replace(':', '_')}.png"
    diff_rel = visual.diff_path or f".dde/visual/{spec.ref.replace(':', '_')}.diff.png"
    actual_path = root / actual_rel
    actual_path.parent.mkdir(parents=True, exist_ok=True)
    actual_path.write_bytes(capture.png_bytes)
    diff_written: str | None = None
    if compare.diff_png is not None:
        diff_path = root / diff_rel
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_bytes(compare.diff_png)
        diff_written = diff_rel

    evidence = {
        "actual_path": actual_rel,
        "golden_path": visual.golden_path,
        "diff_path": diff_written,
        "actual_sha256": hashlib.sha256(capture.png_bytes).hexdigest(),
        "golden_sha256": hashlib.sha256(golden_bytes).hexdigest(),
        "diff_ratio": compare.diff_ratio,
        "max_diff_pixel_ratio": visual.max_diff_pixel_ratio,
        "detail": compare.detail,
    }
    exit_code = 0 if compare.passed else 1
    return CheckResult(
        check_ref=spec.ref,
        kind=spec.kind,
        command=list(spec.command),
        exit_code=exit_code,
        stdout=json.dumps(evidence, sort_keys=True),
        stderr="" if compare.passed else compare.detail,
        duration_ms=capture.duration_ms,
        timed_out=False,
        status=_check_status(exit_code=exit_code, timed_out=False),
    )


async def _run_security_scan(
    workspace: Workspace,
    spec: CheckSpec,
    *,
    security: SecurityCapability | None,
) -> CheckResult:
    if security is None:
        raise DdeError(
            "POLICY_DENIED",
            "security_scan requires a SecurityCapability "
            "(capability.security); none was injected on the "
            "verification runner",
            details={"check_ref": spec.ref},
        )
    if not workspace.workspace_path:
        raise DdeError(
            "POLICY_DENIED",
            "security_scan requires a workspace with a filesystem path",
            details={"workspace_id": str(workspace.workspace_id)},
        )
    mode = spec.command[0] if spec.command else "sast"
    result = await security.scan(
        SecurityScanSpec(root=workspace.workspace_path, mode=mode)
    )
    return CheckResult(
        check_ref=spec.ref,
        kind=spec.kind,
        command=list(spec.command) if spec.command else [mode],
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
        status=_check_status(exit_code=result.exit_code, timed_out=result.timed_out),
    )
