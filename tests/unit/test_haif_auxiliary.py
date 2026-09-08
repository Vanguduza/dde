from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
import pytest

from engine.contracts.ai_research_artifact import AiResearchArtifact
from engine.core.errors import DdeError
from engine.fabric.haif import (
    HaifAuxiliaryClient,
    HaifResearchBridge,
    HaifTaskRequest,
)


def _token(tmp_path: Path) -> Path:
    path = tmp_path / "haif-control.token"
    path.write_text("local-haif-token-value-123456\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def test_client_refuses_non_loopback_endpoint(tmp_path: Path) -> None:
    with pytest.raises(DdeError, match="loopback-only"):
        HaifAuxiliaryClient(
            base_url="https://api.xkiro.com/v1",
            token_file=_token(tmp_path),
        )


def test_client_refuses_loose_token_permissions(tmp_path: Path) -> None:
    token = _token(tmp_path)
    token.chmod(0o644)
    client = HaifAuxiliaryClient(token_file=token)
    with pytest.raises(DdeError, match="0600"):
        client._token()


@pytest.mark.asyncio
async def test_submit_is_dde_scoped_public_and_non_authoritative(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            202,
            json={
                "task_id": "11111111-1111-1111-1111-111111111111",
                "state": "QUEUED",
                "reused": False,
                "authority": "NON_AUTHORITATIVE_AUXILIARY",
            },
        )

    client = HaifAuxiliaryClient(
        token_file=_token(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    request = HaifTaskRequest(
        task_archetype="VEKL_SYNTHESIS",
        purpose="Summarize admitted target-application evidence.",
        evidence={"source_id": "s1", "text": "public evidence"},
        evidence_refs=["s1"],
    )
    submission = await client.submit(request)
    assert submission.authority == "NON_AUTHORITATIVE_AUXILIARY"
    body = cast(dict[str, object], seen["body"])
    assert body["dataClass"] == "PUBLIC"
    assert body["taskArchetype"] == "VEKL_SYNTHESIS"
    assert "project" not in body
    assert "scope_kind" not in body
    assert seen["authorization"] == "Bearer local-haif-token-value-123456"


@pytest.mark.asyncio
async def test_task_projection_never_requires_raw_provider_credentials(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith("/v1/tasks/")
        return httpx.Response(
            200,
            json={
                "task_id": "11111111-1111-1111-1111-111111111111",
                "project": "dde",
                "task_archetype": "VEKL_SYNTHESIS",
                "state": "COMPLETED",
                "authority": "NON_AUTHORITATIVE_AUXILIARY",
                "evidence": {
                    "authority": "NON_AUTHORITATIVE_AUXILIARY_EVIDENCE",
                    "project": "dde",
                    "direct_premium_invocation": False,
                    "packets": [],
                },
            },
        )

    client = HaifAuxiliaryClient(
        token_file=_token(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    projection = await client.task("11111111-1111-1111-1111-111111111111")
    assert projection.project == "dde"
    assert projection.evidence is not None
    assert "api_key" not in json.dumps(projection.model_dump()).lower()


class _Sink:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def add_source(self, **kwargs: object) -> AiResearchArtifact:
        self.calls.append(kwargs)
        return cast(AiResearchArtifact, object())


@pytest.mark.asyncio
async def test_bridge_attaches_only_non_authoritative_dde_evidence(tmp_path: Path) -> None:
    task_id = "11111111-1111-1111-1111-111111111111"

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/tasks":
            return httpx.Response(202, json={"task_id": task_id, "state": "QUEUED"})
        if request.method == "GET" and request.url.path == f"/v1/tasks/{task_id}":
            return httpx.Response(
                200,
                json={
                    "task_id": task_id,
                    "project": "dde",
                    "task_archetype": "SOURCE_INTELLIGENCE",
                    "state": "COMPLETED",
                    "authority": "NON_AUTHORITATIVE_AUXILIARY",
                    "evidence": {
                        "authority": "NON_AUTHORITATIVE_AUXILIARY_EVIDENCE",
                        "project": "dde",
                        "direct_premium_invocation": False,
                        "packets": [],
                    },
                },
            )
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    client = HaifAuxiliaryClient(
        token_file=_token(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    sink = _Sink()
    bridge = HaifResearchBridge(client, sink)
    request = HaifTaskRequest(
        task_archetype="SOURCE_INTELLIGENCE",
        purpose="Compare public target-application source evidence.",
        evidence={"source_id": "s1", "text": "public"},
        evidence_refs=["s1"],
    )
    await bridge.submit_and_attach(
        tenant_id=uuid4(),
        project_id=uuid4(),
        research_id=uuid4(),
        lock_version=1,
        request=request,
    )
    assert len(sink.calls) == 1
    assert sink.calls[0]["source_kind"] == "HAIF_AUXILIARY"
    assert sink.calls[0]["authority"] == "NON_AUTHORITATIVE_AUXILIARY_EVIDENCE"
    assert str(sink.calls[0]["ref"]).startswith("haif://dde/")


@pytest.mark.asyncio
async def test_bridge_rejects_wrong_project_evidence(tmp_path: Path) -> None:
    task_id = "11111111-1111-1111-1111-111111111111"

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"task_id": task_id, "state": "QUEUED"})
        return httpx.Response(
            200,
            json={
                "task_id": task_id,
                "project": "dde",
                "task_archetype": "VEKL_SYNTHESIS",
                "state": "COMPLETED",
                "authority": "NON_AUTHORITATIVE_AUXILIARY",
                "evidence": {
                    "authority": "NON_AUTHORITATIVE_AUXILIARY_EVIDENCE",
                    "project": "dial",
                    "direct_premium_invocation": False,
                },
            },
        )

    client = HaifAuxiliaryClient(
        token_file=_token(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    bridge = HaifResearchBridge(client, _Sink())
    with pytest.raises(DdeError, match="project is invalid"):
        await bridge.submit_and_attach(
            tenant_id=uuid4(),
            project_id=uuid4(),
            research_id=uuid4(),
            lock_version=1,
            request=HaifTaskRequest(
                task_archetype="VEKL_SYNTHESIS",
                purpose="Public evidence",
                evidence={"source_id": "s1", "text": "public"},
            ),
        )
