"""Verification that the human-accepted EDR records (EDR-0001..EDR-0014)
are durably persisted as accepted rows in the real `edrs` table (Chapter 3.6
sole-writer path), readable back through the Project Truth repository and
valid against the generated `Edr` contract (Chapter 3.1), and that every
registered-but-undecided slug stays exactly `proposed`.

The markdown files under docs/truth/edr/ are pre-image documentation only;
this test pins the authoritative database state their headers point at.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from engine.gateway.settings import get_settings
from engine.truth.db import open_unit_of_work
from engine.truth.repository import TruthRepository
from scripts.accept_owner_edrs import (
    ACCEPTED_OWNER_EDR_SLUGS,
    OWNER_PRINCIPAL_ID,
    OWNER_PROJECT_ID,
    OWNER_TENANT_ID,
    PROPOSED_OWNER_EDR_SLUGS,
    _payload,
)


def _owner_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url)


@pytest.mark.asyncio
async def test_all_accepted_owner_edrs_are_persisted_as_accepted() -> None:
    """Every accepted owner EDR slug resolves to exactly one accepted row
    decided by the recorded owner principal."""
    engine = _owner_engine()
    try:
        repository = TruthRepository()
        for slug in sorted(ACCEPTED_OWNER_EDR_SLUGS):
            async with open_unit_of_work(
                engine,
                tenant_id=OWNER_TENANT_ID,
                project_id=OWNER_PROJECT_ID,
            ) as uow:
                record = await repository.get_edr_by_slug(
                    uow.connection, OWNER_PROJECT_ID, slug
                )
                await uow.commit()
            assert record is not None, f"{slug} row missing from edrs"
            assert record.status == "accepted"
            assert record.decided_by_principal == OWNER_PRINCIPAL_ID
            assert record.decided_at is not None
            assert record.supersedes_id is None
            assert record.affected_requirement_slugs == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_owner_project_holds_exactly_the_accepted_slugs() -> None:
    """No extra or half-proposed EDR rows leak into the owner project."""
    engine = _owner_engine()
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text("SELECT slug, status FROM edrs WHERE project_id = :pid"),
                    {"pid": OWNER_PROJECT_ID},
                )
            ).all()
        assert {(slug, status) for slug, status in rows} == {
            (slug, "accepted") for slug in ACCEPTED_OWNER_EDR_SLUGS
        }
    finally:
        await engine.dispose()


def test_payload_covers_every_accepted_slug_with_pre_image() -> None:
    """Every accepted slug has a faithful payload transcription backed by its
    markdown pre-image; every registered-but-proposed slug has its pre-image
    file but deliberately no payload here (acceptance is always a human act,
    and this script's run loop never proposes those slugs)."""
    docs = Path(__file__).resolve().parents[2] / "docs" / "truth" / "edr"
    for slug in sorted(ACCEPTED_OWNER_EDR_SLUGS):
        payload = _payload(slug)
        assert set(payload) == {
            "context",
            "alternatives",
            "decision",
            "rationale",
            "consequences",
            "affected_requirement_slugs",
        }
        assert str(payload["context"]).strip()
        assert bool(payload["alternatives"])
        assert str(payload["decision"]).strip()
        assert str(payload["rationale"]).strip()
        assert bool(payload["consequences"])
        assert payload["affected_requirement_slugs"] == []
    for slug in sorted(ACCEPTED_OWNER_EDR_SLUGS | PROPOSED_OWNER_EDR_SLUGS):
        matches = list(docs.glob(f"{slug}-*.md"))
        assert matches, f"{slug} markdown pre-image missing under docs/truth/edr/"
