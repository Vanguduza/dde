"""Chapter 19.1 recovery: certification is process-local."""

from __future__ import annotations

import pytest

from adapters.cursor.adapter import CursorWorkerAdapter
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.smoke import run_smoke


@pytest.mark.asyncio
async def test_smoke_pass_does_not_survive_a_new_registry() -> None:
    adapter = CursorWorkerAdapter()
    writer = WorkerProfileRegistry()
    await writer.register_profile(adapter)
    report = await run_smoke(adapter)
    writer.record_smoke_pass(report.profile_id, report.profile_hash)
    assert writer.status_for(report.profile_id) == "CERTIFIED"

    reader = WorkerProfileRegistry()
    await reader.register_profile(CursorWorkerAdapter())
    assert reader.status_for(report.profile_id) == "STALE"
