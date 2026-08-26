"""HTTP transport boundary for DDE Core."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import redis.asyncio as redis
import structlog
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from engine.contracts.healthz import Healthz
from engine.contracts.readyz import Readyz
from engine.core.errors import DdeError
from engine.gateway.api import dde_error_handler, router
from engine.gateway.settings import Settings, get_settings
from engine.governance.config import RuntimeFlags, validate_configuration

log = structlog.get_logger("dde.gateway")

# Ch.3.6 / DDE-052: browser operator assets live under interfaces/dashboard.
_DASHBOARD_STATIC = (
    Path(__file__).resolve().parents[2] / "interfaces" / "dashboard" / "static"
)


def _configure_tracer() -> None:
    provider = trace.get_tracer_provider()
    if type(provider).__name__ == "ProxyTracerProvider":
        trace.set_tracer_provider(
            TracerProvider(resource=Resource.create({"service.name": "dde-core"}))
        )


def _alembic_heads() -> set[str]:
    config = Config("alembic.ini")
    return set(ScriptDirectory.from_config(config).get_heads())


async def _database_ready(
    database_url: str,
) -> tuple[bool, Literal["head", "behind", "unknown"]]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            try:
                result = await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
                current = {str(row[0]) for row in result.all()}
            except Exception:
                return True, "behind"
        heads = _alembic_heads()
        if current == heads:
            return True, "head"
        return True, "behind"
    except Exception:
        log.warning("readyz.database_unreachable")
        return False, "unknown"
    finally:
        await engine.dispose()


async def _redis_ready(redis_url: str) -> bool:
    client = redis.from_url(redis_url)
    try:
        return bool(await client.ping())
    except Exception:
        log.warning("readyz.redis_unreachable")
        return False
    finally:
        await client.aclose()


def create_app() -> FastAPI:
    """Build the FastAPI application with liveness and readiness only."""
    _configure_tracer()
    validate_configuration(RuntimeFlags())
    application = FastAPI(title="DDE Core", version="0.1.0")
    FastAPIInstrumentor.instrument_app(application)
    application.include_router(router)
    application.add_exception_handler(DdeError, dde_error_handler)
    if _DASHBOARD_STATIC.is_dir():
        # Static operator UI only — no mission state. Same-origin /v1 calls
        # from /dashboard/ keep Ch.13.9 authz on the Gateway path.
        application.mount(
            "/dashboard",
            StaticFiles(directory=str(_DASHBOARD_STATIC), html=True),
            name="dashboard",
        )

    @application.get("/healthz")
    async def healthz() -> Healthz:
        return Healthz(status="ok")

    @application.get("/readyz")
    async def readyz() -> JSONResponse:
        settings: Settings = get_settings()
        database_ok, migrations = await _database_ready(settings.database_url)
        redis_ok = await _redis_ready(settings.redis_url)
        ready = database_ok and redis_ok and migrations == "head"
        status: Literal["ready", "not_ready"] = "ready" if ready else "not_ready"
        body = Readyz(
            status=status,
            database=database_ok,
            redis=redis_ok,
            migrations=migrations,
        )
        return JSONResponse(
            status_code=200 if ready else 503,
            content=body.model_dump(),
        )

    return application


app = create_app()
