"""Gateway scope model and command routing table (Chapter 14.2, 15.1, 15.4).

Baseline scopes come from the principal-class table in Chapter 14.2; a
session's requested scopes must be a subset of its `client_type` baseline.
`COMMAND_SCOPES` binds each gateway command to the scope required to execute
it, and `COMMAND_TARGET_TYPE` names the target kind a command must address.
Governance commands (`approval.batch_decide`,
`approval.request_budget_increase`, `approval.decide_budget_increase`) bind
the human `approval.decide` baseline for every decision and a separate
`approval.request` scope (human AND service baselines) for proposals;
neither binding grants decide authority to a non-human principal.
"""

from __future__ import annotations

from typing import Final

from engine.core.errors import DdeError

#: Baseline scopes granted per principal class (Chapter 14.2).
BASELINE_SCOPES: Final[dict[str, frozenset[str]]] = {
    "human": frozenset(
        {
            "mission.read",
            "mission.create",
            "mission.control",
            "approval.read",
            "approval.decide",
            # Propose-half only: a human may file a budget-increase
            # REQUEST for their own paused task (Ch.7.1/12.3); deciding
            # stays behind `approval.decide`. No decide authority is
            # widened by this scope.
            "approval.request",
            # Operator paste of static provider secrets (OpenSandbox API key)
            # through Studio Settings → Credential Broker capture seam.
            "credential.capture",
        }
    ),
    "service": frozenset(
        {
            "mission.read",
            "mission.control",
            "event.read",
            "approval.request",
            "credential.capture",
        }
    ),
    "worker": frozenset({"worker.execute", "worker.events", "worker.artifacts"}),
    "device": frozenset({"device.read", "device.command"}),
    "capability": frozenset({"capability.execute"}),
}

#: Scope required by each gateway command (Chapter 15.4 "Scope" column).
COMMAND_SCOPES: Final[dict[str, str]] = {
    "mission.create": "mission.create",
    "mission.pause": "mission.control",
    "mission.resume": "mission.control",
    "mission.cancel": "mission.control",
    "mission.read": "mission.read",
    # Chapter 15.4 governance row: `POST /v1/approvals` · `/{id}/decision`
    # binds `approval.*`. Deciding is a human act (Ch.13.1: only a human
    # may hold `approval.decide`; Ch.13.2 forbids standing pre-authorisation
    # of exactly the classes a batch would most want to decide), so both
    # decide-shaped commands bind the human-only scope and a service
    # principal is refused at the session-authorisation layer.
    "approval.batch_decide": "approval.decide",
    "approval.decide_budget_increase": "approval.decide",
    # Requesting a budget increase (Ch.7.1/12.3 pause-for-human path) only
    # proposes a ceiling for human attention; the human still decides. The
    # new `approval.request` scope (added to human AND service baselines)
    # keeps the propose half available to service principals without
    # widening any decide authority. Fail-closed: unknown command types
    # still raise FORBIDDEN in `required_scope`.
    "approval.request_budget_increase": "approval.request",
    "credential.capture_opensandbox": "credential.capture",
    "credential.inspect_opensandbox": "credential.capture",
    # DDE-054 / Ch.14.2: minimal device command under device.command.
    # Richer device surface is EDR-0030 if product needs it.
    "device.heartbeat": "device.command",
    # DDE-067 Frontend Studio — human authoring/compile/discovery ride
    # existing baselines (no new scope, no autonomy widening).
    "frontend.intake.compile_prompt": "mission.control",
    "frontend.donors.run_discovery": "mission.control",
    "frontend.donors.submit_uri": "mission.control",
    "frontend.donors.request_adoption": "approval.request",
    "frontend.prototype.request_pixel_signoff": "approval.request",
    "frontend.canvas.insert_component": "mission.control",
    "frontend.canvas.move_component": "mission.control",
    "frontend.canvas.update_element": "mission.control",
    "frontend.canvas.remove_element": "mission.control",
    "frontend.motion.set_animation": "mission.control",
    "frontend.flow.upsert_step": "mission.control",
    # DDE-069 Frontend Studio V2 -- contract/PXG/coverage authoring is
    # ordinary project authoring, so it rides `mission.control` like the
    # DDE-067 canvas commands. No new scope and no autonomy widening.
    "frontend.screen.register": "mission.control",
    "frontend.design.provider_status": "mission.read",
    "frontend.design.request": "mission.control",
    "frontend.design.try_live": "mission.control",
    "frontend.chat.open": "mission.control",
    "frontend.chat.set_context": "mission.control",
    "frontend.chat.send": "mission.control",
    "frontend.chat.rename": "mission.control",
    "frontend.chat.archive": "mission.control",
    "frontend.chat.set_mode": "mission.control",
    "frontend.chat.set_model": "mission.control",
    "frontend.chat.pin_context": "mission.control",
    "frontend.chat.branch": "mission.control",
    "frontend.chat.attachment.reserve": "mission.control",
    "frontend.chat.attachment.import_workspace": "mission.control",
    "frontend.chat.attachment.remove": "mission.control",
    "frontend.chat.plan.create": "mission.control",
    "frontend.chat.plan.update": "mission.control",
    "frontend.chat.plan.approve": "mission.control",
    "frontend.chat.plan.prepare_step": "mission.control",
    "frontend.chat.plan.record_step": "mission.control",
    "frontend.chat.plan.retry_step": "mission.control",
    "frontend.chat.plan.cancel": "mission.control",
    "frontend.chat.activity.cancel": "mission.control",
    "frontend.chat.checkpoint.create": "mission.control",
    "frontend.chat.checkpoint.restore": "mission.control",
    "frontend.chat.workspace.apply_patch": "mission.control",
    "frontend.chat.workspace.accept_file": "mission.control",
    "frontend.chat.workspace.revert_file": "mission.control",
    "frontend.chat.workspace.revert_all": "mission.control",
    "frontend.candidate.create": "mission.control",
    "frontend.candidate.transition": "mission.control",
    "frontend.candidate.promote": "mission.control",
    "frontend.mutation.apply": "mission.control",
    "frontend.mutation.revert": "mission.control",
    "frontend.preview.start": "mission.control",
    "frontend.preview.set_state": "mission.control",
    "frontend.preview.stop": "mission.control",
    "frontend.verification.run": "mission.control",
    "frontend.lock.create": "mission.control",
    "frontend.lock.release": "mission.control",
    "frontend.contract.publish": "mission.control",
    "frontend.pxg.apply": "mission.control",
    "frontend.coverage.recompute": "mission.control",
    "frontend.audit.run": "mission.control",
    "frontend.audit.recompute_affected": "mission.control",
    "frontend.audit.accept_exception": "mission.control",
}

#: Target kind each command must address (Chapter 15.2 target_type).
COMMAND_TARGET_TYPE: Final[dict[str, str]] = {
    "mission.create": "project",
    "mission.pause": "mission",
    "mission.resume": "mission",
    "mission.cancel": "mission",
    "mission.read": "mission",
    # Approvals and budget requests are project-scoped rows (Ch.3.2), so
    # the commands address the project and `_resolve_project` authorises
    # the principal grant for it directly.
    "approval.batch_decide": "project",
    "approval.request_budget_increase": "project",
    "approval.decide_budget_increase": "project",
    "credential.capture_opensandbox": "project",
    "credential.inspect_opensandbox": "project",
    "device.heartbeat": "device",
    "frontend.intake.compile_prompt": "mission",
    "frontend.donors.run_discovery": "mission",
    "frontend.donors.submit_uri": "mission",
    "frontend.donors.request_adoption": "mission",
    "frontend.prototype.request_pixel_signoff": "mission",
    "frontend.canvas.insert_component": "mission",
    "frontend.canvas.move_component": "mission",
    "frontend.canvas.update_element": "mission",
    "frontend.canvas.remove_element": "mission",
    "frontend.motion.set_animation": "mission",
    "frontend.flow.upsert_step": "mission",
    "frontend.screen.register": "mission",
    "frontend.design.provider_status": "mission",
    "frontend.design.request": "mission",
    "frontend.design.try_live": "mission",
    "frontend.chat.open": "mission",
    "frontend.chat.set_context": "mission",
    "frontend.chat.send": "mission",
    "frontend.chat.rename": "mission",
    "frontend.chat.archive": "mission",
    "frontend.chat.set_mode": "mission",
    "frontend.chat.set_model": "mission",
    "frontend.chat.pin_context": "mission",
    "frontend.chat.branch": "mission",
    "frontend.chat.attachment.reserve": "mission",
    "frontend.chat.attachment.import_workspace": "mission",
    "frontend.chat.attachment.remove": "mission",
    "frontend.chat.plan.create": "mission",
    "frontend.chat.plan.update": "mission",
    "frontend.chat.plan.approve": "mission",
    "frontend.chat.plan.prepare_step": "mission",
    "frontend.chat.plan.record_step": "mission",
    "frontend.chat.plan.retry_step": "mission",
    "frontend.chat.plan.cancel": "mission",
    "frontend.chat.activity.cancel": "mission",
    "frontend.chat.checkpoint.create": "mission",
    "frontend.chat.checkpoint.restore": "mission",
    "frontend.chat.workspace.apply_patch": "mission",
    "frontend.chat.workspace.accept_file": "mission",
    "frontend.chat.workspace.revert_file": "mission",
    "frontend.chat.workspace.revert_all": "mission",
    "frontend.candidate.create": "mission",
    "frontend.candidate.transition": "mission",
    "frontend.candidate.promote": "mission",
    "frontend.mutation.apply": "mission",
    "frontend.mutation.revert": "mission",
    "frontend.preview.start": "mission",
    "frontend.preview.set_state": "mission",
    "frontend.preview.stop": "mission",
    "frontend.verification.run": "mission",
    "frontend.lock.create": "mission",
    "frontend.lock.release": "mission",
    "frontend.contract.publish": "mission",
    "frontend.pxg.apply": "mission",
    "frontend.coverage.recompute": "mission",
    "frontend.audit.run": "mission",
    "frontend.audit.recompute_affected": "mission",
    "frontend.audit.accept_exception": "mission",
}

