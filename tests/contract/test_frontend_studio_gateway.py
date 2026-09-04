"""Frontend Studio Gateway command types are registered (Ch.15.4).

Covers the DDE-067 command families and the DDE-069 V2 additions. Every
`frontend.*` type the dispatcher accepts must appear here, so a command
cannot reach production with no declared scope or target type.
"""

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

DDE_069_COMMANDS = (
    "frontend.screen.register",
    "frontend.contract.publish",
    "frontend.pxg.apply",
    "frontend.coverage.recompute",
)


def test_frontend_commands_are_registered() -> None:
    for command_type in FRONTEND_COMMANDS + DDE_069_COMMANDS:
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


def test_every_dispatched_frontend_command_declares_a_scope() -> None:
    """The dispatcher branches on literal command types; each must be in
    the scope map or it would reach the studio with no authority check."""
    import re

    from engine.context.repo import repo_root

    source = (repo_root() / "engine" / "gateway" / "commands.py").read_text(
        encoding="utf-8"
    )
    dispatched = set(re.findall(r'command_type == "(frontend\.[a-z_.]+)"', source))
    assert dispatched, "no frontend command branches found; parser is stale"
    assert dispatched <= set(FRONTEND_COMMANDS + DDE_069_COMMANDS)
    for command_type in dispatched:
        assert command_type in COMMAND_SCOPES, command_type
        assert command_type in COMMAND_TARGET_TYPE, command_type
