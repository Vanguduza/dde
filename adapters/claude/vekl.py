"""Claude Code materializers for DDE-owned Production VEKL artifacts.

Provider files are delivery artifacts only.  DDE's ActivationManifest, InstructionIR,
HookIR and TaskSignature remain authoritative; this module merely compiles already
selected/qualified material into Claude Code's documented project formats.

Provider hooks are defense in depth only. Current Claude Code command-hook behavior can
continue after some hook failures/timeouts, so a DDE ``BLOCK`` policy is never delegated
to provider hook semantics alone. Hard scope, capability, external-effect and completion
gates remain in DDE's own governed runtimes.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from engine.contracts.hook_ir import HookIR
from engine.contracts.instruction_ir import InstructionIR
from engine.core.errors import DdeError
from engine.vekl.engineering_playbook import EngineeringSkillDefinition

CLAUDE_EVENT_MAP: dict[str, str] = {
    "before_tool_use": "PreToolUse",
    "after_tool_use": "PostToolUse",
    "before_stop": "Stop",
    "before_task_complete": "TaskCompleted",
}
CLAUDE_EVENTS_WITHOUT_MATCHERS = frozenset({"Stop", "TaskCompleted"})


@dataclass(frozen=True)
class ClaudeSkillArtifact:
    relative_path: str
    content: str


def compile_claude_skill(skill: EngineeringSkillDefinition) -> ClaudeSkillArtifact:
    """Compile one explicitly selected DDE Skill into Claude's SKILL.md shape.

    ``disable-model-invocation`` is intentionally true. Claude must not independently
    decide to activate a VEKL skill: DDE resolves the exact skill revision and binds it
    to the ActivationManifest before this artifact is delivered.
    """

    frontmatter = (
        "---\n"
        f"name: {skill.skill_id}\n"
        f"description: {skill.description}\n"
        "disable-model-invocation: true\n"
        "---\n"
    )
    body = (
        f"# {skill.title}\n\n"
        "> Generated from a DDE-qualified VEKL resource. Project Truth, DDE policy, "
        "and the bound ActivationManifest outrank this guidance.\n\n"
        + "\n".join(f"- {item}" for item in skill.guidance)
        + "\n"
    )
    return ClaudeSkillArtifact(
        relative_path=f".claude/skills/{skill.skill_id}/SKILL.md",
        content=frontmatter + body,
    )


def compile_claude_instruction_ir(instruction: InstructionIR) -> str:
    """Materialize canonical InstructionIR as a concise generated CLAUDE.md."""

    constraints = "\n".join(f"- {item}" for item in instruction.constraints) or "- None"
    guidance = "\n".join(f"- {item}" for item in instruction.guidance) or "- None"
    provenance = (
        "\n".join(f"- {item}" for item in instruction.provenance_refs) or "- None"
    )
    return (
        "# DDE-generated Claude instructions\n\n"
        "This file is a compiled delivery artifact, not Project Truth. Do not edit it "
        "to change requirements or DDE policy.\n\n"
        f"Project Truth hash: `{instruction.project_truth_hash}`  \n"
        f"Policy hash: `{instruction.policy_hash}`  \n"
        f"Instruction hash: `{instruction.content_hash}`\n\n"
        "## Binding constraints\n"
        f"{constraints}\n\n"
        "## Qualified guidance\n"
        f"{guidance}\n\n"
        "## Provenance\n"
        f"{provenance}\n"
    )


def _claude_matcher(hook: HookIR) -> str:
    value = hook.matcher.get("claude")
    if value is None:
        value = hook.matcher.get("tool")
    if value is None and hook.event in {"before_stop", "before_task_complete"}:
        return ""
    if not isinstance(value, str):
        raise DdeError(
            "VEKL_HOOK_INVALID",
            "Claude hook materialization needs matcher.claude or matcher.tool",
            details={"hook_id": hook.hook_id},
        )
    return value


def compile_claude_hook_settings(hooks: list[HookIR]) -> dict[str, object]:
    """Compile safe command HookIR entries to `.claude/settings.json` structure.

    DDE-capability hooks stay in DDE's own LeaseBoundHookRuntime. Mapping them to an
    arbitrary provider shell command would bypass capability leases and ExternalEffect
    journaling, so this compiler fails closed for ``capability_id`` hooks. Command hooks
    emitted here are supplemental feedback/defense-in-depth and never replace DDE-native
    blocking enforcement.
    """

    result: dict[str, list[dict[str, object]]] = {}
    for hook in hooks:
        if hook.command is None or hook.capability_id is not None:
            raise DdeError(
                "VEKL_HOOK_INVALID",
                "Claude settings may materialize only concrete command HookIR entries",
                details={"hook_id": hook.hook_id},
            )
        try:
            event = CLAUDE_EVENT_MAP[hook.event]
        except KeyError as exc:
            raise DdeError(
                "VEKL_HOOK_INVALID",
                "HookIR event has no semantics-preserving Claude mapping",
                details={"hook_id": hook.hook_id, "event": hook.event},
            ) from exc
        matcher = _claude_matcher(hook)
        handler = {
            "type": "command",
            "command": shlex.join(hook.command),
            "timeout": hook.timeout_seconds,
        }
        group: dict[str, object] = {"hooks": [handler]}
        if event not in CLAUDE_EVENTS_WITHOUT_MATCHERS:
            group["matcher"] = matcher
        result.setdefault(event, []).append(group)
    return {"hooks": result}
