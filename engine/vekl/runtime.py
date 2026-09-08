"""Instruction, hook and bounded-loop runtime on existing DDE authorities."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.contracts.bounded_loop_definition import BoundedLoopDefinition
from engine.contracts.hook_ir import HookIR
from engine.contracts.instruction_ir import InstructionIR
from engine.contracts.task_signature import TaskSignature
from engine.contracts.vekl_resource import VEKLResource
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.recovery.service import ExternalEffectService

HookCall = Callable[[], Awaitable[dict[str, object]]]
ComponentCall = Callable[[], Awaitable[dict[str, object]]]
LoopStep = Callable[[int, int], Awaitable[None]]
LoopVerifier = Callable[[int], Awaitable[bool]]
LoopReserve = Callable[[int, int], Awaitable[dict[str, float]]]
LoopCheckpoint = Callable[[int], Awaitable[None]]
LoopRollback = Callable[[str], Awaitable[None]]

_EXECUTION_STATES = frozenset({"EXECUTION_EVALUATED", "CANARY", "PRODUCTION_QUALIFIED"})


def compile_instruction_ir(
    *,
    project_truth_hash: str,
    policy_hash: str,
    constraints: list[str],
    guidance: list[str],
    provenance_refs: list[str],
) -> InstructionIR:
    payload = {
        "version": "1",
        "project_truth_hash": project_truth_hash,
        "policy_hash": policy_hash,
        "constraints": constraints,
        "guidance": guidance,
        "provenance_refs": provenance_refs,
    }
    return InstructionIR(**payload, content_hash=sha256_hex(canonical_json(payload)))


def validate_hook_scope(hook: HookIR, signature: TaskSignature) -> str:
    if (hook.command is None) == (hook.capability_id is None):
        raise DdeError(
            "VEKL_HOOK_INVALID",
            "hook must declare exactly one command or DDE capability",
        )
    capability_id = hook.capability_id or "capability.run_local_process"
    if capability_id not in signature.required_capabilities:
        raise DdeError(
            "POLICY_DENIED",
            "hook capability exceeds the TaskSignature",
            details={"capability_id": capability_id},
        )
    checks = (
        (hook.filesystem_scopes, signature.allowed_filesystem_scopes, "filesystem"),
        (hook.network_scopes, signature.allowed_network_scopes, "network"),
        (hook.secret_scopes, signature.allowed_secret_scopes, "secret"),
    )
    for requested, allowed, scope_kind in checks:
        if not set(requested).issubset(set(allowed or [])):
            raise DdeError(
                "POLICY_DENIED",
                f"hook {scope_kind} scope exceeds the TaskSignature",
                details={"requested": requested, "allowed": allowed or []},
            )
    return capability_id


def validate_component_scope(
    resource: VEKLResource, signature: TaskSignature, capability_id: str
) -> None:
    """Re-check independently qualified executable scope at invocation time."""
    if resource.lifecycle_state not in _EXECUTION_STATES or not resource.component_kind:
        raise DdeError(
            "POLICY_DENIED",
            "VEKL executable component is not execution-qualified",
            details={"resource_id": str(resource.resource_id)},
        )
    if (
        capability_id not in resource.required_capabilities
        or capability_id not in signature.required_capabilities
    ):
        raise DdeError(
            "POLICY_DENIED",
            "VEKL executable capability exceeds resource or TaskSignature authority",
            details={"capability_id": capability_id},
        )
    checks = (
        (resource.filesystem_scopes, signature.allowed_filesystem_scopes, "filesystem"),
        (resource.network_scopes, signature.allowed_network_scopes, "network"),
        (resource.secret_scopes, signature.allowed_secret_scopes, "secret"),
    )
    for requested, allowed, scope_kind in checks:
        if not set(requested).issubset(set(allowed or [])):
            raise DdeError(
                "POLICY_DENIED",
                f"VEKL component {scope_kind} scope exceeds the TaskSignature",
                details={"requested": requested, "allowed": allowed or []},
            )


class LeaseBoundComponentRuntime:
    """Generic executable-component seam on CapabilityLease + ExternalEffect law."""

    def __init__(
        self,
        *,
        leases: CapabilityLeaseService,
        effects: ExternalEffectService,
    ) -> None:
        self._leases = leases
        self._effects = effects

    async def execute(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        worker_run_id: UUID,
        resource: VEKLResource,
        signature: TaskSignature,
        capability_id: str,
        operation: str,
        idempotency_key: str,
        invoke: ComponentCall,
        timeout_seconds: float,
        sandbox_available: bool,
        approval_scope_hash: str | None = None,
    ) -> dict[str, object]:
        validate_component_scope(resource, signature, capability_id)
        if not sandbox_available:
            raise DdeError(
                "POLICY_DENIED",
                "VEKL executable component lost its required sandbox at invocation",
            )
        lease = await self._leases.require_active(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_run_id=worker_run_id,
            capability_id=capability_id,
        )
        effect = None
        if resource.side_effect_class != "PURE_READ":
            effect = await self._effects.prepare(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                worker_run_id=worker_run_id,
                capability_lease_id=lease.lease_id,
                target_system="vekl_component",
                target_resource=str(resource.resource_id),
                operation=operation,
                side_effect_class=resource.side_effect_class,
                idempotency_key=idempotency_key,
                approval_scope_hash=approval_scope_hash,
            )
            if effect.status != "PREPARED":
                raise DdeError(
                    "EFFECT_CONFLICT",
                    "VEKL component effect already left PREPARED; refusing replay",
                    details={
                        "effect_id": str(effect.effect_id),
                        "status": effect.status,
                    },
                )
            await self._effects.mark_sent(
                tenant_id=tenant_id,
                project_id=project_id,
                effect_id=effect.effect_id,
            )
        try:
            result = await asyncio.wait_for(invoke(), timeout=timeout_seconds)
        except Exception as exc:
            if effect is not None:
                marker = (
                    self._effects.mark_unknown
                    if resource.side_effect_class
                    in {"EXTERNAL_NON_IDEMPOTENT", "IRREVERSIBLE"}
                    else self._effects.mark_failed
                )
                await marker(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    effect_id=effect.effect_id,
                    reason=type(exc).__name__,
                )
            raise
        if effect is not None:
            await self._effects.mark_confirmed(
                tenant_id=tenant_id,
                project_id=project_id,
                effect_id=effect.effect_id,
                response_hash=sha256_hex(canonical_json(result)),
            )
        return result


class LeaseBoundHookRuntime:
    """Every hook checkout uses a real lease; side effects are journaled first."""

    def __init__(
        self,
        *,
        leases: CapabilityLeaseService,
        effects: ExternalEffectService,
    ) -> None:
        self._leases = leases
        self._effects = effects

    async def execute(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        worker_run_id: UUID,
        hook: HookIR,
        resource: VEKLResource,
        signature: TaskSignature,
        idempotency_key: str,
        invoke: HookCall,
        sandbox_available: bool,
    ) -> dict[str, object]:
        capability_id = validate_hook_scope(hook, signature)
        validate_component_scope(resource, signature, capability_id)
        if not sandbox_available:
            raise DdeError(
                "POLICY_DENIED",
                "VEKL hook lost its required sandbox at invocation",
            )
        lease = await self._leases.require_active(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_run_id=worker_run_id,
            capability_id=capability_id,
        )
        effect = None
        if resource.side_effect_class != "PURE_READ":
            effect = await self._effects.prepare(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                worker_run_id=worker_run_id,
                capability_lease_id=lease.lease_id,
                target_system="vekl_hook",
                target_resource=str(resource.resource_id),
                operation=hook.event,
                side_effect_class=resource.side_effect_class,
                idempotency_key=idempotency_key,
            )
            await self._effects.mark_sent(
                tenant_id=tenant_id,
                project_id=project_id,
                effect_id=effect.effect_id,
            )
        try:
            result = await asyncio.wait_for(invoke(), timeout=hook.timeout_seconds)
        except Exception as exc:
            if effect is not None:
                marker = (
                    self._effects.mark_unknown
                    if resource.side_effect_class
                    in {"EXTERNAL_NON_IDEMPOTENT", "IRREVERSIBLE"}
                    else self._effects.mark_failed
                )
                await marker(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    effect_id=effect.effect_id,
                    reason=type(exc).__name__,
                )
            raise
        if effect is not None:
            await self._effects.mark_confirmed(
                tenant_id=tenant_id,
                project_id=project_id,
                effect_id=effect.effect_id,
                response_hash=sha256_hex(canonical_json(result)),
            )
        return result


@dataclass(frozen=True)
class LoopResult:
    state: str
    cycles: int
    steps_executed: int
    verifier_terminated: bool
    budget_used: dict[str, float]
    rollback_executed: bool = False
    exhaustion_reason: str | None = None


def _loop_budget_limits(definition: BoundedLoopDefinition) -> dict[str, float]:
    limits: dict[str, float] = {}
    for key, raw in definition.budget.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0:
            raise DdeError(
                "VEKL_LOOP_INVALID",
                "bounded loop budget values must be non-negative numbers",
                details={"budget_key": key},
            )
        limits[str(key)] = float(raw)
    return limits


async def run_bounded_loop(
    definition: BoundedLoopDefinition,
    *,
    run_step: LoopStep,
    verify: LoopVerifier,
    reserve: LoopReserve | None = None,
    checkpoint: LoopCheckpoint | None = None,
    rollback: LoopRollback | None = None,
) -> LoopResult:
    if (
        definition.max_cycles < 1
        or definition.max_steps < 1
        or not definition.steps
        or not definition.verifier.strip()
    ):
        raise DdeError(
            "VEKL_LOOP_INVALID",
            "bounded loops require positive bounds, steps and a verifier",
        )
    limits = _loop_budget_limits(definition)
    measured = set(limits) - {"steps", "cycles"}
    if measured and reserve is None:
        raise DdeError(
            "VEKL_LOOP_BUDGET_UNMEASURED",
            "bounded loop declares measured budgets without a pre-step reservation",
            details={"budget_dimensions": sorted(measured)},
        )
    needs_checkpoint = any(item == "each_cycle" for item in definition.checkpoints)
    if needs_checkpoint and checkpoint is None:
        raise DdeError(
            "VEKL_LOOP_CHECKPOINT_UNAVAILABLE",
            "bounded loop requires each-cycle checkpoints but no checkpoint "
            "writer exists",
        )
    rollback_required = definition.rollback_policy.strip().lower() not in {
        "",
        "none",
        "no_rollback",
    }
    if rollback_required and rollback is None:
        raise DdeError(
            "VEKL_LOOP_ROLLBACK_UNAVAILABLE",
            "bounded loop declares rollback policy but no rollback runtime exists",
        )
    usage: dict[str, float] = {"steps": 0.0, "cycles": 0.0}
    steps_executed = 0
    last_cycle = 0

    async def exhaust(reason: str) -> LoopResult:
        rolled_back = False
        if rollback_required and rollback is not None:
            await rollback(reason)
            rolled_back = True
        return LoopResult(
            "EXHAUSTED",
            last_cycle,
            steps_executed,
            False,
            dict(usage),
            rolled_back,
            reason,
        )

    for cycle in range(1, definition.max_cycles + 1):
        last_cycle = cycle
        next_cycles = usage["cycles"] + 1.0
        if "cycles" in limits and next_cycles > limits["cycles"]:
            return await exhaust("budget:cycles")
        usage["cycles"] = next_cycles
        for index, _step in enumerate(definition.steps, start=1):
            if steps_executed >= definition.max_steps:
                return await exhaust("max_steps")
            charges: dict[str, float] = {"steps": 1.0}
            if reserve is not None:
                reserved = await reserve(cycle, index)
                for key, raw in reserved.items():
                    if (
                        isinstance(raw, bool)
                        or not isinstance(raw, (int, float))
                        or raw < 0
                    ):
                        raise DdeError(
                            "VEKL_LOOP_INVALID",
                            "loop reservation charges must be non-negative numbers",
                            details={"budget_key": key},
                        )
                    charges[str(key)] = charges.get(str(key), 0.0) + float(raw)
            for key, limit in limits.items():
                if usage.get(key, 0.0) + charges.get(key, 0.0) > limit:
                    return await exhaust(f"budget:{key}")
            await run_step(cycle, index)
            steps_executed += 1
            for key, charge in charges.items():
                usage[key] = usage.get(key, 0.0) + charge
        if needs_checkpoint and checkpoint is not None:
            await checkpoint(cycle)
        if await verify(cycle):
            return LoopResult(
                "VERIFIED",
                cycle,
                steps_executed,
                True,
                dict(usage),
                False,
                None,
            )
    return await exhaust("max_cycles")
