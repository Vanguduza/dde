"""One-off operator inspection: list accepted EDR slugs in the owner project."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from engine.gateway.settings import get_settings
from engine.truth.db import build_engine, open_unit_of_work
from scripts.accept_owner_edrs import OWNER_PROJECT_ID, OWNER_TENANT_ID


async def run() -> None:
    engine = build_engine(get_settings().database_url)
    try:
        async with open_unit_of_work(
            engine,
            tenant_id=OWNER_TENANT_ID,
            project_id=OWNER_PROJECT_ID,
        ) as uow:
            result = await uow.connection.execute(
                text(
                    "SELECT edr_id, slug, status, decided_at FROM edrs "
                    "WHERE project_id = :project_id ORDER BY slug"
                ),
                {"project_id": OWNER_PROJECT_ID},
            )
            for row in result.mappings().all():
                print(dict(row))
            await uow.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
