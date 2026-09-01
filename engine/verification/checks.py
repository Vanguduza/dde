"""Chapter 11.1's mechanical check execution.

`CheckSpec` is a caller-declared, deterministic binding. `test`/`invariant`
reuse `WorkspaceService.execute`; specialized evidence kinds use injected
capability contracts so vendor runtimes stay in `adapters/**`.

DDE-068 extends `visual_diff`: after the DDE-044 screenshot/golden compare,
the same real ProductEnvironment is measured through `BrowserCapability.layout`
under normal and reduced-motion preferences. Density, generic-silhouette and
reduced-motion failures are hard deterministic failures and are persisted in
the check evidence JSON. They cannot later be waived by a VLM score or pixel
sign-off.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from engine.capabilities.android import AndroidCapability, AndroidScanSpec
from engine.capabilities.browser import (
    BrowserCapability,
    BrowserCaptureSpec,
    BrowserLayoutSpec,
    BrowserProbeSpec,
)
from engine.capabilities.database import (
    DatabaseAssertionSpec,
    DatabaseCapability,
)
from engine.capabilities.security import SecurityCapability, SecurityScanSpec
from engine.contracts.verification_run import CheckResult
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.truth.db import PostgresUnitOfWork
from engine.verification.pixel_compare import compare_pngs
from engine.verification.visual_quality import assess_visual_quality
from engine.verification.visual_spec import load_visual_diff_spec
from engine.workspaces.service import WorkspaceService

DEFAULT_CHECK_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class CheckSpec:
    """One AcceptanceOracle outcome's executable binding."""

    outcome_id: UUID
    statement: str
    kind: str
    ref: str
    command: list[str]
    is_negative_case: bool = False


def _check_status(*, exit_code: int, timed_out: bool) -> str:
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
    android: AndroidCapability | None = None,
    database: DatabaseCapability | None = None,
) -> CheckResult:
    """Execute one real check using the capability that owns its effects."""
    if spec.kind == "api_probe":
        return await _run_api_probe(spec, browser=browser)
    if spec.kind == "visual_diff":
        return await _run_visual_diff(workspace, spec, browser=browser)
    if spec.kind == "security_scan":
        return await _run_security_scan(workspace, spec, security=security)
    if spec.kind == "android_scan":
        return await _run_android_scan(workspace, spec, android=android)
    if spec.kind == "db_assertion":
        return await _run_db_assertion(spec, database=database)
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

    quality_payload: dict[str, object] | None = None
    quality_passed = True
    quality_duration = 0
    if visual.quality_gate:
        normal_layout = await browser.layout(
            BrowserLayoutSpec(
                url=visual.url,
                viewport_width=visual.viewport_width,
                viewport_height=visual.viewport_height,
                expect_text=visual.expect_text,
                reduced_motion=False,
            )
        )
        reduced_layout = await browser.layout(
            BrowserLayoutSpec(
                url=visual.url,
                viewport_width=visual.viewport_width,
                viewport_height=visual.viewport_height,
                expect_text=visual.expect_text,
                reduced_motion=True,
            )
        )
        quality_duration = normal_layout.duration_ms + reduced_layout.duration_ms
        quality = assess_visual_quality(
            normal_layout,
            reduced_layout,
            viewport_width=visual.viewport_width,
            viewport_height=visual.viewport_height,
            density_floor=visual.density_floor,
            silhouette_threshold=visual.silhouette_threshold,
            end_state_similarity_floor=visual.reduced_motion_end_state_similarity,
        )
        quality_payload = quality.as_dict()
        quality_passed = quality.passed

    evidence = {
        "actual_path": actual_rel,
        "golden_path": visual.golden_path,
        "diff_path": diff_written,
        "actual_sha256": hashlib.sha256(capture.png_bytes).hexdigest(),
        "golden_sha256": hashlib.sha256(golden_bytes).hexdigest(),
        "diff_ratio": compare.diff_ratio,
        "max_diff_pixel_ratio": visual.max_diff_pixel_ratio,
        "pixel_detail": compare.detail,
        "quality_gate": visual.quality_gate,
        "quality": quality_payload,
    }
    passed = compare.passed and quality_passed
    errors: list[str] = []
    if not compare.passed:
        errors.append(compare.detail)
    if quality_payload is not None and not quality_passed:
        failures = quality_payload.get("failures")
        errors.append(f"visual quality failures: {failures}")
    exit_code = 0 if passed else 1
    return CheckResult(
        check_ref=spec.ref,
        kind=spec.kind,
        command=list(spec.command),
        exit_code=exit_code,
        stdout=json.dumps(evidence, sort_keys=True),
        stderr="; ".join(errors),
        duration_ms=capture.duration_ms + quality_duration,
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


async def _run_android_scan(
    workspace: Workspace,
    spec: CheckSpec,
    *,
    android: AndroidCapability | None,
) -> CheckResult:
    if android is None:
        raise DdeError(
            "POLICY_DENIED",
            "android_scan requires an AndroidCapability "
            "(capability.android_analysis); none was injected on the "
            "verification runner",
            details={"check_ref": spec.ref},
        )
    if not workspace.workspace_path:
        raise DdeError(
            "POLICY_DENIED",
            "android_scan requires a workspace with a filesystem path",
            details={"workspace_id": str(workspace.workspace_id)},
        )
    mode = spec.command[0] if spec.command else "static"
    result = await android.scan(
        AndroidScanSpec(root=workspace.workspace_path, mode=mode)
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


async def _run_db_assertion(
    spec: CheckSpec,
    *,
    database: DatabaseCapability | None,
) -> CheckResult:
    if database is None:
        raise DdeError(
            "POLICY_DENIED",
            "db_assertion requires a DatabaseCapability "
            "(capability.database); none was injected on the "
            "verification runner",
            details={"check_ref": spec.ref},
        )
    if not spec.command:
        raise DdeError(
            "VALIDATION_FAILED",
            "db_assertion binding requires [datastore_url, assertion_sql...]",
            details={"check_ref": spec.ref},
        )
    datastore_url = spec.command[0]
    statements = tuple(spec.command[1:])
    result = await database.assert_(
        DatabaseAssertionSpec(datastore_url=datastore_url, statements=statements)
    )
    return CheckResult(
        check_ref=spec.ref,
        kind=spec.kind,
        command=list(spec.command),
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
        status=_check_status(exit_code=result.exit_code, timed_out=result.timed_out),
    )
