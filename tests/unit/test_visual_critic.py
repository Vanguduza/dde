"""DDE-068 visual critic, OpenRouter adapter, and broker boundary proofs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from adapters.openrouter.visual_critic import OpenRouterVisualCritic
from engine.capabilities.broker.http import (
    BrokeredJsonHttpService,
    BrokeredJsonResponse,
)
from engine.capabilities.browser import (
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserLayoutResult,
    BrowserLayoutSpec,
    BrowserProbeResult,
    BrowserProbeSpec,
)
from engine.capabilities.visual_critic import (
    VisualCriticDimensionResult,
    VisualCriticResult,
    VisualCriticRubricItem,
    VisualCriticSpec,
)
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.verification.checks import CheckSpec, run_check
from engine.verification.visual_critic import load_visual_critic_rubric

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


class _Browser:
    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        del spec
        return BrowserProbeResult(0, "", "", 1, False)

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        del spec
        return BrowserCaptureResult(0, _PNG, "", 2, False)

    async def layout(self, spec: BrowserLayoutSpec) -> BrowserLayoutResult:
        del spec
        return BrowserLayoutResult(0, (), "", 0, 0, 1, False)


class _Critic:
    def __init__(self, score: float, verdict: str = "PASS") -> None:
        self.score = score
        self.verdict = verdict
        self.calls: list[VisualCriticSpec] = []

    async def critique(self, spec: VisualCriticSpec) -> VisualCriticResult:
        self.calls.append(spec)
        dimensions = tuple(
            VisualCriticDimensionResult(item.rubric_id, self.score, "visible evidence")
            for item in spec.rubric
        )
        return VisualCriticResult(
            exit_code=0 if self.verdict == "PASS" else 1,
            verdict=self.verdict,
            score=self.score,
            dimensions=dimensions,
            findings=() if self.verdict == "PASS" else ("tighten hierarchy",),
            model_id=spec.model_id,
            provider_id="test-provider",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            duration_ms=3,
            timed_out=False,
        )


def _workspace(tmp_path: Path) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        workspace_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        task_id=uuid7(),
        execution_environment_id=uuid7(),
        base_revision="HEAD",
        current_revision="HEAD",
        workspace_path=str(tmp_path),
        policy={},
        status="READY",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _visual_spec(tmp_path: Path) -> None:
    visual = tmp_path / "visual"
    visual.mkdir(parents=True)
    (visual / "screen.json").write_text(
        json.dumps(
            {
                "url": "https://example.invalid/",
                "golden_path": "visual/golden.png",
                "quality_gate": False,
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_judge_passes_only_when_dde_weighted_score_clears_threshold(
    tmp_path: Path,
) -> None:
    _visual_spec(tmp_path)
    critic = _Critic(4.5, "PASS")
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="screen is professionally polished",
            kind="judge",
            ref="judge:screen",
            command=["visual/screen.json"],
        ),
        browser=_Browser(),
        visual_critic=critic,
    )
    assert result.status == "PASSED"
    payload = json.loads(result.stdout)
    assert payload["rubric_version"] == "visual-critic-v1"
    assert payload["dde_weighted_score"] == 4.5
    assert payload["cost_usd"] == 0.001
    assert Path(tmp_path / payload["screenshot_path"]).is_file()
    assert critic.calls[0].max_cost_usd == 0.05


@pytest.mark.asyncio
async def test_judge_dde_threshold_can_fail_provider_pass(tmp_path: Path) -> None:
    _visual_spec(tmp_path)
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="screen is professionally polished",
            kind="judge",
            ref="judge:screen",
            command=["visual/screen.json"],
        ),
        browser=_Browser(),
        visual_critic=_Critic(3.9, "PASS"),
    )
    assert result.status == "FAILED"
    payload = json.loads(result.stdout)
    assert payload["provider_verdict"] == "PASS"
    assert payload["dde_weighted_score"] == 3.9


@pytest.mark.asyncio
async def test_judge_fails_closed_without_critic(tmp_path: Path) -> None:
    _visual_spec(tmp_path)
    with pytest.raises(DdeError) as exc:
        await run_check(
            workspaces=None,  # type: ignore[arg-type]
            workspace=_workspace(tmp_path),
            spec=CheckSpec(
                outcome_id=uuid7(),
                statement="screen is polished",
                kind="judge",
                ref="judge:screen",
                command=["visual/screen.json"],
            ),
            browser=_Browser(),
        )
    assert exc.value.error_code == "POLICY_DENIED"


class _Broker:
    def __init__(self, response: BrokeredJsonResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def post_json(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return self.response


def _adapter_spec(max_cost_usd: float = 0.05) -> VisualCriticSpec:
    item = VisualCriticRubricItem("hierarchy", "Hierarchy", "Judge hierarchy", 1.0)
    return VisualCriticSpec(
        tenant_id=uuid7(),
        project_id=uuid7(),
        png_bytes=_PNG,
        statement="professional hierarchy",
        rubric_version="test-v1",
        rubric=(item,),
        context={"surface": "orders"},
        model_id="z-ai/glm-5.3-flash",
        max_cost_usd=max_cost_usd,
    )


def _openrouter_body(*, cost: float = 0.001, model: str = "z-ai/glm-5.3-flash"):
    content = json.dumps(
        {
            "verdict": "PASS",
            "score": 4.5,
            "dimensions": [
                {
                    "rubric_id": "hierarchy",
                    "score": 4.5,
                    "finding": "clear primary action",
                }
            ],
            "findings": [],
        }
    )
    return {
        "model": model,
        "provider": "test-upstream",
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost": cost,
        },
    }


@pytest.mark.asyncio
async def test_openrouter_critic_requests_structured_private_pinned_call() -> None:
    broker = _Broker(BrokeredJsonResponse(200, _openrouter_body(), 10))
    result = await OpenRouterVisualCritic(broker).critique(_adapter_spec())
    assert result.verdict == "PASS"
    call = broker.calls[0]
    body = call["body"]
    assert isinstance(body, dict)
    assert body["model"] == "z-ai/glm-5.3-flash"
    assert body["usage"] == {"include": True}
    provider = body["provider"]
    assert isinstance(provider, dict)
    assert provider["data_collection"] == "deny"
    assert provider["zdr"] is True
    assert provider["allow_fallbacks"] is False
    assert provider["require_parameters"] is True
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"


@pytest.mark.asyncio
async def test_openrouter_critic_refuses_model_substitution() -> None:
    broker = _Broker(
        BrokeredJsonResponse(200, _openrouter_body(model="other/model"), 10)
    )
    result = await OpenRouterVisualCritic(broker).critique(_adapter_spec())
    assert result.exit_code < 0
    assert "different from the pinned critic" in result.stderr


@pytest.mark.asyncio
async def test_openrouter_critic_enforces_actual_per_cycle_cost() -> None:
    broker = _Broker(BrokeredJsonResponse(200, _openrouter_body(cost=0.051), 10))
    with pytest.raises(DdeError) as exc:
        await OpenRouterVisualCritic(broker).critique(_adapter_spec())
    assert exc.value.error_code == "BUDGET_EXCEEDED"


class _Capture:
    def __init__(self) -> None:
        self.reads = 0

    async def resolve_secret(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        self.reads += 1
        return "super-secret-value"


@pytest.mark.asyncio
async def test_broker_refuses_unallowlisted_destination_before_secret_read() -> None:
    capture = _Capture()
    service = BrokeredJsonHttpService(
        None,  # type: ignore[arg-type]
        allowed_hosts=frozenset({"openrouter.ai"}),
        captures=capture,  # type: ignore[arg-type]
    )
    with pytest.raises(DdeError) as exc:
        await service.post_json(
            tenant_id=uuid7(),
            project_id=uuid7(),
            provider_id="openrouter_api_key",
            url="https://example.com/v1/chat",
            body={},
        )
    assert exc.value.error_code == "POLICY_DENIED"
    assert capture.reads == 0


@pytest.mark.asyncio
async def test_broker_refuses_caller_authorization_header() -> None:
    capture = _Capture()
    service = BrokeredJsonHttpService(
        None,  # type: ignore[arg-type]
        allowed_hosts=frozenset({"openrouter.ai"}),
        captures=capture,  # type: ignore[arg-type]
    )
    with pytest.raises(DdeError) as exc:
        await service.post_json(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            provider_id="openrouter_api_key",
            url="https://openrouter.ai/api/v1/chat/completions",
            body={},
            headers={"Authorization": "attacker-value"},
        )
    assert exc.value.error_code == "POLICY_DENIED"
    assert capture.reads == 1


def test_committed_visual_critic_rubric_is_complete_and_stable() -> None:
    rubric = load_visual_critic_rubric()
    assert rubric.version == "visual-critic-v1"
    assert rubric.pass_threshold == 4.0
    assert len(rubric.items) == 10
    assert len(rubric.content_hash) == 64
