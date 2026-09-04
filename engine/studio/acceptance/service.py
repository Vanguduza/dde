"""DDE-069 screen registration with automatic verification binding.

One governed step registers a generated screen in the Project Experience
Graph *and* authors its `AcceptanceOracle` carrying the mandatory DDE-068
visual bindings. Doing both together is the point: a screen that exists
in the graph but carries no oracle is a screen that can reach promotion
on code validity alone, and that is precisely the gap this closes.

The binding is not advisory. `AcceptanceOracleService.define` writes the
oracle the existing promotion gate already consumes -- proven in
`test_silhouette_promotion_gate_postgres.py` and
`test_visual_critique_promotion_gate_postgres.py` -- so binding by
default converts DDE-068's conditional guarantee into a universal one
without touching the gate itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.acceptance_oracle import AcceptanceOracle
from engine.contracts.task import Task
from engine.studio.acceptance.defaults import (
    GENERATED_SCREEN,
    assert_mandatory_bindings,
    build_screen_specs,
    load_defaults,
)
from engine.studio.pxg.service import NodeInput, PxgService, validate_key
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService


@dataclass(frozen=True)
class ScreenRegistration:
    """What a caller gets back, so the binding is inspectable rather than
    an invisible side effect."""

    screen_ref: str
    pxg_revision: int
    oracle: AcceptanceOracle
    bound_kinds: tuple[str, ...]
    policy_version: int


class ScreenAcceptanceService:
    """Registers a screen and binds its verification in one step."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        pxg: PxgService | None = None,
        oracles: AcceptanceOracleService | None = None,
        policy_root: Path | None = None,
    ) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)
        self._oracles = oracles or AcceptanceOracleService(engine)
        self._policy_root = policy_root

    async def register_screen(
        self,
        *,
        task: Task,
        screen_ref: str,
        title: str,
        preview_url: str,
        profile: str = GENERATED_SCREEN,
        route: str | None = None,
        expect_text: str | None = None,
        visual_diff_spec_path: str | None = None,
        extra_specs: tuple[CheckSpec, ...] = (),
        approved_by: str | None = None,
    ) -> ScreenRegistration:
        """Register `screen_ref` and author its default-bound oracle.

        `extra_specs` lets a caller add functional checks; it cannot
        remove the mandatory visual ones, because the assertion below
        runs over the merged list.
        """
        validate_key(screen_ref)
        defaults = load_defaults(self._policy_root)

        specs = build_screen_specs(
            screen_ref=screen_ref,
            preview_url=preview_url,
            profile=profile,
            expect_text=expect_text,
            visual_diff_spec_path=visual_diff_spec_path,
            root=self._policy_root,
        )
        merged = tuple(extra_specs) + specs

        # Fail closed before anything is written: a screen must not exist
        # in the graph with a half-bound oracle.
        assert_mandatory_bindings(
            merged,
            screen_ref=screen_ref,
            profile=profile,
            root=self._policy_root,
        )

        oracle = await self._oracles.define(
            task=task,
            outcomes=list(merged),
            approved_by=approved_by,
        )

        attributes: dict[str, object] = {
            "preview_url": preview_url,
            "acceptance_oracle_version": oracle.oracle_version,
            "acceptance_profile": profile,
            "acceptance_policy_version": defaults.policy_version,
            "bound_verification_kinds": sorted({spec.kind for spec in merged}),
        }
        if route:
            attributes["route"] = route

        revision = await self._pxg.apply(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            nodes=[
                NodeInput(
                    pxg_key=screen_ref,
                    node_kind="screen",
                    title=title,
                    attributes=attributes,
                    provenance={
                        "authored_by_task_id": str(task.task_id),
                        "mission_id": str(task.mission_id),
                    },
                )
            ],
        )
        return ScreenRegistration(
            screen_ref=screen_ref,
            pxg_revision=revision,
            oracle=oracle,
            bound_kinds=tuple(sorted({spec.kind for spec in merged})),
            policy_version=defaults.policy_version,
        )
