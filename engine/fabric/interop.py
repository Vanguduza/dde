"""Agent interop discovery/certification and provider-capacity authority."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.agent_interop_endpoint import AgentInteropEndpoint
from engine.contracts.provider_capacity_snapshot import ProviderCapacitySnapshot
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import agent_interop_endpoints, provider_capacity_snapshots
from engine.truth.db import open_unit_of_work

PROBE_TIMEOUT_SECONDS = 12.0


@dataclass(frozen=True)
class ProbeResult:
    harness_id: str
    protocol: str
    executable: str
    version: str | None
    discovered_capabilities: dict[str, object]
    health_state: str
    error: str | None = None


class ProbeRunner(Protocol):
    async def __call__(self, argv: tuple[str, ...]) -> tuple[int, str, str]: ...


async def _run_probe(argv: tuple[str, ...]) -> tuple[int, str, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=PROBE_TIMEOUT_SECONDS
        )
    except (OSError, TimeoutError) as exc:
        return 127, "", str(exc)
    return (
        process.returncode or 0,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


def _contains(help_text: str, token: str) -> bool:
    return token.lower() in help_text.lower()


async def discover_local_harnesses(
    runner: ProbeRunner = _run_probe,
) -> tuple[ProbeResult, ...]:
    """Discover exact installed CLI features without touching provider credentials."""
    results: list[ProbeResult] = []
    for harness, binary in (
        ("claude", "claude"),
        ("hermes", "hermes"),
        ("codex", "codex"),
    ):
        path = shutil.which(binary)
        if path is None:
            results.append(
                ProbeResult(
                    harness_id=harness,
                    protocol="NATIVE_CLI",
                    executable=binary,
                    version=None,
                    discovered_capabilities={},
                    health_state="UNHEALTHY",
                    error="executable not found on PATH",
                )
            )
            continue
        rc_v, out_v, err_v = await runner((path, "--version"))
        rc_h, out_h, err_h = await runner((path, "--help"))
        version = (out_v or err_v).strip().splitlines()[0] if rc_v == 0 else None
        help_text = out_h + "\n" + err_h
        if harness == "claude":
            caps: dict[str, object] = {
                "persistent_session": _contains(help_text, "--session-id"),
                "session_resume": _contains(help_text, "--resume"),
                "session_fork": _contains(help_text, "--fork-session"),
                "streaming": _contains(help_text, "stream-json"),
                "structured_output": _contains(help_text, "--json-schema"),
                "model_request": _contains(help_text, "--model"),
                "reasoning_effort": _contains(help_text, "--effort"),
                "fallback_chain": _contains(help_text, "--fallback-model"),
                "tool_policy": _contains(help_text, "--allowedTools"),
                "subagents": _contains(help_text, "--agents"),
                "hook_events": _contains(help_text, "--include-hook-events"),
                "mcp": _contains(help_text, "--mcp-config"),
                "background": _contains(help_text, "--background"),
                "file_input": _contains(help_text, "--file"),
                "dangerous_permission_bypass_exposed": _contains(
                    help_text, "--dangerously-skip-permissions"
                ),
                "requires_per_invocation_approval": True,
            }
        elif harness == "hermes":
            supports_dde_context = _contains(help_text, "--ignore-rules")
            acp_check = (
                (path, "--ignore-rules", "acp", "--check")
                if supports_dde_context
                else (path, "acp", "--check")
            )
            rc_acp, out_acp, err_acp = await runner(acp_check)
            caps = {
                "persistent_session": _contains(help_text, "--resume"),
                "session_resume": _contains(help_text, "--resume"),
                "session_fork": False,
                "reasoning_effort": _contains(help_text, "--reasoning"),
                "model_request": _contains(help_text, "--model"),
                "provider_request": _contains(help_text, "--provider"),
                "fallback_chain": _contains(help_text, "fallback"),
                "skills": _contains(help_text, "--skills"),
                "toolsets": _contains(help_text, "--toolsets"),
                "worktree": _contains(help_text, "--worktree"),
                "hooks": _contains(help_text, "hooks"),
                "cron": _contains(help_text, "cron"),
                "memory": _contains(help_text, "memory"),
                "mcp": _contains(help_text, "mcp"),
                "dde_managed_context_mode": supports_dde_context and rc_acp == 0,
                "acp": _contains(help_text, "acp") and rc_acp == 0,
                "acp_check_detail": (out_acp or err_acp).strip(),
                "dangerous_permission_bypass_exposed": _contains(help_text, "--yolo"),
            }
        else:
            caps = {
                "persistent_session": _contains(help_text, "resume"),
                "session_resume": _contains(help_text, "resume"),
                "session_fork": _contains(help_text, "fork"),
                "model_request": _contains(help_text, "--model"),
                "sandbox_policy": _contains(help_text, "--sandbox"),
                "mcp": _contains(help_text, "mcp"),
                "structured_events": True,
                "image_input": _contains(help_text, "--image"),
                "web_search": _contains(help_text, "--search"),
                "dangerous_permission_bypass_exposed": _contains(
                    help_text, "dangerously-bypass-approvals"
                ),
            }
        results.append(
            ProbeResult(
                harness_id=harness,
                protocol="ACP"
                if harness == "hermes" and bool(caps.get("acp"))
                else "NATIVE_CLI",
                executable=path,
                version=version,
                discovered_capabilities=caps,
                health_state="HEALTHY" if rc_h == 0 and rc_v == 0 else "DEGRADED",
                error=None if rc_h == 0 and rc_v == 0 else (err_h or err_v).strip(),
            )
        )
    return tuple(results)


def endpoint_config_hash(probe: ProbeResult) -> str:
    payload = {
        "harness": probe.harness_id,
        "protocol": probe.protocol,
        "executable": probe.executable,
        "version": probe.version,
        "capabilities": probe.discovered_capabilities,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class AgentInteropService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.repo = FabricRepository(engine)

    async def discover_local(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        runner: ProbeRunner = _run_probe,
    ) -> tuple[AgentInteropEndpoint, ...]:
        probes = await discover_local_harnesses(runner)
        rows: list[AgentInteropEndpoint] = []
        for probe in probes:
            rows.append(
                await self._upsert_probe(
                    tenant_id=tenant_id, project_id=project_id, probe=probe
                )
            )
        return tuple(rows)

    async def _upsert_probe(
        self, *, tenant_id: UUID, project_id: UUID, probe: ProbeResult
    ) -> AgentInteropEndpoint:
        now = datetime.now(UTC)
        config_hash = endpoint_config_hash(probe)
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            existing_result = await uow.connection.execute(
                select(agent_interop_endpoints).where(
                    agent_interop_endpoints.c.harness_id == probe.harness_id,
                    agent_interop_endpoints.c.protocol == probe.protocol,
                    agent_interop_endpoints.c.executable_or_uri == probe.executable,
                )
            )
            existing = existing_result.mappings().one_or_none()
            if existing is None:
                values = {
                    "endpoint_id": uuid7(),
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "harness_id": probe.harness_id,
                    "protocol": probe.protocol,
                    "executable_or_uri": probe.executable,
                    "installation_version": probe.version,
                    "discovery_state": "DISCOVERED" if probe.version else "UNAVAILABLE",
                    "certification_state": "DISCOVERED",
                    "discovered_capabilities": probe.discovered_capabilities,
                    "certified_capabilities": {},
                    "certification_refs": [],
                    "health_state": probe.health_state,
                    "config_hash": config_hash,
                    "last_probe_at": now,
                    "last_error": probe.error,
                    "lock_version": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                result = await uow.connection.execute(
                    insert(agent_interop_endpoints)
                    .values(**values)
                    .returning(agent_interop_endpoints)
                )
            else:
                certification = str(existing["certification_state"])
                if (
                    existing["config_hash"] != config_hash
                    and certification == "CERTIFIED"
                ):
                    certification = "STALE"
                result = await uow.connection.execute(
                    update(agent_interop_endpoints)
                    .where(
                        agent_interop_endpoints.c.endpoint_id == existing["endpoint_id"]
                    )
                    .values(
                        installation_version=probe.version,
                        discovery_state="DISCOVERED"
                        if probe.version
                        else "UNAVAILABLE",
                        certification_state=certification,
                        discovered_capabilities=probe.discovered_capabilities,
                        health_state=probe.health_state,
                        config_hash=config_hash,
                        last_probe_at=now,
                        last_error=probe.error,
                        lock_version=agent_interop_endpoints.c.lock_version + 1,
                        updated_at=now,
                    )
                    .returning(agent_interop_endpoints)
                )
            row = result.mappings().one()
            await uow.commit()
        return AgentInteropEndpoint.model_validate(dict(row))

    async def register_external(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        harness_id: str,
        protocol: str,
        executable_or_uri: str,
        discovered_capabilities: dict[str, object] | None = None,
    ) -> AgentInteropEndpoint:
        """Register an explicit external/native endpoint as DISCOVERED only.

        Registration records where/how to probe a provider. It never certifies
        the endpoint and never writes provider credentials into DDE state.
        """
        if protocol not in {
            "NATIVE_CLI",
            "NATIVE_SDK",
            "ACP",
            "MCP",
            "HTTP",
            "OPENAI_COMPATIBLE",
        }:
            raise DdeError("VALIDATION_FAILED", "unknown interop protocol")
        if not harness_id.strip() or not executable_or_uri.strip():
            raise DdeError(
                "VALIDATION_FAILED", "harness_id and executable_or_uri are required"
            )
        now = datetime.now(UTC)
        probe = ProbeResult(
            harness_id=harness_id.strip(),
            protocol=protocol,
            executable=executable_or_uri.strip(),
            version=None,
            discovered_capabilities=discovered_capabilities or {},
            health_state="UNKNOWN",
            error=None,
        )
        config_hash = endpoint_config_hash(probe)
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            existing = (
                (
                    await uow.connection.execute(
                        select(agent_interop_endpoints).where(
                            agent_interop_endpoints.c.harness_id == probe.harness_id,
                            agent_interop_endpoints.c.protocol == probe.protocol,
                            agent_interop_endpoints.c.executable_or_uri
                            == probe.executable,
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                return AgentInteropEndpoint.model_validate(dict(existing))
            values = {
                "endpoint_id": uuid7(),
                "tenant_id": tenant_id,
                "project_id": project_id,
                "harness_id": probe.harness_id,
                "protocol": protocol,
                "executable_or_uri": probe.executable,
                "installation_version": None,
                "discovery_state": "DISCOVERED",
                "certification_state": "DISCOVERED",
                "discovered_capabilities": probe.discovered_capabilities,
                "certified_capabilities": {},
                "certification_refs": [],
                "health_state": "UNKNOWN",
                "config_hash": config_hash,
                "last_probe_at": None,
                "last_error": None,
                "lock_version": 1,
                "created_at": now,
                "updated_at": now,
            }
            result = await uow.connection.execute(
                insert(agent_interop_endpoints)
                .values(**values)
                .returning(agent_interop_endpoints)
            )
            row = result.mappings().one()
            await uow.commit()
        return AgentInteropEndpoint.model_validate(dict(row))

    async def list_endpoints(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[AgentInteropEndpoint, ...]:
        return await self.repo.list_models(
            table=agent_interop_endpoints,
            model=AgentInteropEndpoint,
            tenant_id=tenant_id,
            project_id=project_id,
            order_by=(agent_interop_endpoints.c.harness_id.asc(),),
        )

    async def certify(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        endpoint_id: UUID,
        certified_capabilities: dict[str, object],
        certification_refs: list[str],
        lock_version: int,
    ) -> AgentInteropEndpoint:
        endpoint = await self.repo.get_model(
            table=agent_interop_endpoints,
            model=AgentInteropEndpoint,
            id_column="endpoint_id",
            object_id=endpoint_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        if not certification_refs:
            raise DdeError(
                "EVIDENCE_MISSING",
                "interop endpoint certification requires contract-test evidence refs",
                retryable=False,
            )
        discovered = endpoint.discovered_capabilities
        unsupported = sorted(
            key
            for key, value in certified_capabilities.items()
            if bool(value) and not bool(discovered.get(key))
        )
        if unsupported:
            raise DdeError(
                "VALIDATION_FAILED",
                "cannot certify capabilities the installed endpoint did not discover",
                details={"capabilities": unsupported},
            )
        return await self.repo.update_locked(
            table=agent_interop_endpoints,
            model=AgentInteropEndpoint,
            id_column="endpoint_id",
            object_id=endpoint_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "certification_state": "CERTIFIED",
                "certified_capabilities": certified_capabilities,
                "certification_refs": certification_refs,
                "updated_at": datetime.now(UTC),
            },
        )

    async def record_capacity(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        endpoint_id: UUID,
        provider_id: str,
        state: str,
        confidence: float,
        quota_metadata: dict[str, object] | None = None,
        **optional: object,
    ) -> ProviderCapacitySnapshot:
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "snapshot_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "endpoint_id": endpoint_id,
            "provider_id": provider_id,
            "state": state,
            "reset_at": optional.get("reset_at"),
            "reset_source": optional.get("reset_source"),
            "confidence": confidence,
            "active_concurrency": optional.get("active_concurrency"),
            "max_concurrency": optional.get("max_concurrency"),
            "latency_ms": optional.get("latency_ms"),
            "recent_failures": optional.get("recent_failures")
            if isinstance(optional.get("recent_failures"), int)
            else 0,
            "input_cost_per_million": optional.get("input_cost_per_million"),
            "output_cost_per_million": optional.get("output_cost_per_million"),
            "quota_metadata": quota_metadata or {},
            "observed_at": now,
            "created_at": now,
            "updated_at": now,
        }
        ProviderCapacitySnapshot.model_validate(values)
        return await self.repo.insert_model(
            table=provider_capacity_snapshots,
            model=ProviderCapacitySnapshot,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )
