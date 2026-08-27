"""Chapter 16.5 operational latency probes at the production Gateway app.

Call sites are the same FastAPI routes the HTTP process serves
(`engine.gateway.app.app` via `interfaces.api`):

- API read p95 < 500 ms: `GET /v1/missions/{id}` (`read_mission`).
  `GET /healthz` is liveness only; it is not the domain read SLO.
- Command acceptance p95 < 1 s excluding heavy planning:
  `POST /v1/commands` (`GatewayCommandService.accept`) with `mission.create`
  (no planner/router on that path).
- Gateway reconnect recovery < 10 s for a bounded gap:
  `POST /v1/sessions/{id}/resume` (`GatewaySessionService.resume`).
  WS/SSE sequence replay remains EDR-0027.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from engine.gateway.app import app

API_READ_P95_MS = 500.0
COMMAND_ACCEPT_P95_MS = 1000.0
RECONNECT_RECOVERY_MS = 10000.0
DEFAULT_SAMPLES = 40
CONCURRENT_READS = 8

#: Routes this probe actually times. Not a QPS ceiling or soak result.
MEASURED_ROUTES = (
    "GET /healthz",
    "GET /v1/missions/{id}",
    "POST /v1/commands",
    "POST /v1/sessions/{id}/resume",
)

NOT_CLAIMED = (
    "published QPS ceiling or multi-instance soak",
    "planner/router latency (heavy planning, excluded by Ch.16.5)",
    "WS/SSE reconnect gap replay (EDR-0027)",
    "Frontend Studio CWV for generated outputs",
)


@dataclass(frozen=True)
class LatencySample:
    n: int
    p50_ms: float
    p95_ms: float
    max_ms: float


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        raise ValueError("no samples")
    index = min(len(sorted_values) - 1, max(0, math.ceil(p * len(sorted_values)) - 1))
    return sorted_values[index]


def _pack(elapsed: list[float]) -> LatencySample:
    elapsed.sort()
    return LatencySample(
        n=len(elapsed),
        p50_ms=_percentile(elapsed, 0.50),
        p95_ms=_percentile(elapsed, 0.95),
        max_ms=elapsed[-1],
    )


class GatewaySloProbe:
    """Production caller for the Chapter 16.5 latency SLOs."""

    async def measure_healthz(self, *, samples: int = DEFAULT_SAMPLES) -> LatencySample:
        elapsed: list[float] = []
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://slo.local"
        ) as client:
            for _ in range(samples):
                started = time.perf_counter()
                response = await client.get("/healthz")
                elapsed.append((time.perf_counter() - started) * 1000.0)
                if response.status_code != 200:
                    raise RuntimeError(f"/healthz returned {response.status_code}")
        return _pack(elapsed)

    async def measure_mission_read(
        self,
        client: httpx.AsyncClient,
        *,
        mission_id: str,
        headers: dict[str, str],
        samples: int = DEFAULT_SAMPLES,
    ) -> LatencySample:
        """Time `GET /v1/missions/{id}` — the Chapter 16.5 API read SLO."""
        path = f"/v1/missions/{mission_id}"
        return await self._time_loop(
            samples,
            lambda: client.get(path, headers=headers),
            expected_status=200,
            label=path,
        )

    async def measure_mission_read_concurrent(
        self,
        client: httpx.AsyncClient,
        *,
        mission_id: str,
        headers: dict[str, str],
        concurrency: int = CONCURRENT_READS,
    ) -> LatencySample:
        """Modest in-process burst against the same mission-read call site.

        This is load evidence on one ASGI app + one Postgres. It is not a
        capacity ceiling.
        """
        path = f"/v1/missions/{mission_id}"

        async def _one() -> float:
            started = time.perf_counter()
            response = await client.get(path, headers=headers)
            elapsed = (time.perf_counter() - started) * 1000.0
            if response.status_code != 200:
                raise RuntimeError(f"{path} returned {response.status_code}")
            return elapsed

        elapsed = list(await asyncio.gather(*[_one() for _ in range(concurrency)]))
        return _pack(elapsed)

    async def measure_command_acceptance(
        self,
        client: httpx.AsyncClient,
        *,
        bodies: list[dict[str, object]],
    ) -> LatencySample:
        """Time `POST /v1/commands` 202 — command acceptance, not completion."""
        elapsed: list[float] = []
        for body in bodies:
            started = time.perf_counter()
            response = await client.post("/v1/commands", json=body)
            elapsed.append((time.perf_counter() - started) * 1000.0)
            if response.status_code != 202:
                raise RuntimeError(f"/v1/commands returned {response.status_code}")
        return _pack(elapsed)

    async def measure_reconnect(
        self,
        client: httpx.AsyncClient,
        *,
        session_id: str,
        last_event_at: str,
        samples: int = DEFAULT_SAMPLES,
    ) -> LatencySample:
        """Time `POST /v1/sessions/{id}/resume` for a bounded event gap."""
        path = f"/v1/sessions/{session_id}/resume"
        body: dict[str, object] = {"last_event_at": last_event_at}
        elapsed: list[float] = []
        for _ in range(samples):
            started = time.perf_counter()
            response = await client.post(path, json=body)
            elapsed.append((time.perf_counter() - started) * 1000.0)
            if response.status_code != 200:
                raise RuntimeError(f"resume returned {response.status_code}")
            payload = response.json()
            if "session" not in payload or "fresh_snapshot" not in payload:
                raise RuntimeError("resume missing reconnect fields")
        return _pack(elapsed)

    async def _time_loop(
        self,
        samples: int,
        request: Callable[[], Awaitable[httpx.Response]],
        *,
        expected_status: int,
        label: str,
    ) -> LatencySample:
        elapsed: list[float] = []
        for _ in range(samples):
            started = time.perf_counter()
            response = await request()
            elapsed.append((time.perf_counter() - started) * 1000.0)
            if response.status_code != expected_status:
                raise RuntimeError(f"{label} returned {response.status_code}")
        return _pack(elapsed)
