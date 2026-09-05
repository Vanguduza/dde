from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from engine.contracts.design_source_artifact import DesignSourceArtifact
from engine.studio.source.adapters import SourceQueryContext, TwentyFirstSourceAdapter
from engine.studio.source.compiler import evaluate_artifact
from engine.studio.source.scoring import REQUIRED_DIMENSIONS, score_candidate


def artifact(**updates: object) -> DesignSourceArtifact:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "artifact_id": uuid4(),
        "source_id": uuid4(),
        "search_run_id": None,
        "tenant_id": uuid4(),
        "project_id": uuid4(),
        "provider_artifact_key": "card-1",
        "artifact_kind": "COMPONENT",
        "title": "Card",
        "source_uri": "https://example.invalid/card",
        "version_ref": "v1",
        "content_hash": "a" * 64,
        "framework": "react",
        "supported_archetypes": ["marketplace"],
        "dependency_manifest": ["react"],
        "license_state": "OPEN_REUSE",
        "license_ids": ["MIT"],
        "security_state": "PASS",
        "accessibility_state": "PASS",
        "compatibility_state": "PASS",
        "retrieval_state": "FETCHED",
        "metadata": {"token_mapping_report": {"complete": True}},
        "created_at": now,
        "updated_at": now,
    }
    values.update(updates)
    return DesignSourceArtifact.model_validate(values)


def test_compiler_admits_evidence_complete_reusable_component() -> None:
    decision = evaluate_artifact(artifact(), project_frameworks=("react",))
    assert decision.state == "ADMITTED"
    assert decision.hard_failures == ()
    assert decision.design_system_state == "PASS"


def test_compiler_rejects_hidden_remote_runtime_dependency() -> None:
    decision = evaluate_artifact(
        artifact(dependency_manifest=["https://cdn.example.invalid/runtime.js"]),
        project_frameworks=("react",),
    )
    assert decision.state == "REJECTED"
    assert decision.dependency_state == "FAIL"
    assert decision.hard_failures == (
        "HIDDEN_REMOTE_RUNTIME:https://cdn.example.invalid/runtime.js",
    )


def test_reference_only_donor_is_admitted_only_as_reference_context() -> None:
    decision = evaluate_artifact(
        artifact(
            artifact_kind="DIRECTIVE",
            framework=None,
            license_state="REFERENCE_ONLY",
            accessibility_state="UNKNOWN",
            compatibility_state="UNKNOWN",
            metadata={},
        )
    )
    assert decision.state == "ADMITTED"
    assert "REFERENCE_ONLY_NO_CODE_REUSE" in decision.validation_obligations
    assert decision.hard_failures == ()


def test_unknown_external_code_does_not_become_usable() -> None:
    decision = evaluate_artifact(
        artifact(
            license_state="UNKNOWN",
            security_state="UNKNOWN",
            accessibility_state="UNKNOWN",
            compatibility_state="UNKNOWN",
            framework=None,
            metadata={},
        )
    )
    assert decision.state == "REJECTED"
    assert "LICENSE_UNKNOWN" in decision.hard_failures
    assert "SECURITY_NOT_EVALUATED" in decision.hard_failures
    assert "ACCESSIBILITY_INCOMPLETE" in decision.hard_failures


def test_candidate_score_is_unscored_until_every_dimension_has_evidence() -> None:
    result = score_candidate(
        {"product_fit": {"score": 90, "evidence_refs": ["audit:1"]}}
    )
    assert result.score_state == "UNSCORED"
    assert result.overall_score is None
    missing = result.dimensions["missing_dimensions"]
    assert isinstance(missing, list)
    assert "feature_coverage" in missing


def test_candidate_score_hard_failure_dominates_numbers() -> None:
    dimensions = {
        name: {"score": 100, "evidence_refs": [f"evidence:{name}"]}
        for name in REQUIRED_DIMENSIONS
    }
    result = score_candidate(dimensions, hard_failures=("LICENSE_REJECTED",))
    assert result.score_state == "BLOCKED"
    assert result.classification == "BLOCKED"
    assert result.overall_score is None


def test_candidate_score_is_good_only_with_complete_evidence() -> None:
    dimensions = {
        name: {"score": 90, "evidence_refs": [f"evidence:{name}"]}
        for name in REQUIRED_DIMENSIONS
    }
    result = score_candidate(dimensions)
    assert result.score_state == "SCORED"
    assert result.overall_score == 90
    assert result.classification == "GOOD"
    assert len(result.evidence_refs) == len(REQUIRED_DIMENSIONS)


