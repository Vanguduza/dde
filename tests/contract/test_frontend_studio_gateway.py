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
    "frontend.design.provider_status",
    "frontend.design.request",
    "frontend.design.try_live",
    "frontend.chat.open",
    "frontend.chat.set_context",
    "frontend.chat.send",
    "frontend.chat.rename",
    "frontend.chat.archive",
    "frontend.chat.set_mode",
    "frontend.chat.set_model",
    "frontend.chat.pin_context",
    "frontend.chat.branch",
    "frontend.chat.attachment.reserve",
    "frontend.chat.attachment.import_workspace",
    "frontend.chat.attachment.remove",
    "frontend.chat.plan.create",
    "frontend.chat.plan.update",
    "frontend.chat.plan.approve",
    "frontend.chat.plan.prepare_step",
    "frontend.chat.plan.record_step",
    "frontend.chat.plan.retry_step",
    "frontend.chat.plan.cancel",
    "frontend.chat.activity.cancel",
    "frontend.chat.checkpoint.create",
    "frontend.chat.checkpoint.restore",
    "frontend.chat.workspace.apply_patch",
    "frontend.chat.workspace.accept_file",
    "frontend.chat.workspace.revert_file",
    "frontend.chat.workspace.revert_all",
    "frontend.candidate.create",
    "frontend.candidate.transition",
    "frontend.candidate.promote",
    "frontend.mutation.apply",
    "frontend.mutation.revert",
    "frontend.preview.start",
    "frontend.preview.set_state",
    "frontend.preview.stop",
    "frontend.verification.run",
    "frontend.lock.create",
    "frontend.lock.release",
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


def test_every_error_code_the_studio_raises_has_an_http_status() -> None:
    """An unmapped code returns 500, which turns a precise refusal into an
    apparent DDE bug. This caught `VALIDATION_FAILED`, then
    `CAPABILITY_UNAVAILABLE`, `DESIGN_SOURCE_REJECTED` and
    `STALE_REVISION`; it exists so the next one is caught before a client
    ever sees it."""
    import re

    from engine.context.repo import repo_root
    from engine.gateway.api import _HTTP_STATUS

    raised: set[str] = set()
    for path in (repo_root() / "engine" / "studio").rglob("*.py"):
        raised |= set(
            re.findall(r'DdeError\(\s*"([A-Z_]+)"', path.read_text(encoding="utf-8"))
        )
    assert raised, "no DdeError codes found; the parser is stale"
    unmapped = sorted(raised - set(_HTTP_STATUS))
    assert unmapped == [], (
        f"these codes would surface as HTTP 500: {unmapped}. Add them to "
        "engine/gateway/api.py::_HTTP_STATUS."
    )
