"""Chapter 16.5 load probe and fixture inventory (DDE-063)."""

from __future__ import annotations

import pytest

from engine.load.inventory import missing_fixture_files
from engine.load.slo import API_READ_P95_MS, GatewaySloProbe


def test_slo_fixture_files_exist() -> None:
    assert missing_fixture_files() == []


@pytest.mark.asyncio
async def test_healthz_read_p95_under_slo() -> None:
    sample = await GatewaySloProbe().measure_healthz()
    assert sample.n >= 40
    assert sample.p95_ms < API_READ_P95_MS