#: AI Conversation Fabric commands are explicit and mission-scoped. The dispatcher
#: may share one prefix branch only because required_scope() has already admitted the
#: exact command from this set; unknown frontend.fabric.* strings still fail closed.
LEGACY_FABRIC_COMMAND_TYPES: Final[frozenset[str]] = frozenset(
    {
        "frontend.fabric.policy.create",
        "frontend.fabric.policy.bind",
        "frontend.fabric.interop.discover",
        "frontend.fabric.interop.register",
        "frontend.fabric.interop.certify",
        "frontend.fabric.capacity.record",
        "frontend.fabric.session.open",
        "frontend.fabric.session.bind",
        "frontend.fabric.session.fork",
        "frontend.fabric.session.transition",
        "frontend.fabric.provider.invoke",
        "frontend.fabric.memory.propose",
        "frontend.fabric.memory.approve",
        "frontend.fabric.memory.reject",
        "frontend.fabric.memory.supersede",
        "frontend.fabric.context.snapshot",
        "frontend.fabric.skill.propose",
        "frontend.fabric.skill.begin_evaluation",
        "frontend.fabric.skill.certify",
        "frontend.fabric.skill.reject",
        "frontend.fabric.team.create",
        "frontend.fabric.team.add_member",
        "frontend.fabric.team.transition_member",
        "frontend.fabric.team.transition",
        "frontend.fabric.research.create",
        "frontend.fabric.research.add_source",
        "frontend.fabric.research.update",
        "frontend.fabric.research.complete",
        "frontend.fabric.research.to_plan",
        "frontend.fabric.automation.create",
        "frontend.fabric.automation.set_state",
        "frontend.fabric.automation.record_result",
        "frontend.fabric.hook.create",
        "frontend.fabric.hook.set_state",
        "frontend.fabric.hook.record_trigger",
        "frontend.fabric.claim.annotate",
        "frontend.fabric.experience.record",
        "frontend.fabric.insight.propose",
        "frontend.fabric.insight.advance",
    }
)
DDE_FABRIC_COMMAND_TYPES: Final[frozenset[str]] = frozenset(
    command.replace("frontend.fabric.", "dde.fabric.", 1)
    for command in LEGACY_FABRIC_COMMAND_TYPES
)
FABRIC_COMMAND_TYPES: Final[frozenset[str]] = frozenset(
    {*LEGACY_FABRIC_COMMAND_TYPES, *DDE_FABRIC_COMMAND_TYPES}
)

LEGACY_FRONTEND_CHAT_COMMAND_TYPES: Final[frozenset[str]] = frozenset(
    command for command in COMMAND_SCOPES if command.startswith("frontend.chat.")
)
DDE_CHAT_COMMAND_TYPES: Final[frozenset[str]] = frozenset(
    command.replace("frontend.chat.", "dde.chat.", 1)
    for command in LEGACY_FRONTEND_CHAT_COMMAND_TYPES
)

COMMAND_SCOPES.update({command: "mission.control" for command in FABRIC_COMMAND_TYPES})
COMMAND_TARGET_TYPE.update({command: "mission" for command in FABRIC_COMMAND_TYPES})
COMMAND_SCOPES.update(
    {command: "mission.control" for command in DDE_CHAT_COMMAND_TYPES}
)
COMMAND_TARGET_TYPE.update({command: "mission" for command in DDE_CHAT_COMMAND_TYPES})


#: Mission control command -> target mission status (Chapter 4.8).
MISSION_CONTROL_TARGETS: Final[dict[str, str]] = {
    "mission.pause": "PAUSED",
    "mission.resume": "ACTIVE",
    "mission.cancel": "CANCELLED",
}


def required_scope(command_type: str) -> str:
    if command_type not in COMMAND_SCOPES:
        raise DdeError(
            "FORBIDDEN",
            "Unsupported command_type",
            details={"command_type": command_type},
        )
    return COMMAND_SCOPES[command_type]


def required_target_type(command_type: str) -> str:
    return COMMAND_TARGET_TYPE[command_type]
