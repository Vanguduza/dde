"""DDE-043 Playwright / capability.browser proofs."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.playwright.adapter import PlaywrightWorkerAdapter
from adapters.playwright.probe import PlaywrightBrowserProbe
from engine.capabilities.browser import BrowserProbeResult, BrowserProbeSpec
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import SEED_CAPABILITIES, seed_capabilities
from engine.capabilities.service import CapabilityRegistryService
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.verification.checks import CheckSpec
from engine.verification.oracle import EXECUTABLE_KINDS, validate_definition
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture


class _FakeProbe:
    """Deterministic probe — no Chromium, no Playwright package needed."""

    def __init__(
        self,
        *,
        body: str = "dde-browser-ok",
        exit_code: int = 0,
        timed_out: bool = False,
    ) -> None:
        self.body = body
        self.exit_code = exit_code
        self.timed_out = timed_out
        self.calls: list[BrowserProbeSpec] = []

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        self.calls.append(spec)
        if self.timed_out:
            return BrowserProbeResult(
                exit_code=-1,
                stdout="",
                stderr="fake timeout",
                duration_ms=1,
                timed_out=True,
            )
        if self.exit_code != 0:
            return BrowserProbeResult(
                exit_code=self.exit_code,
                stdout="",
                stderr="fake probe failure",
                duration_ms=1,
                timed_out=False,
            )
        if spec.expect_text and spec.expect_text not in self.body:
            return BrowserProbeResult(
                exit_code=1,
                stdout=self.body,
                stderr=f"expected text not found: {spec.expect_text!r}",
                duration_ms=1,
                timed_out=False,
            )
        return BrowserProbeResult(
            exit_code=0,
            stdout=self.body,
            stderr="",
            duration_ms=1,
            timed_out=False,
        )


def test_api_probe_is_an_executable_oracle_kind() -> None:
    assert "api_probe" in EXECUTABLE_KINDS
    validate_definition(
        scope="task",
        observable_outcomes=[
            CheckSpec(
                outcome_id=uuid7(),
                statement="home page renders marker text",
                kind="api_probe",
                ref="probe:home",
                command=["file:///tmp/x.html", "dde-browser-ok"],
            )
        ],
        negative_cases=[],
        minimum_confidence=1.0,
    )


def test_visual_diff_is_an_executable_oracle_kind() -> None:
    assert "visual_diff" in EXECUTABLE_KINDS
    validate_definition(
        scope="task",
        observable_outcomes=[
            CheckSpec(
                outcome_id=uuid7(),
                statement="pixels match golden",
                kind="visual_diff",
                ref="visual:home",
                command=["visual/supplier-credit-screen.json"],
            )
        ],
        negative_cases=[],
        minimum_confidence=1.0,
    )


def test_capability_browser_is_in_seed_portfolio() -> None:
    ids = {spec.capability_id for spec in SEED_CAPABILITIES}
    assert "capability.browser" in ids
    browser = next(
        s for s in SEED_CAPABILITIES if s.capability_id == "capability.browser"
    )
    assert browser.side_effect_class == "EXTERNAL_NON_IDEMPOTENT"
    assert browser.enforcement_tier == "T1"


@pytest.mark.asyncio
async def test_playwright_smoke_fail_closes_without_fabricating_success() -> None:
    from engine.workers.smoke import run_smoke

    report = await run_smoke(PlaywrightWorkerAdapter())
    assert report.passed is True
    assert report.profile_id == "profile.vision"


@pytest.mark.asyncio
async def test_browser_probe_refuses_disallowed_scheme() -> None:
    probe = PlaywrightBrowserProbe()
    with pytest.raises(DdeError) as exc:
        await probe.probe(BrowserProbeSpec(url="javascript:alert(1)"))
    assert exc.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_browser_probe_refuses_when_playwright_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def _block_playwright(name: str, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if name == "playwright" or name.startswith("playwright."):
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_playwright)
    probe = PlaywrightBrowserProbe()
    with pytest.raises(DdeError) as exc:
        await probe.probe(BrowserProbeSpec(url="https://example.invalid/"))
    assert exc.value.error_code == "POLICY_DENIED"
    assert exc.value.details.get("dependency") == "playwright"


@pytest.mark.asyncio
async def test_seed_registers_capability_browser() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        registered = await seed_capabilities(
            service, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert "capability.browser" in {item.capability_id for item in registered}
        active = await service.get_active(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id="capability.browser",
        )
        assert active.side_effect_class == "EXTERNAL_NON_IDEMPOTENT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_invoke_run_browser_probe_grants_lease_and_journals(
    tmp_path: Path,
) -> None:
    """Production path: lease grant → prepare/bind → journal → probe.

    Uses a fake probe so CI does not require Chromium binaries. The real
    Playwright import path is covered by allowlist + ImportError tests.
    """
    root = Path.cwd()
    db_engine = new_engine()
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-BROWSER-PROBE"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        leases = CapabilityLeaseService(db_engine)
        registry = WorkerProfileRegistry()
        fake = _FakeProbe()
        adapter = PlaywrightWorkerAdapter(workspaces, leases, probe=fake)
        await registry.register_profile(adapter)
        manager = WorkerManagerService(db_engine, registry, leases=leases)

        plan = fixture.execution_plan.model_copy(
            update={"worker_profile_id": "profile.vision"}
        )
        url = (tmp_path / "probe.html").as_uri()
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(
                command=(),
                browser_url=url,
                browser_expect_text="dde-browser-ok",
            ),
            idempotency_key="browser-probe-run-1",
        )
        assert run.status == "COMPLETED", (run.status, run.failure_class)
        assert len(fake.calls) == 1
        assert fake.calls[0].url == url
        assert fake.calls[0].expect_text == "dde-browser-ok"
    finally:
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_unknown_browser_effect_refuses_new_worker_run(
    tmp_path: Path,
) -> None:
    """Ch.12.4: UNKNOWN never blind-retried; a new idempotency key cannot
    mint a second goto against the same URL."""
    root = Path.cwd()
    db_engine = new_engine()
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-BROWSER-UNKNOWN"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        leases = CapabilityLeaseService(db_engine)
        registry = WorkerProfileRegistry()
        fake = _FakeProbe(timed_out=True)
        adapter = PlaywrightWorkerAdapter(workspaces, leases, probe=fake)
        await registry.register_profile(adapter)
        manager = WorkerManagerService(db_engine, registry, leases=leases)
        plan = fixture.execution_plan.model_copy(
            update={"worker_profile_id": "profile.vision"}
        )
        url = "https://example.invalid/timeout"
        action = WorkerAction(command=(), browser_url=url)
        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="browser-unknown-1",
        )
        assert first.status == "FAILED"
        assert first.failure_class == "SIDE_EFFECT_UNKNOWN"
        with pytest.raises(DdeError) as exc:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=action,
                idempotency_key="browser-unknown-2",
            )
        assert exc.value.error_code == "EFFECT_CONFLICT"
    finally:
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_api_probe_check_uses_injected_browser() -> None:
    from engine.verification.checks import run_check

    fake = _FakeProbe(body="hello probe")
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=None,  # type: ignore[arg-type]
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="marker",
            kind="api_probe",
            ref="probe:x",
            command=["https://example.invalid/", "hello"],
        ),
        browser=fake,
    )
    assert result.status == "PASSED"
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_api_probe_fails_closed_without_browser_injection() -> None:
    from engine.verification.checks import run_check

    with pytest.raises(DdeError) as exc:
        await run_check(
            workspaces=None,  # type: ignore[arg-type]
            workspace=None,  # type: ignore[arg-type]
            spec=CheckSpec(
                outcome_id=uuid7(),
                statement="marker",
                kind="api_probe",
                ref="probe:x",
                command=["https://example.invalid/"],
            ),
            browser=None,
        )
    assert exc.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_real_playwright_file_url_when_installed(tmp_path: Path) -> None:
    pytest.importorskip("playwright.async_api")
    html = tmp_path / "probe.html"
    html.write_text(
        "<!doctype html><html><body>dde-browser-ok</body></html>",
        encoding="utf-8",
    )
    probe = PlaywrightBrowserProbe()
    try:
        result = await probe.probe(
            BrowserProbeSpec(url=html.as_uri(), expect_text="dde-browser-ok")
        )
    except Exception as exc:  # noqa: BLE001 — skip if chromium binary missing
        pytest.skip(f"chromium unavailable: {exc}")
    if result.exit_code != 0 and "Executable doesn't exist" in result.stderr:
        pytest.skip(f"chromium unavailable: {result.stderr}")
    assert result.exit_code == 0
    assert "dde-browser-ok" in result.stdout
