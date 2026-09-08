"""Adversarial Production VEKL policy/runtime acceptance without external egress."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from engine.capabilities.seed import SEED_CAPABILITIES
from engine.context.hashing import assembly_hash
from engine.context.model import ContextExtension
from engine.contracts.bounded_loop_definition import BoundedLoopDefinition
from engine.contracts.hook_ir import HookIR
from engine.contracts.task_signature import TaskSignature
from engine.contracts.vekl_activation_manifest import VEKLActivationManifest
from engine.contracts.vekl_resource import VEKLResource
from engine.contracts.workspace import Workspace
from engine.core.errors import BudgetExhaustedError, DdeError
from engine.vekl.compiler import VEKLKnowledgeCompiler
from engine.vekl.policy import (
    APPLICATION_MANUFACTURING_VEKL,
    EligibilityContext,
    EligibilityDecision,
    enforce_target_scope,
    evaluate,
)
from engine.vekl.runtime import (
    LeaseBoundComponentRuntime,
    LeaseBoundHookRuntime,
    compile_instruction_ir,
    run_bounded_loop,
    validate_hook_scope,
)
from engine.vekl.service import VEKLService
from engine.vekl.stack import observe_workspace_stack

NOW = datetime.now(UTC)
TENANT = uuid4()
PROJECT = uuid4()
TASK = uuid4()
FINGERPRINT = uuid4()


def signature(**changes: object) -> TaskSignature:
    values: dict[str, object] = {
        "signature_id": uuid4(),
        "tenant_id": TENANT,
        "project_id": PROJECT,
        "task_id": TASK,
        "fingerprint_id": FINGERPRINT,
        "lifecycle_stage": "implementation",
        "task_class": "implementation",
        "constraints": {
            "versions": {"react": "19.2.8"},
            "stack": {
                "os": "linux",
                "package_manager": "pnpm",
                "deployment_target": "web",
            },
        },
        "risk_category": "medium",
        "error_signatures": [],
        "required_capabilities": ["capability.run_local_process"],
        "allowed_filesystem_scopes": ["src/**"],
        "allowed_network_scopes": [],
        "allowed_secret_scopes": [],
        "required_verifiers": ["pytest"],
        "freshness_needs": {},
        "budget": {"tokens": 500},
        "signature_hash": "signature-hash",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return TaskSignature.model_validate(values)


def resource(**changes: object) -> VEKLResource:
    values: dict[str, object] = {
        "resource_id": uuid4(),
        "tenant_id": TENANT,
        "project_id": PROJECT,
        "parent_resource_id": None,
        "source_id": None,
        "source_artifact_id": None,
        "resource_kind": "OFFICIAL_DOC",
        "component_kind": None,
        "title": "React exact docs",
        "publisher": "React",
        "source_uri": None,
        "revision": "19.2.8",
        "content_hash": "a" * 64,
        "source_trust": "S2_FIRST_PARTY",
        "reuse_class": "SOURCE_REFERENCE_ONLY",
        "lifecycle_state": "REFERENCE_QUALIFIED",
        "activation_modes": ["READ_ONLY_CONTEXT"],
        "exact_versions": {"react": "19.2.8"},
        "license_ids": ["MIT"],
        "provenance": {
            "source": "operator-materialized exact pin",
            "hash_verified": True,
            "offline_pin_available": True,
        },
        "required_capabilities": [],
        "filesystem_scopes": [],
        "network_scopes": [],
        "secret_scopes": [],
        "sandbox_requirements": {},
        "side_effect_class": "PURE_READ",
        "required_verifiers": [],
        "stack_constraints": {},
        "truth_constraints": {},
        "freshness": {"stale": False},
        "budget": {"tokens": 100},
        "injection_findings": [],
        "content_excerpt": "Use createRoot for React 19.",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return VEKLResource.model_validate(values)


def context(**changes: object) -> EligibilityContext:
    values: dict[str, object] = {
        "project_kind": "TARGET_APPLICATION",
        "request_mode": APPLICATION_MANUFACTURING_VEKL,
        "truth_constraints": {},
        "admitted_source_ids": frozenset(),
        "available_capabilities": frozenset({"capability.run_local_process"}),
        "available_verifiers": frozenset({"pytest"}),
        "sandbox_available": True,
    }
    values.update(changes)
    return EligibilityContext(**values)  # type: ignore[arg-type]


def decision(item: VEKLResource, **context_changes: object) -> EligibilityDecision:
    return evaluate(
        item,
        activation_mode=item.activation_modes[0],
        signature=signature(),
        context=context(**context_changes),
    )


def test_stack_fingerprint_observation_is_workspace_derived_and_hash_backed(
    tmp_path: Path,
) -> None:
    (tmp_path / "package.json").write_text(
        '{"packageManager":"pnpm@10.0.0","dependencies":'
        '{"react":"19.2.8","vite":"^7.3.6"}}'
    )
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    workspace = Workspace(
        workspace_id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        task_id=TASK,
        execution_environment_id=uuid4(),
        base_revision="base",
        current_revision="head",
        workspace_path=str(tmp_path),
        policy={},
        status="READY",
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    observation = observe_workspace_stack(workspace)
    assert observation.facts["package_manager"] == "pnpm"
    assert observation.facts["versions"] == {"react": "19.2.8"}
    assert observation.facts["lockfiles"] == ["pnpm-lock.yaml"]
    assert all(
        "#sha256:" in ref or ":revision:" in ref for ref in observation.evidence_refs
    )


def test_self_scope_refuses_with_typed_error() -> None:
    with pytest.raises(DdeError) as caught:
        enforce_target_scope(
            project_kind="DDE_CONTROL_PLANE",
            request_mode=APPLICATION_MANUFACTURING_VEKL,
        )
    assert caught.value.error_code == "VEKL_SCOPE_VIOLATION"


def test_project_truth_precedence_and_wrong_major_reject() -> None:
    conflict = resource(truth_constraints={"requirement:ui": "use Vue"})
    truth_decision = decision(
        conflict, truth_constraints={"requirement:ui": "use React"}
    )
    assert "PROJECT_TRUTH_CONFLICT" in truth_decision.reasons
    wrong_major = resource(exact_versions={"react": "18.x"})
    assert "VERSION_INCOMPATIBLE" in decision(wrong_major).reasons
    wrong_stack = resource(
        stack_constraints={"os": ["windows"], "package_manager": "pnpm"}
    )
    assert "STACK_INCOMPATIBLE" in decision(wrong_stack).reasons


def test_revoked_and_stale_security_resources_refuse() -> None:
    assert "RESOURCE_REVOKED" in decision(resource(lifecycle_state="REVOKED")).reasons
    security = resource(
        resource_kind="SECURITY_FEED",
        freshness={"stale": True, "mandatory": True},
    )
    assert "MANDATORY_SECURITY_EVIDENCE_STALE" in decision(security).reasons


def test_plugin_bundle_does_not_approve_components_and_mcp_scope_is_minimized() -> None:
    bundle = resource(
        resource_kind="PLUGIN",
        lifecycle_state="PRODUCTION_QUALIFIED",
        activation_modes=["PLUGIN_COMPONENT"],
        reuse_class="OPEN_REUSE",
    )
    assert "BUNDLE_EXECUTION_FORBIDDEN" in decision(bundle).reasons
    component = resource(
        resource_kind="MCP_SERVER",
        component_kind="mcp-server",
        parent_resource_id=bundle.resource_id,
        lifecycle_state="PRODUCTION_QUALIFIED",
        activation_modes=["MCP_RUNTIME"],
        reuse_class="OPEN_REUSE",
        network_scopes=["api.example.invalid/**"],
    )
    assert "NETWORK_SCOPE_EXCESSIVE" in decision(component).reasons


def test_injection_offline_pin_and_budget_are_hard_eligibility() -> None:
    injected = resource(injection_findings=["injection_phrase:ignore previous"])
    assert "PROMPT_INJECTION_DETECTED" in decision(injected).reasons
    unpinned = resource(
        exact_versions={}, provenance={"source": "x", "hash_verified": True}
    )
    assert "OFFLINE_EXACT_PIN_REQUIRED" in decision(unpinned, offline=True).reasons
    expensive = resource(budget={"tokens": 501})
    assert "RESERVED_BUDGET_INSUFFICIENT" in decision(expensive).reasons


def test_source_capability_verifier_sandbox_and_secret_admission_are_independent() -> (
    None
):
    source_id = uuid4()
    guarded = resource(
        source_id=source_id,
        component_kind="tool",
        resource_kind="TOOL",
        lifecycle_state="PRODUCTION_QUALIFIED",
        activation_modes=["TOOL_EXECUTION"],
        reuse_class="OPEN_REUSE",
        required_capabilities=["capability.tool.missing"],
        required_verifiers=["tool-oracle"],
        secret_scopes=["production/*"],
    )
    result = decision(guarded, sandbox_available=False)
    assert {
        "SOURCE_NOT_ADMITTED",
        "CAPABILITY_UNAVAILABLE",
        "VERIFIER_UNAVAILABLE",
        "SECRET_SCOPE_EXCESSIVE",
        "SANDBOX_UNAVAILABLE",
    }.issubset(result.reasons)


def test_vekl_capabilities_are_narrow_and_carry_risk_effect_metadata() -> None:
    specs = {
        item.capability_id: item
        for item in SEED_CAPABILITIES
        if item.capability_id.startswith("capability.vekl.")
    }
    assert set(specs) == {
        "capability.vekl.qualify",
        "capability.vekl.resolve",
        "capability.vekl.compile_context",
    }
    assert specs["capability.vekl.compile_context"].side_effect_class == "PURE_READ"
    assert all(item.risk_class in {"low", "medium"} for item in specs.values())
    assert all(
        item.network_requirements.get("egress") == "none" for item in specs.values()
    )


@pytest.mark.asyncio
async def test_component_runtime_rechecks_lease_scope_and_journals_before_effect() -> (
    None
):
    states: list[str] = []

    class Leases:
        async def require_active(self, **_kwargs: object) -> object:
            states.append("LEASE")
            return SimpleNamespace(lease_id=uuid4())

    class Effects:
        async def prepare(self, **_kwargs: object) -> object:
            states.append("PREPARED")
            return SimpleNamespace(effect_id=uuid4(), status="PREPARED")

        async def mark_sent(self, **_kwargs: object) -> None:
            states.append("SENT")

        async def mark_unknown(self, **_kwargs: object) -> None:
            states.append("UNKNOWN")

        async def mark_failed(self, **_kwargs: object) -> None:
            states.append("FAILED")

        async def mark_confirmed(self, **_kwargs: object) -> None:
            states.append("CONFIRMED")

    runtime = LeaseBoundComponentRuntime(
        leases=cast("object", Leases()),  # type: ignore[arg-type]
        effects=cast("object", Effects()),  # type: ignore[arg-type]
    )
    tool = resource(
        resource_kind="TOOL",
        component_kind="cli",
        lifecycle_state="PRODUCTION_QUALIFIED",
        activation_modes=["TOOL_EXECUTION"],
        reuse_class="OPEN_REUSE",
        required_capabilities=["capability.run_local_process"],
        filesystem_scopes=["src/**"],
        side_effect_class="WORKSPACE_LOCAL",
    )

    async def invoke() -> dict[str, object]:
        states.append("INVOKE")
        return {"ok": True}

    result = await runtime.execute(
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        worker_run_id=uuid4(),
        resource=tool,
        signature=signature(),
        capability_id="capability.run_local_process",
        operation="format",
        idempotency_key="tool-1",
        invoke=invoke,
        timeout_seconds=5,
        sandbox_available=True,
    )
    assert result == {"ok": True}
    assert states == ["LEASE", "PREPARED", "SENT", "INVOKE", "CONFIRMED"]

    with pytest.raises(DdeError) as caught:
        await runtime.execute(
            tenant_id=TENANT,
            project_id=PROJECT,
            mission_id=uuid4(),
            worker_run_id=uuid4(),
            resource=tool.model_copy(update={"network_scopes": ["internet/**"]}),
            signature=signature(),
            capability_id="capability.run_local_process",
            operation="format",
            idempotency_key="tool-2",
            invoke=invoke,
            timeout_seconds=5,
            sandbox_available=True,
        )
    assert caught.value.error_code == "POLICY_DENIED"


def test_hook_scope_refuses_permission_broadening() -> None:
    hook = HookIR(
        hook_id="lint",
        hook_class="pre_commit",
        event="before_commit",
        matcher={"paths": ["src/**"]},
        command=None,
        capability_id="capability.run_local_process",
        filesystem_scopes=["**/*"],
        network_scopes=[],
        secret_scopes=[],
        timeout_seconds=30,
        failure_policy="BLOCK",
        evidence_types=["command_result"],
    )
    with pytest.raises(DdeError) as caught:
        validate_hook_scope(hook, signature())
    assert caught.value.error_code == "POLICY_DENIED"


def test_instruction_ir_is_hash_bound_to_truth_policy_and_provenance() -> None:
    first = compile_instruction_ir(
        project_truth_hash="truth-a",
        policy_hash="policy-a",
        constraints=["must pass pytest"],
        guidance=["use exact React 19 API"],
        provenance_refs=["vekl:resource@19.2.8#abc"],
    )
    changed = compile_instruction_ir(
        project_truth_hash="truth-b",
        policy_hash="policy-a",
        constraints=["must pass pytest"],
        guidance=["use exact React 19 API"],
        provenance_refs=["vekl:resource@19.2.8#abc"],
    )
    assert first.content_hash != changed.content_hash


@pytest.mark.asyncio
async def test_uncertain_hook_effect_is_journaled_unknown_and_never_retried() -> None:
    calls = 0

    class Leases:
        async def require_active(self, **_kwargs: object) -> object:
            return SimpleNamespace(lease_id=uuid4())

    class Effects:
        def __init__(self) -> None:
            self.states: list[str] = []

        async def prepare(self, **_kwargs: object) -> object:
            self.states.append("PREPARED")
            return SimpleNamespace(effect_id=uuid4())

        async def mark_sent(self, **_kwargs: object) -> None:
            self.states.append("SENT")

        async def mark_unknown(self, **_kwargs: object) -> None:
            self.states.append("UNKNOWN")

        async def mark_failed(self, **_kwargs: object) -> None:
            self.states.append("FAILED")

        async def mark_confirmed(self, **_kwargs: object) -> None:
            self.states.append("CONFIRMED")

    effects = Effects()
    runtime = LeaseBoundHookRuntime(
        leases=cast("object", Leases()),  # type: ignore[arg-type]
        effects=cast("object", effects),  # type: ignore[arg-type]
    )
    hook_resource = resource(
        resource_kind="HOOK",
        component_kind="hook",
        lifecycle_state="PRODUCTION_QUALIFIED",
        activation_modes=["HOOK_ENFORCEMENT"],
        reuse_class="OPEN_REUSE",
        required_capabilities=["capability.run_local_process"],
        filesystem_scopes=["src/**"],
        side_effect_class="EXTERNAL_NON_IDEMPOTENT",
    )
    hook = HookIR(
        hook_id="format",
        hook_class="pre_commit",
        event="before_commit",
        matcher={},
        command=["ruff", "format", "src"],
        capability_id=None,
        filesystem_scopes=["src/**"],
        network_scopes=[],
        secret_scopes=[],
        timeout_seconds=5,
        failure_policy="BLOCK",
        evidence_types=["effect"],
    )

    async def uncertain() -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise TimeoutError("outcome unknown")

    with pytest.raises(TimeoutError):
        await runtime.execute(
            tenant_id=TENANT,
            project_id=PROJECT,
            mission_id=uuid4(),
            worker_run_id=uuid4(),
            hook=hook,
            resource=hook_resource,
            signature=signature(),
            idempotency_key="hook-1",
            invoke=uncertain,
            sandbox_available=True,
        )
    assert calls == 1
    assert effects.states == ["PREPARED", "SENT", "UNKNOWN"]


@pytest.mark.asyncio
async def test_bounded_loop_exhausts_and_verifier_terminates() -> None:
    definition = BoundedLoopDefinition(
        loop_id="compile-repair",
        entry_condition="compile failed",
        objective="compile passes",
        max_cycles=3,
        max_steps=3,
        steps=[{"action": "repair"}],
        allowed_resource_ids=[],
        allowed_capabilities=[],
        budget={"tokens": 100},
        verifier="compile",
        checkpoints=["each_cycle"],
        failure_policy="escalate",
        rollback_policy="last_checkpoint",
    )
    calls: list[tuple[int, int]] = []
    checkpoints: list[int] = []
    rollbacks: list[str] = []

    async def step(cycle: int, index: int) -> None:
        calls.append((cycle, index))

    async def reserve(_cycle: int, _index: int) -> dict[str, float]:
        return {"tokens": 10}

    async def checkpoint(cycle: int) -> None:
        checkpoints.append(cycle)

    async def rollback(reason: str) -> None:
        rollbacks.append(reason)

    async def never(_cycle: int) -> bool:
        return False

    exhausted = await run_bounded_loop(
        definition,
        run_step=step,
        verify=never,
        reserve=reserve,
        checkpoint=checkpoint,
        rollback=rollback,
    )
    assert exhausted.state == "EXHAUSTED"
    assert exhausted.steps_executed == 3
    assert exhausted.rollback_executed is True
    assert exhausted.budget_used["tokens"] == 30
    assert rollbacks == ["max_cycles"]

    calls.clear()
    checkpoints.clear()
    rollbacks.clear()

    async def second(cycle: int) -> bool:
        return cycle == 2

    verified = await run_bounded_loop(
        definition,
        run_step=step,
        verify=second,
        reserve=reserve,
        checkpoint=checkpoint,
        rollback=rollback,
    )
    assert verified.state == "VERIFIED"
    assert verified.verifier_terminated is True
    assert verified.cycles == 2
    assert checkpoints == [1, 2]
    assert rollbacks == []


@pytest.mark.asyncio
async def test_bounded_loop_reserves_budget_before_side_effecting_step() -> None:
    definition = BoundedLoopDefinition(
        loop_id="budgeted",
        entry_condition="needs repair",
        objective="passes",
        max_cycles=3,
        max_steps=3,
        steps=[{"action": "repair"}],
        allowed_resource_ids=[],
        allowed_capabilities=[],
        budget={"tokens": 15},
        verifier="compile",
        checkpoints=[],
        failure_policy="escalate",
        rollback_policy="none",
    )
    calls = 0

    async def step(_cycle: int, _index: int) -> None:
        nonlocal calls
        calls += 1

    async def reserve(_cycle: int, _index: int) -> dict[str, float]:
        return {"tokens": 8}

    async def never(_cycle: int) -> bool:
        return False

    result = await run_bounded_loop(
        definition, run_step=step, verify=never, reserve=reserve
    )
    assert result.state == "EXHAUSTED"
    assert result.exhaustion_reason == "budget:tokens"
    assert calls == 1
    assert result.budget_used["tokens"] == 8


def test_compiler_is_smallest_sufficient_and_budget_exhaustion_is_typed() -> None:
    mandatory = resource(content_excerpt="x" * 400)
    manifest = VEKLActivationManifest(
        manifest_id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        task_id=TASK,
        task_attempt_id=None,
        worker_run_id=None,
        task_signature_id=uuid4(),
        stack_fingerprint_id=FINGERPRINT,
        project_truth_hash="truth",
        stack_fingerprint_hash="stack",
        policy_hash="policy",
        selected_resources=[
            {
                "resource_id": str(mandatory.resource_id),
                "revision": mandatory.revision,
                "content_hash": mandatory.content_hash,
                "activation_mode": "READ_ONLY_CONTEXT",
            }
        ],
        tools=[],
        hooks=[],
        loops=[],
        community_evidence=[],
        freshness_state={},
        manifest_hash="manifest",
        created_at=NOW,
        updated_at=NOW,
    )
    with pytest.raises(BudgetExhaustedError) as caught:
        VEKLKnowledgeCompiler().compile(
            manifest=manifest,
            resources=[mandatory],
            truth_constraints={"required": "value"},
            token_budget=20,
        )
    assert caught.value.error_code == "BUDGET_EXCEEDED"


def test_compiler_delivers_truth_stack_tool_contracts_and_verifier_obligations() -> (
    None
):
    tool = resource(
        resource_kind="HOOK",
        component_kind="hook",
        lifecycle_state="PRODUCTION_QUALIFIED",
        activation_modes=["HOOK_ENFORCEMENT"],
        reuse_class="OPEN_REUSE",
        required_capabilities=["capability.run_local_process"],
        filesystem_scopes=["src/**"],
        required_verifiers=["hook-verifier"],
    )
    manifest = VEKLActivationManifest(
        manifest_id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        task_id=TASK,
        task_attempt_id=None,
        worker_run_id=None,
        task_signature_id=uuid4(),
        stack_fingerprint_id=FINGERPRINT,
        project_truth_hash="truth",
        stack_fingerprint_hash="stack",
        policy_hash="policy",
        selected_resources=[
            {
                "resource_id": str(tool.resource_id),
                "revision": tool.revision,
                "content_hash": tool.content_hash,
                "activation_mode": "HOOK_ENFORCEMENT",
                "reason": "mandatory",
                "mandatory": True,
            }
        ],
        tools=[],
        hooks=[],
        loops=[],
        community_evidence=[],
        freshness_state={str(tool.resource_id): {"stale": False}},
        manifest_hash="manifest",
        created_at=NOW,
        updated_at=NOW,
    )
    capsule = VEKLKnowledgeCompiler().compile(
        manifest=manifest,
        resources=[tool],
        truth_constraints={"requirement:ui": "React 19"},
        stack_facts={"versions": {"react": "19.2.8"}},
        task_verifiers=("pytest",),
        token_budget=500,
    )
    assert capsule.truth_constraints == {"requirement:ui": "React 19"}
    assert capsule.stack_facts == {"versions": {"react": "19.2.8"}}
    assert capsule.selection_reasons == (f"{tool.resource_id}:mandatory",)
    assert capsule.tool_contracts[0]["filesystem_scopes"] == ["src/**"]
    assert capsule.verifier_obligations == ("hook-verifier", "pytest")
    assert capsule.provenance_refs[0].endswith(f"#{tool.content_hash}")


def test_context_package_hash_binds_vekl_extension_provenance() -> None:
    mission_id = uuid4()
    base = assembly_hash(
        task_id=TASK,
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage={},
        included_items=(),
    )
    with_vekl = assembly_hash(
        task_id=TASK,
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage={},
        included_items=(),
        extensions=(
            ContextExtension(
                name="vekl",
                content_hash="c" * 64,
                token_estimate=42,
                provenance_refs=("vekl:r@1#hash",),
            ),
        ),
    )
    assert with_vekl != base


def test_hermes_has_candidate_only_boundary() -> None:
    result = VEKLService.hermes_candidate({"suggestion": "rank docs first"})
    assert result["authority"] == "CANDIDATE_ONLY"
    assert "truth" not in result
