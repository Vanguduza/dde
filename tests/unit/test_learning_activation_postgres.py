"""PostgreSQL-backed Chapter 6.9 activation refusal (DDE-058).

Exercises `LearningActivationService.attempt_advance` against a real
database: an empty eligible population must not advance `routing.mode`.
"""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from engine.learning.activation_service import LearningActivationService
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_attempt_advance_refuses_when_eligible_population_is_empty() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = LearningActivationService(engine)
        with pytest.raises(DdeError, match="learning activation gates unmet") as exc:
            await service.attempt_advance(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                current_mode="deterministic",
                requested_mode="shadow_learning",
            )
        details = exc.value.details or {}
        reasons = details.get("refused_reasons")
        assert isinstance(reasons, list)
        assert "eligible_real_attempts_global_below_threshold" in reasons
        assert details.get("requested_mode") == "shadow_learning"
    finally:
        await engine.dispose()
