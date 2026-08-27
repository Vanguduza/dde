"""PostgreSQL proofs for DDE-066 DonorDiscoveryService.search.

Production mutation: journal prepare+mark_sent before fetch, broker mint,
classify-before-use, persist taint via ingest, DDE-046 pins in the same
inventory. Transport is injected — this suite does not call the public net.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.donor.discovery_service import DonorDiscoveryService, SearchQuery
from engine.donor.grouping import FeatureCategory
from engine.donor.service import DonorLabService
from engine.recovery.scope import DONOR_SEARCH_GET_OPERATION, DONOR_SEARCH_SYSTEM
from engine.recovery.service import EFFECT_CONFLICT, ExternalEffectService
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import WorkerFixture, build_worker_fixture

FEATURES = (
    FeatureCategory(feature_id="feat-journals", title="Journals"),
    FeatureCategory(feature_id="feat-auth", title="Auth"),
)
GITHUB_SEARCH = "https://api.github.com/search/repositories?q=ledger"


async def _completed_run(
    engine: AsyncEngine, tmp_path: Path, mission_slug: str
) -> tuple[WorkerFixture, WorkerRun]:
    worker = await build_worker_fixture(engine, tmp_path, mission_slug=mission_slug)
    workspaces = WorkspaceService(engine, root=repo_root())
    leases = CapabilityLeaseService(engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    manager = WorkerManagerService(engine, registry, leases=leases)
    run = await manager.invoke_run(
        task=worker.task,
        execution_plan=worker.execution_plan,
        workspace=worker.workspace,
        input_context_hash=worker.context_package.assembly_hash,
        action=WorkerAction(command=[sys.executable, "-c", "pass"]),
        idempotency_key=f"{mission_slug}:invoke",
    )
    return worker, run


@pytest.mark.asyncio
async def test_search_journals_prepare_before_fetch_and_groups(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        worker, run = await _completed_run(engine, tmp_path, "MISSION-DONOR-SEARCH-1")
        workspace = worker.workspace
        order: list[str] = []
        effects = ExternalEffectService(engine)

        def fetch(uri: str, authorization: str | None) -> str:
            order.append(f"fetch:{uri}")
            assert authorization, "broker secret must reach the transport"
            return json.dumps(
                {
                    "items": [
                        {
                            "html_url": "https://github.com/acme/ledger",
                            "description": "MIT licensed journal UI",
                            "license": {"spdx_id": "MIT"},
                        }
                    ]
                }
            )

        original_prepare = effects.prepare

        async def recording_prepare(**kwargs):  # type: ignore[no-untyped-def]
            order.append(f"prepare:{kwargs['target_resource']}")
            return await original_prepare(**kwargs)

        effects.prepare = recording_prepare  # type: ignore[method-assign]
        ingest = DonorLabService(engine)
        await ingest.submit_uri(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            source_uri="https://example.local/pin",
            idempotency_key="donor-pin-1",
            content=b"Apache-2.0 fixture pin\n",
            media_kind="readme",
        )
        service = DonorDiscoveryService(engine, effects=effects, fetch=fetch)
        results = await service.search(
            worker_run=run,
            prd_id="prd-1",
            features=FEATURES,
            queries=(SearchQuery(uri=GITHUB_SEARCH, feature_ids=("feat-journals",)),),
            idempotency_key="donor-search-1",
        )
        assert order[0].startswith("prepare:")
        assert order[1].startswith("fetch:")
        by_feature = {fid: hits for fid, hits in results.groups}
        assert by_feature["feat-journals"]
        assert any(
            item.source_uri == "https://example.local/pin" for item in results.unmatched
        )
        journaled = await effects.list_for_run(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            worker_run_id=run.run_id,
        )
        donor_rows = [
            row
            for row in journaled
            if row.target_system == DONOR_SEARCH_SYSTEM
            and row.operation == DONOR_SEARCH_GET_OPERATION
        ]
        assert len(donor_rows) == 1
        assert donor_rows[0].status == "CONFIRMED"
        replayed = await service.search(
            worker_run=run,
            prd_id="prd-1",
            features=FEATURES,
            queries=(SearchQuery(uri=GITHUB_SEARCH, feature_ids=("feat-journals",)),),
            idempotency_key="donor-search-1",
        )
        assert replayed == results
        assert order.count(f"fetch:{GITHUB_SEARCH}") == 1
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_get_is_not_blind_retried(tmp_path: Path) -> None:
    engine = new_engine()
    workspace = None
    try:
        worker, run = await _completed_run(engine, tmp_path, "MISSION-DONOR-SEARCH-UNK")
        workspace = worker.workspace

        def boom(_uri: str, _authorization: str | None) -> str:
            raise TimeoutError("search timed out")

        service = DonorDiscoveryService(engine, fetch=boom)
        with pytest.raises(TimeoutError):
            await service.search(
                worker_run=run,
                prd_id="prd-1",
                features=FEATURES,
                queries=(SearchQuery(uri=GITHUB_SEARCH),),
                idempotency_key="donor-search-unk-1",
            )
        effects = ExternalEffectService(engine)
        journaled = await effects.list_for_run(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            worker_run_id=run.run_id,
        )
        donor_rows = [
            row for row in journaled if row.target_system == DONOR_SEARCH_SYSTEM
        ]
        assert donor_rows
        assert donor_rows[0].status == "UNKNOWN"
        with pytest.raises(DdeError) as captured:
            await service.search(
                worker_run=run,
                prd_id="prd-1",
                features=FEATURES,
                queries=(SearchQuery(uri=GITHUB_SEARCH),),
                idempotency_key="donor-search-unk-2",
            )
        assert captured.value.error_code == EFFECT_CONFLICT
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()
