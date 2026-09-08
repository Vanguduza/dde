"""DDE bridge to the localhost Hermes xKiro Auxiliary Intelligence Fabric.

HAIF is deliberately outside DDE's manager/routing authority.  DDE submits only
non-authoritative target-application evidence tasks to the local tenant daemon,
then may attach completed evidence to an AiResearchArtifact.  No API key enters
DDE Core and no HAIF result becomes a command, plan approval, truth mutation or
manager selection by this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import stat
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from engine.contracts.ai_research_artifact import AiResearchArtifact
from engine.core.errors import DdeError

HaifArchetype = Literal[
    "EXTRACT_STRUCTURED_FACTS",
    "CLASSIFY",
    "SUMMARIZE_BOUNDED",
    "LONG_CONTEXT_SYNTHESIS",
    "CONTRADICTION_DETECTION",
    "COMPARE_SOURCES",
    "CRITIQUE_PLAN",
    "CLUSTER_LOGS",
    "ROOT_CAUSE_HYPOTHESIS",
    "CONTEXT_COMPRESSION",
    "MEMORY_CONSOLIDATION",
    "VISUAL_HEURISTIC_CRITIQUE",
    "RESEARCH_PREPROCESS",
    "VEKL_EXTRACT",
    "VEKL_SYNTHESIS",
    "TRUTH_DOC_DRIFT_CANDIDATE",
    "ARCHITECTURE_COMPARE",
    "CI_EVIDENCE_CLUSTER",
    "SOURCE_INTELLIGENCE",
]


class HaifTaskRequest(BaseModel):
    """One DDE auxiliary request; project identity is pinned by the daemon."""

    model_config = ConfigDict(extra="forbid")

    scope_kind: Literal["TARGET_APPLICATION"] = "TARGET_APPLICATION"
    task_archetype: HaifArchetype
    purpose: str = Field(min_length=1, max_length=4000)
    evidence: dict[str, object]
    evidence_refs: list[str] = Field(default_factory=list)
    data_class: Literal["PUBLIC"] = "PUBLIC"
    risk: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    diversity: Literal["S1", "S2", "S3"] = "S1"
    max_input_tokens: int = Field(default=120_000, ge=1, le=1_000_000)
    max_output_tokens: int = Field(default=8_000, ge=1, le=65_536)
    deadline_class: Literal["DEFERRABLE", "INTERACTIVE"] = "DEFERRABLE"
    max_attempts: int = Field(default=2, ge=1, le=4)
    cacheable: bool = True
    priority: Literal["NORMAL", "PRIORITY"] = "NORMAL"

    def daemon_payload(self) -> dict[str, object]:
        payload = self.model_dump(exclude={"scope_kind"}, mode="json")
        payload["taskArchetype"] = payload.pop("task_archetype")
        payload["evidenceRefs"] = payload.pop("evidence_refs")
        payload["dataClass"] = payload.pop("data_class")
        payload["maxInputTokens"] = payload.pop("max_input_tokens")
        payload["maxOutputTokens"] = payload.pop("max_output_tokens")
        payload["deadlineClass"] = payload.pop("deadline_class")
        payload["maxAttempts"] = payload.pop("max_attempts")
        return cast(dict[str, object], payload)


class HaifSubmission(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str
    state: str
    reused: bool = False
    authority: str | None = None


class HaifTaskProjection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str
    project: Literal["dde"]
    task_archetype: str
    state: str
    authority: str
    evidence: dict[str, object] | None = None
    failure_reason: str | None = None
    finished_at: str | None = None


class ResearchSourceSink(Protocol):
    async def add_source(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        research_id: UUID,
        source_kind: str,
        ref: str,
        authority: str,
        lock_version: int,
        title: str | None = None,
        published_at: object | None = None,
        content_hash: str | None = None,
        notes: str | None = None,
    ) -> AiResearchArtifact: ...


class HaifAuxiliaryClient:
    """Loopback-only DDE client for the project-scoped HAIF tenant daemon."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:9142",
        token_file: Path = Path.home() / ".dde-control/secrets/haif-control.token",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise DdeError(
                "POLICY_DENIED",
                "DDE HAIF endpoint must be loopback-only",
                details={"hostname": parsed.hostname or ""},
            )
        self.base_url = base_url.rstrip("/")
        self.token_file = token_file
        self.transport = transport

    def _token(self) -> str:
        try:
            mode = stat.S_IMODE(self.token_file.stat().st_mode)
            if mode & 0o077:
                raise DdeError(
                    "POLICY_DENIED",
                    "DDE HAIF control token permissions must be 0600",
                )
            token = self.token_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "DDE HAIF control token is not installed",
            ) from exc
        if len(token) < 16:
            raise DdeError("CAPABILITY_UNAVAILABLE", "DDE HAIF control token is invalid")
        return token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        headers = {"authorization": f"Bearer {self._token()}"}
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                transport=self.transport,
                timeout=30.0,
                headers=headers,
            ) as client:
                response = await client.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "DDE HAIF localhost transport failed",
                retryable=True,
            ) from exc
        if response.status_code >= 400:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "DDE HAIF tenant rejected the request",
                retryable=response.status_code >= 500,
                details={"status_code": response.status_code},
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise DdeError("INVARIANT_VIOLATION", "DDE HAIF response must be an object")
        return cast(dict[str, object], payload)

    async def status(self) -> dict[str, object]:
        return await self._request("GET", "/v1/status")

    async def submit(self, request: HaifTaskRequest) -> HaifSubmission:
        return HaifSubmission.model_validate(
            await self._request("POST", "/v1/tasks", body=request.daemon_payload())
        )

    async def task(self, task_id: str) -> HaifTaskProjection:
        return HaifTaskProjection.model_validate(
            await self._request("GET", f"/v1/tasks/{task_id}")
        )

    async def run_once(self) -> dict[str, object]:
        return await self._request("POST", "/v1/run-once", body={})

    async def wait(
        self,
        task_id: str,
        *,
        timeout_seconds: float = 60.0,
        poll_interval_seconds: float = 0.5,
    ) -> HaifTaskProjection:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            projection = await self.task(task_id)
            if projection.state in {"COMPLETED", "FAILED", "PARKED"}:
                return projection
            if asyncio.get_running_loop().time() >= deadline:
                raise DdeError(
                    "CAPABILITY_UNAVAILABLE",
                    "DDE HAIF task did not finish before the caller deadline",
                    retryable=True,
                    details={"task_id": task_id},
                )
            await asyncio.sleep(poll_interval_seconds)