@pytest.mark.asyncio
async def test_twenty_first_has_no_uncontrolled_network_fallback() -> None:
    adapter = TwentyFirstSourceAdapter()
    context = SourceQueryContext(uuid4(), uuid4())
    health = await adapter.health(context)
    assert health.status == "NOT_CONFIGURED"
    assert "transport is not configured" in (health.detail or "")
    assert await adapter.search(context, "checkout") == ()
    assert await adapter.inspect(context, "candidate") is None
    assert await adapter.fetch(context, "candidate") is None


class _FakeInterop:
    def __init__(self, endpoint: Any | None = None) -> None:
        self.endpoint = endpoint
        self.registered: list[dict[str, object]] = []

    async def list_endpoints(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[Any, ...]:
        del tenant_id, project_id
        return (self.endpoint,) if self.endpoint is not None else ()

    async def register_external(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        harness_id: str,
        protocol: str,
        executable_or_uri: str,
        discovered_capabilities: dict[str, object] | None = None,
    ) -> Any:
        from engine.contracts.agent_interop_endpoint import AgentInteropEndpoint
        from engine.core.ids import uuid7

        kwargs: dict[str, object] = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "harness_id": harness_id,
            "protocol": protocol,
            "executable_or_uri": executable_or_uri,
            "discovered_capabilities": discovered_capabilities or {},
        }
        self.registered.append(kwargs)
        now = datetime.now(UTC)
        self.endpoint = AgentInteropEndpoint(
            endpoint_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            harness_id=harness_id,
            protocol=protocol,
            executable_or_uri=executable_or_uri,
            installation_version=None,
            discovery_state="DISCOVERED",
            certification_state="DISCOVERED",
            discovered_capabilities=dict(discovered_capabilities or {}),
            certified_capabilities={},
            certification_refs=[],
            health_state="UNKNOWN",
            config_hash=None,
            last_probe_at=None,
            last_error=None,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        return self.endpoint


@pytest.mark.asyncio
async def test_twenty_first_transport_registers_discovered_but_does_not_call_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.studio.source.twentyfirst import TwentyFirstMcpTransport

    monkeypatch.delenv("API_KEY_21ST", raising=False)
    interop = _FakeInterop()
    from engine.fabric.interop import AgentInteropService

    transport = TwentyFirstMcpTransport(
        None,  # type: ignore[arg-type]
        interop=cast(AgentInteropService, interop),
    )
    context = SourceQueryContext(uuid4(), uuid4())
    health = await transport.health(context)
    assert health.status == "NOT_CONFIGURED"
    assert "not certified" in (health.detail or "")
    assert len(interop.registered) == 1
    assert interop.registered[0]["protocol"] == "MCP"
    with pytest.raises(Exception) as exc_info:
        await transport.search(context, "checkout")
    assert "not certified" in str(exc_info.value)


@pytest.mark.asyncio
async def test_twenty_first_transport_uses_certified_mcp_without_persisting_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from engine.contracts.agent_interop_endpoint import AgentInteropEndpoint
    from engine.core.ids import uuid7
    from engine.studio.source.twentyfirst import (
        TWENTY_FIRST_MCP_URL,
        TwentyFirstMcpTransport,
    )

    tenant_id, project_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    endpoint = AgentInteropEndpoint(
        endpoint_id=uuid7(),
        tenant_id=tenant_id,
        project_id=project_id,
        harness_id="21st",
        protocol="MCP",
        executable_or_uri=TWENTY_FIRST_MCP_URL,
        installation_version=None,
        discovery_state="DISCOVERED",
        certification_state="CERTIFIED",
        discovered_capabilities={
            "mcp": True,
            "source_search": True,
            "source_fetch": True,
        },
        certified_capabilities={
            "mcp": True,
            "source_search": True,
            "source_fetch": True,
        },
        certification_refs=["contract:test-21st-mcp"],
        health_state="HEALTHY",
        config_hash="cfg",
        last_probe_at=now,
        last_error=None,
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    interop = _FakeInterop(endpoint)
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        body = __import__("json").loads(request.content)
        method = body["method"]
        if method == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "session-1"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"protocolVersion": "2025-06-18"},
                },
            )
        if method == "tools/list":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {
                                "name": "search_components",
                                "inputSchema": {
                                    "properties": {"query": {"type": "string"}}
                                },
                            },
                            {
                                "name": "get_component",
                                "inputSchema": {
                                    "properties": {"component_id": {"type": "string"}}
                                },
                            },
                        ]
                    },
                },
            )
        assert method == "tools/call"
        tool = body["params"]["name"]
        if tool == "search_components":
            result: dict[str, object] = {
                "components": [
                    {
                        "id": "hero-1",
                        "name": "Hero",
                        "license": "MIT",
                        "framework": "react",
                    }
                ]
            }
        else:
            result = {
                "component": {
                    "id": "hero-1",
                    "name": "Hero",
                    "license": "MIT",
                    "framework": "react",
                    "code": "export function Hero(){ return null }",
                }
            }
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 3, "result": {"structuredContent": result}},
        )

    from engine.fabric.interop import AgentInteropService

    mock = httpx.MockTransport(handler)
    monkeypatch.setenv("API_KEY_21ST", "secret-21st-key")
    transport = TwentyFirstMcpTransport(
        None,  # type: ignore[arg-type]
        interop=cast(AgentInteropService, interop),
        client_factory=lambda: httpx.AsyncClient(transport=mock),
    )
    context = SourceQueryContext(tenant_id, project_id)
    health = await transport.health(context)
    assert health.status == "AVAILABLE"
    rows = await transport.search(context, "hero")
    assert rows[0].provider_artifact_key == "hero-1"
    assert rows[0].license_state == "OPEN_REUSE"
    fetched = await transport.fetch(context, "hero-1")
    assert fetched is not None and fetched.content is not None
    assert fetched.candidate.content_hash is not None
    assert all(
        headers.get("x-api-key") == "secret-21st-key" for headers in seen_headers
    )
    dumped = repr(rows) + repr(fetched)
    assert "secret-21st-key" not in dumped


