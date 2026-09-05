from __future__ import annotations

from uuid import uuid4

import pytest

from engine.capabilities.browser import (
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserProbeResult,
    BrowserProbeSpec,
)
from engine.capabilities.visual_critic import (
    VisualCritiqueRequest,
    VisualCritiqueResult,
)
from engine.verification.capability_runtime import (
    CAPABILITY_BROWSER,
    CAPABILITY_VISUAL_CRITIQUE,
    LeaseBoundBrowserCapability,
    LeaseBoundVisualCriticCapability,
)
from engine.verification.checks import CheckSpec, _render_bound_spec


class _Leases:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    async def require_active_lease(self, **kwargs: object) -> object:
        self.calls.append((kwargs["lease_id"], str(kwargs["capability_id"])))
        return object()


class _Browser:
    def __init__(self) -> None:
        self.probes = 0
        self.screenshots = 0

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        self.probes += 1
        return BrowserProbeResult(0, spec.url, "", 1, False)

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        self.screenshots += 1
        return BrowserCaptureResult(0, b"png", "", 1, False)


class _Critic:
    def __init__(self) -> None:
        self.calls = 0

    async def critique(self, request: VisualCritiqueRequest) -> VisualCritiqueResult:
        self.calls += 1
        return VisualCritiqueResult(0, "{}", "", 1, False)


@pytest.mark.asyncio
async def test_browser_runtime_checks_non_worker_lease_before_every_call() -> None:
    leases = _Leases()
    browser = _Browser()
    lease_id = uuid4()
    bound = LeaseBoundBrowserCapability(
        leases=leases,  # type: ignore[arg-type]
        tenant_id=uuid4(),
        project_id=uuid4(),
        lease_id=lease_id,
        inner=browser,
    )
    await bound.probe(BrowserProbeSpec(url="file:///x.html"))
    await bound.screenshot(
        BrowserCaptureSpec(url="file:///x.html", viewport_width=1, viewport_height=1)
    )
    assert leases.calls == [
        (lease_id, CAPABILITY_BROWSER),
        (lease_id, CAPABILITY_BROWSER),
    ]
    assert browser.probes == 1
    assert browser.screenshots == 1


@pytest.mark.asyncio
async def test_visual_critic_runtime_checks_its_narrow_lease() -> None:
    leases = _Leases()
    critic = _Critic()
    lease_id = uuid4()
    bound = LeaseBoundVisualCriticCapability(
        leases=leases,  # type: ignore[arg-type]
        tenant_id=uuid4(),
        project_id=uuid4(),
        lease_id=lease_id,
        inner=critic,
    )
    await bound.critique(
        VisualCritiqueRequest(
            screenshot_png=b"png",
            rubric_version="v1",
            candidate_ref="screen",
            viewport_width=1,
            viewport_height=1,
            deterministic_evidence={},
        )
    )
    assert leases.calls == [(lease_id, CAPABILITY_VISUAL_CRITIQUE)]
    assert critic.calls == 1


def test_render_binding_replaces_only_url_and_preserves_oracle_input() -> None:
    spec = CheckSpec(
        outcome_id=uuid4(),
        statement="render candidate",
        kind="silhouette",
        ref="screens/x:silhouette",
        command=["file:///accepted.html", "Expected text"],
    )
    rebound = _render_bound_spec(spec, "file:///candidate.html")
    assert rebound.command == ["file:///candidate.html", "Expected text"]
    assert spec.command == ["file:///accepted.html", "Expected text"]
    assert rebound.outcome_id == spec.outcome_id
    assert rebound.ref == spec.ref


class _LeaseRepo:
    def __init__(self, lease: object) -> None:
        self.lease = lease

    async def get_by_id(self, connection: object, lease_id: object) -> object:
        del connection, lease_id
        return self.lease


class _Uow:
    connection = object()


@pytest.mark.asyncio
async def test_non_worker_checkout_refuses_worker_bound_lease() -> None:
    from datetime import UTC, datetime, timedelta

    from engine.capabilities.lease_service import CapabilityLeaseService
    from engine.contracts.capability_lease import CapabilityLease
    from engine.core.errors import DdeError

    now = datetime.now(UTC)
    lease = CapabilityLease(
        lease_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        task_id=uuid4(),
        execution_plan_id=uuid4(),
        worker_run_id=uuid4(),
        environment_id=None,
        capability_id=CAPABILITY_BROWSER,
        capability_version="1",
        resource_scope={},
        operation_scope="verify",
        constraints={},
        issued_by_policy_version="test",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        revocable=True,
        status="ACTIVE",
        lease_hash="hash",
        requested_by="test",
        created_at=now,
        updated_at=now,
    )
    service = CapabilityLeaseService(
        None,  # type: ignore[arg-type]
        repository=_LeaseRepo(lease),  # type: ignore[arg-type]
    )
    with pytest.raises(DdeError) as exc:
        await service.require_active_lease(
            tenant_id=lease.tenant_id,
            project_id=lease.project_id,
            lease_id=lease.lease_id,
            capability_id=CAPABILITY_BROWSER,
            uow=_Uow(),  # type: ignore[arg-type]
        )
    assert exc.value.error_code == "POLICY_DENIED"
    assert "kill flags" in str(exc.value)