class HaifResearchBridge:
    """Attach verified HAIF evidence to research without granting command authority."""

    def __init__(self, client: HaifAuxiliaryClient, sink: ResearchSourceSink) -> None:
        self.client = client
        self.sink = sink

    async def submit_and_attach(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        research_id: UUID,
        lock_version: int,
        request: HaifTaskRequest,
        drive_once: bool = False,
    ) -> tuple[AiResearchArtifact, HaifTaskProjection]:
        submission = await self.client.submit(request)
        if drive_once:
            await self.client.run_once()
        projection = await self.client.wait(submission.task_id)
        if projection.state != "COMPLETED" or projection.evidence is None:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "DDE HAIF task did not produce attachable evidence",
                details={
                    "task_id": projection.task_id,
                    "state": projection.state,
                    "failure_reason": projection.failure_reason or "",
                },
            )
        evidence = projection.evidence
        if evidence.get("authority") != "NON_AUTHORITATIVE_AUXILIARY_EVIDENCE":
            raise DdeError("INVARIANT_VIOLATION", "DDE HAIF evidence authority is invalid")
        if evidence.get("project") != "dde":
            raise DdeError("TENANT_SCOPE_VIOLATION", "DDE HAIF evidence project is invalid")
        if evidence.get("direct_premium_invocation") is not False:
            raise DdeError(
                "INVARIANT_VIOLATION",
                "DDE HAIF evidence crossed the premium-runtime boundary",
            )
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str)
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        artifact = await self.sink.add_source(
            tenant_id=tenant_id,
            project_id=project_id,
            research_id=research_id,
            source_kind="HAIF_AUXILIARY",
            ref=f"haif://dde/{projection.task_id}",
            authority="NON_AUTHORITATIVE_AUXILIARY_EVIDENCE",
            lock_version=lock_version,
            title=f"HAIF {projection.task_archetype} evidence",
            content_hash=content_hash,
            notes="Auxiliary evidence only; no command, approval, truth, routing or completion authority.",
        )
        return artifact, projection
