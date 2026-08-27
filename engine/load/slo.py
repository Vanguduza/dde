"""Chapter 16.5 operational read-latency probe at the production Gateway app.

`GatewaySloProbe.measure_healthz` hits `engine.gateway.app.app`'s `/healthz`
(the same ASGI app the HTTP process serves). The Chapter 16.5 target is
API p95 read latency < 500 ms.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import httpx

from engine.gateway.app import app

API_READ_P95_MS = 500.0
DEFAULT_SAMPLES = 40


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


class GatewaySloProbe:
    """Production caller for the Chapter 16.5 API read-latency SLO."""

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
        elapsed.sort()
        return LatencySample(
            n=len(elapsed),
            p50_ms=_percentile(elapsed, 0.50),
            p95_ms=_percentile(elapsed, 0.95),
            max_ms=elapsed[-1],
        )