def test_dde_library_catalog_hashes_match_repository_bytes() -> None:
    import hashlib

    from engine.studio.source.adapters import DdeLibrarySourceAdapter

    adapter = DdeLibrarySourceAdapter()
    rows = adapter._rows()  # noqa: SLF001 - contract test of versioned local catalog
    assert rows, "DDE library must contain at least one governed reusable asset"
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    repo = root.parent
    for row in rows:
        source_path = row.get("source_path")
        expected = row.get("content_hash")
        assert isinstance(source_path, str) and source_path
        assert isinstance(expected, str) and len(expected) == 64
        payload = (repo / source_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected
        assert row.get("evidence_refs")


@pytest.mark.asyncio
async def test_dde_library_exposes_real_foundation_and_fetches_exact_bytes() -> None:
    from engine.studio.source.adapters import DdeLibrarySourceAdapter

    adapter = DdeLibrarySourceAdapter()
    context = SourceQueryContext(uuid4(), uuid4())
    health = await adapter.health(context)
    assert health.status == "AVAILABLE"
    rows = await adapter.search(context, "marketplace")
    foundation = next(row for row in rows if row.artifact_kind == "FOUNDATION")
    assert foundation.provider_artifact_key == "dde.foundation.marketplace.v1"
    assert foundation.license_state == "OPEN_REUSE"
    fetched = await adapter.fetch(context, foundation.provider_artifact_key)
    assert fetched is not None and fetched.content is not None
    import hashlib

    assert hashlib.sha256(fetched.content).hexdigest() == foundation.content_hash


def _source(*, source_class: str) -> Any:
    from engine.contracts.design_source import DesignSource

    now = datetime.now(UTC)
    return DesignSource.model_validate(
        {
            "source_id": uuid4(),
            "tenant_id": uuid4(),
            "project_id": uuid4(),
            "provider_key": "provider",
            "display_name": "Provider",
            "source_class": source_class,
            "adapter_kind": "test",
            "priority": 1,
            "status": "AVAILABLE",
            "health_detail": None,
            "capabilities": ["search", "inspect"],
            "config": {},
            "item_count": 1,
            "last_checked_at": now,
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )


def _admission(item: DesignSourceArtifact, *, state: str = "ADMITTED") -> Any:
    from engine.contracts.design_source_admission import DesignSourceAdmission

    now = datetime.now(UTC)
    return DesignSourceAdmission.model_validate(
        {
            "admission_id": uuid4(),
            "artifact_id": item.artifact_id,
            "tenant_id": item.tenant_id,
            "project_id": item.project_id,
            "content_hash": item.content_hash,
            "compiler_version": "m8.compiler.v1",
            "framework_state": "PASS",
            "license_state": "PASS",
            "dependency_state": "PASS",
            "security_state": "PASS",
            "accessibility_state": "PASS",
            "design_system_state": "PASS",
            "token_mapping_report": {"complete": True},
            "unsupported_behaviors": [],
            "hard_failures": [],
            "validation_obligations": [],
            "state": state,
            "created_at": now,
            "updated_at": now,
        }
    )


def test_project_native_reuse_does_not_invent_external_admission() -> None:
    from engine.studio.source.provenance import evaluate_reusable_provenance

    item = artifact()
    decision = evaluate_reusable_provenance(
        artifact=item,
        source=_source(source_class="PROJECT_NATIVE"),
        admission=None,
        usage_kind="REUSED",
        subject_kind="CANDIDATE",
        subject_ref=str(uuid4()),
        recorded_admission_id=None,
    )
    assert decision.allowed
    assert "project-native" in decision.detail


def test_external_reuse_requires_candidate_bound_current_sandbox_validation() -> None:
    from engine.studio.source.provenance import evaluate_reusable_provenance

    candidate_id = uuid4()
    item = artifact(
        metadata={
            "token_mapping_report": {"complete": True},
            "sandbox_validation": {
                "state": "CURRENT_BYTES_VALIDATED",
                "candidate_id": str(candidate_id),
                "content_hash": "a" * 64,
            },
        }
    )
    admission = _admission(item)
    good = evaluate_reusable_provenance(
        artifact=item,
        source=_source(source_class="EXTERNAL_REGISTRY"),
        admission=admission,
        usage_kind="ADAPTED",
        subject_kind="CANDIDATE",
        subject_ref=str(candidate_id),
        recorded_admission_id=admission.admission_id,
    )
    assert good.allowed

    wrong_candidate = evaluate_reusable_provenance(
        artifact=item,
        source=_source(source_class="EXTERNAL_REGISTRY"),
        admission=admission,
        usage_kind="ADAPTED",
        subject_kind="CANDIDATE",
        subject_ref=str(uuid4()),
        recorded_admission_id=admission.admission_id,
    )
    assert not wrong_candidate.allowed
    assert "another candidate" in wrong_candidate.detail


def test_reuse_rejects_stale_recorded_admission_identity() -> None:
    from engine.studio.source.provenance import evaluate_reusable_provenance

    item = artifact()
    admission = _admission(item)
    decision = evaluate_reusable_provenance(
        artifact=item,
        source=_source(source_class="DDE_LIBRARY"),
        admission=admission,
        usage_kind="REUSED",
        subject_kind="CANDIDATE",
        subject_ref=str(uuid4()),
        recorded_admission_id=uuid4(),
    )
    assert not decision.allowed
    assert "stale" in decision.detail


@pytest.mark.asyncio
async def test_twenty_first_requires_exact_certified_source_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.contracts.agent_interop_endpoint import AgentInteropEndpoint
    from engine.core.ids import uuid7
    from engine.fabric.interop import AgentInteropService
    from engine.studio.source.twentyfirst import (
        TWENTY_FIRST_MCP_URL,
        TwentyFirstMcpTransport,
    )

    tenant_id, project_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    endpoint = AgentInteropEndpoint(
        endpoint_id=uuid7(),
        tenant_id=tenant_id,
        project_id=project_id,
        harness_id="21st",
        protocol="MCP",
        executable_or_uri=TWENTY_FIRST_MCP_URL,
        installation_version=None,
        discovery_state="DISCOVERED",
        certification_state="CERTIFIED",
        discovered_capabilities={"mcp": True, "source_search": True},
        certified_capabilities={"mcp": True, "source_search": False},
        certification_refs=["contract:no-search"],
        health_state="HEALTHY",
        config_hash="cfg",
        last_probe_at=now,
        last_error=None,
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setenv("API_KEY_21ST", "should-not-be-used")
    transport = TwentyFirstMcpTransport(
        None,  # type: ignore[arg-type]
        interop=cast(AgentInteropService, _FakeInterop(endpoint)),
    )
    with pytest.raises(Exception) as exc_info:
        await transport.search(SourceQueryContext(tenant_id, project_id), "hero")
    assert "not certified for source_search" in str(exc_info.value)


def test_target_blend_is_normalized_without_rewriting_provenance() -> None:
    from engine.studio.source.blend import normalize_target_blend

    result = normalize_target_blend(
        {"donors": 0.25, "project-native": 0.75},
        known_provider_keys=frozenset({"project-native", "donors", "21st"}),
    )
    assert result == {"donors": 0.25, "project-native": 0.75}


def test_target_blend_rejects_unknown_provider_and_invalid_total() -> None:
    from engine.core.errors import DdeError
    from engine.studio.source.blend import normalize_target_blend

    with pytest.raises(DdeError, match="unknown providers"):
        normalize_target_blend(
            {"mystery": 1.0}, known_provider_keys=frozenset({"project-native"})
        )
    with pytest.raises(DdeError, match="sum to 1.0"):
        normalize_target_blend(
            {"project-native": 0.5}, known_provider_keys=frozenset({"project-native"})
        )
