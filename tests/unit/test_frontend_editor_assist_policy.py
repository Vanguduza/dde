"""Fail-closed policy for editor assists that depend on external providers."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.errors import DdeError
from engine.studio.design.providers import DesignProviderStatus, ProviderState
from engine.studio.frontend import FrontendStudioService


class _UncertifiedGateway:
    async def provider_statuses(self) -> tuple[DesignProviderStatus, ...]:
        return (
            DesignProviderStatus(
                provider_id="claude-design",
                display_name="Claude Design",
                state=ProviderState.NOT_CERTIFIED,
                detail="no certified transport",
            ),
        )


@pytest.mark.asyncio
async def test_ai_suggest_cannot_enable_without_a_certified_provider() -> None:
    studio = FrontendStudioService(cast(AsyncEngine, object()))
    studio._design_gateway = lambda: _UncertifiedGateway()  # type: ignore[method-assign]

    with pytest.raises(DdeError) as excinfo:
        await studio.set_editor_assist(
            tenant_id=uuid4(),
            project_id=uuid4(),
            principal_id=uuid4(),
            parameters={"assist": "ai_suggest", "enabled": True},
        )

    assert excinfo.value.error_code == "PROVIDER_UNAVAILABLE"
    assert excinfo.value.details["providers"][0]["state"] == "NOT_CERTIFIED"
