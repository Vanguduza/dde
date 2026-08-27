"""DDE-067 Gateway command types are registered (Ch.15.4 / GUI spec §5)."""

from __future__ import annotations

from engine.capabilities.seed import SEED_CAPABILITIES
from engine.gateway.scopes import COMMAND_SCOPES, COMMAND_TARGET_TYPE, required_scope

FRONTEND_COMMANDS = (
    "frontend.intake.compile_prompt",
    "frontend.donors.run_discovery",
    "frontend.donors.submit_uri",
    "frontend.donors.request_adoption",
    "frontend.prototype.request_pixel_signoff",
    "frontend.canvas.insert_component",
    "frontend.canvas.move_component",
    "frontend.canvas.update_element",
    "frontend.canvas.remove_element",
    "frontend.motion.set_animation",
    "frontend.flow.upsert_step",
)


def test_frontend_commands_are_registered() -> None:
    for command_type in FRONTEND_COMMANDS:
        assert command_type in COMMAND_SCOPES
        assert command_type in COMMAND_TARGET_TYPE
        assert COMMAND_TARGET_TYPE[command_type] == "mission"
        required_scope(command_type)


def test_frontend_canvas_capability_declares_workspace_local() -> None:
    spec = next(
        item
        for item in SEED_CAPABILITIES
        if item.capability_id == "capability.frontend_canvas"
    )
    assert spec.side_effect_class == "WORKSPACE_LOCAL"
    assert spec.network_requirements.get("egress") == "none"
