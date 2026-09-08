"""Production VEKL engineering-playbook policy and Claude materialization tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from adapters.claude.vekl import (
    compile_claude_hook_settings,
    compile_claude_instruction_ir,
    compile_claude_skill,
)
from engine.contracts.hook_ir import HookIR
from engine.contracts.instruction_ir import InstructionIR
from engine.contracts.task import Task
from engine.contracts.vekl_activation_manifest import VEKLActivationManifest
from engine.contracts.vekl_resource import VEKLResource
from engine.core.errors import DdeError
from engine.vekl.compiler import VEKLKnowledgeCompiler
from engine.vekl.engineering_playbook import (
    ARCHETYPES,
    GATES,
    HOOK_POLICIES,
    MAX_ENGINEERING_PLAYBOOK_SKILLS,
    SKILLS,
    apply_engineering_playbook,
    build_orchestrator_policy,
    evaluate_completion_gates,
    materialize_hook_ir,
    resolve_required_skill_resources,
    skill_resource_specs,
)
from engine.vekl.models import TaskSignatureSpec

NOW = datetime.now(UTC)


def task(**changes: object) -> Task:
    values: dict[str, object] = {
        "task_id": uuid4(),
        "tenant_id": uuid4(),
        "project_id": uuid4(),
        "mission_id": uuid4(),
        "graph_id": uuid4(),
        "parent_task_id": None,
        "title": "Implement checkout",
        "intent": "Deliver the approved checkout behavior",
        "task_class": "implementation",
        "requirement_refs": ["REQ-checkout"],
        "feature_refs": ["CAP-checkout"],
        "success_criteria": ["checkout works end-to-end"],
        "expected_write_scope": ["src/checkout/**"],
        "expected_read_scope": ["src/**", "tests/**"],
        "blast_radius": "module",
        "risk_class": "medium",
        "estimated_effort": "m",
        "autonomy_ceiling": 3,
        "requires_approval": False,
        "verification_profile_ref": None,
        "status": "READY",
        "lock_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return Task.model_validate(values)


def signature_spec(archetype: str | None) -> TaskSignatureSpec:
    return TaskSignatureSpec(
        lifecycle_stage="implementation",
        engineering_archetype=archetype,
        constraints={"caller_constraint": "preserve"},
        required_verifiers=["pytest"],
        budget={"tokens": 2000},
    )


def manifest() -> VEKLActivationManifest:
    return VEKLActivationManifest(
        manifest_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        task_id=uuid4(),
        task_attempt_id=None,
        worker_run_id=None,
        task_signature_id=uuid4(),
        stack_fingerprint_id=uuid4(),
        project_truth_hash="truth",
        stack_fingerprint_hash="stack",
        policy_hash="policy",
        selected_resources=[],
        tools=[],
        hooks=[],
        loops=[],
        community_evidence=[],
        freshness_state={},
        manifest_hash="manifest",
        created_at=NOW,
        updated_at=NOW,
    )


def qualified_skill_resource(
    skill_id: str, *, revision: str | None = None
) -> VEKLResource:
    spec = SKILLS[skill_id].to_resource_spec()
    if revision is not None:
        spec = spec.model_copy(update={"revision": revision})
    return VEKLResource(
        resource_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        lifecycle_state="REFERENCE_QUALIFIED",
        injection_findings=[],
        created_at=NOW,
        updated_at=NOW,
        **spec.model_dump(),
    )


def instruction() -> InstructionIR:
    return InstructionIR(
        version="1",
        project_truth_hash="truth-hash",
        policy_hash="policy-hash",
        constraints=["Do not alter protected acceptance tests."],
        guidance=["Follow the selected repository pattern."],
        provenance_refs=["vekl:skill@1#abc"],
        content_hash="instruction-hash",
    )


def test_pattern_pack_has_no_egress_or_implicit_execution_authority() -> None:
    specs = skill_resource_specs()
    assert len(specs) == len(SKILLS)
    assert len(SKILLS) >= 16
    assert len(ARCHETYPES) >= 14
    assert len(GATES) >= 12
    assert len(HOOK_POLICIES) >= 7
    for spec in specs:
        assert spec.resource_kind == "SKILL"
        assert spec.source_uri is None
        assert spec.source_trust == "S2_FIRST_PARTY"
        assert spec.activation_modes == ["PROCEDURAL_GUIDANCE"]
        assert spec.side_effect_class == "PURE_READ"
        assert spec.required_capabilities == []
        assert spec.network_scopes == []
        assert spec.secret_scopes == []
        assert spec.provenance["activation_authority"] == "VEKLActivationManifest"
        assert spec.provenance["upstream_snapshot"] == "2026-09-08"


def test_engineering_skill_hash_is_stable_and_skill_specific() -> None:
    first = SKILLS["feature-delivery"]
    same = SKILLS["feature-delivery"]
    other = SKILLS["bug-root-cause"]
    assert first.content_hash == same.content_hash
    assert first.content_hash != other.content_hash


def test_archetype_is_explicit_and_must_match_canonical_task_class() -> None:
    with pytest.raises(DdeError) as caught:
        build_orchestrator_policy(
            task(task_class="documentation"), "feature-implementation"
        )
    assert caught.value.error_code == "VEKL_TASK_ARCHETYPE_INVALID"


def test_orchestrator_policy_keeps_authority_and_skill_activation_minimal() -> None:
    policy = build_orchestrator_policy(
        task(risk_class="high"), "feature-implementation", unattended=True
    )
    assert policy.authority == "NON_AUTHORITATIVE_ENGINEERING_GUIDANCE"
    assert policy.canon_wins is True
    assert policy.may_change_architecture is False
    assert policy.may_advance_gate is False
    assert policy.may_access_secrets is False
    assert len(policy.skill_ids) <= MAX_ENGINEERING_PLAYBOOK_SKILLS
    assert policy.max_skill_count == MAX_ENGINEERING_PLAYBOOK_SKILLS


def test_conditional_plan_uses_risk_blast_radius_and_effort() -> None:
    normal = build_orchestrator_policy(task(), "feature-implementation")
    assert normal.plan_required is False
    risky = build_orchestrator_policy(task(risk_class="high"), "feature-implementation")
    broad = build_orchestrator_policy(
        task(blast_radius="cross_module"), "feature-implementation"
    )
    large = build_orchestrator_policy(
        task(estimated_effort="l"), "feature-implementation"
    )
    assert risky.plan_required is True
    assert broad.plan_required is True
    assert large.plan_required is True


def test_two_failed_corrections_require_fresh_start() -> None:
    one = build_orchestrator_policy(
        task(), "feature-implementation", correction_failures=1
    )
    two = build_orchestrator_policy(
        task(), "feature-implementation", correction_failures=2
    )
    assert one.fresh_start_required is False
    assert two.fresh_start_required is True
    assert two.max_correction_failures_before_restart == 2


def test_high_risk_or_unattended_work_gets_fresh_adversarial_review() -> None:
    high = build_orchestrator_policy(task(risk_class="high"), "feature-implementation")
    unattended = build_orchestrator_policy(
        task(), "feature-implementation", unattended=True
    )
    for policy in (high, unattended):
        assert policy.fresh_reviewer_required is True
        assert "gate.fresh-review" in policy.completion_gate_ids
        assert "adversarial-review" in policy.skill_ids


def test_migration_and_bulk_work_are_strictly_governed() -> None:
    migration = build_orchestrator_policy(task(task_class="integration"), "migration")
    bulk = build_orchestrator_policy(task(), "bulk-migration")
    assert migration.plan_required is True
    assert migration.fresh_reviewer_required is True
    assert "gate.migration-reversible" in migration.completion_gate_ids
    assert bulk.parallelism_policy == "DISJOINT_WORKTREES_ONLY"
    assert bulk.plan_required is True


def test_apply_playbook_binds_policy_into_existing_signature_constraints() -> None:
    original = signature_spec("feature-implementation")
    updated, policy = apply_engineering_playbook(task(), original)
    assert policy is not None
    assert updated.constraints["caller_constraint"] == "preserve"
    assert updated.constraints["engineering_archetype"] == "feature-implementation"
    bound = updated.constraints["engineering_playbook"]
    assert isinstance(bound, dict)
    assert bound["require_evidence"] is True
    assert bound["prohibit_scope_thinning"] is True
    assert bound["prohibit_verifier_tampering"] is True

    unchanged, no_policy = apply_engineering_playbook(task(), signature_spec(None))
    assert no_policy is None
    assert unchanged.constraints == {"caller_constraint": "preserve"}


def test_engineering_policy_is_protected_context_and_hash_bound() -> None:
    compiler = VEKLKnowledgeCompiler()
    first = compiler.compile(
        manifest=manifest(),
        resources=[],
        truth_constraints={"requirement": "x"},
        token_budget=2000,
        stack_facts={"language": "python"},
        engineering_policy={"plan_required": False},
    )
    changed = compiler.compile(
        manifest=manifest(),
        resources=[],
        truth_constraints={"requirement": "x"},
        token_budget=2000,
        stack_facts={"language": "python"},
        engineering_policy={"plan_required": True},
    )
    assert first.engineering_policy == {"plan_required": False}
    assert first.capsule_hash != changed.capsule_hash


def test_required_playbook_skills_fail_closed_when_not_installed() -> None:
    updated, policy = apply_engineering_playbook(
        task(), signature_spec("feature-implementation")
    )
    assert policy is not None
    with pytest.raises(DdeError) as caught:
        resolve_required_skill_resources(
            signature_constraints=updated.constraints,
            resources=[],
            requested_modes=["PROCEDURAL_GUIDANCE"],
        )
    assert caught.value.error_code == "VEKL_RESOURCE_INELIGIBLE"
    assert "feature-specification" in caught.value.details["skills"]


def test_required_playbook_skills_require_procedural_guidance_mode() -> None:
    updated, policy = apply_engineering_playbook(
        task(), signature_spec("feature-implementation")
    )
    assert policy is not None
    resources = [qualified_skill_resource(skill_id) for skill_id in policy.skill_ids]
    with pytest.raises(DdeError) as caught:
        resolve_required_skill_resources(
            signature_constraints=updated.constraints,
            resources=resources,
            requested_modes=["READ_ONLY_CONTEXT"],
        )
    assert caught.value.error_code == "VEKL_RESOURCE_INELIGIBLE"


def test_required_playbook_skills_bind_exact_resources_deterministically() -> None:
    updated, policy = apply_engineering_playbook(
        task(), signature_spec("feature-implementation")
    )
    assert policy is not None
    resources = [qualified_skill_resource(skill_id) for skill_id in policy.skill_ids]
    duplicate = qualified_skill_resource(policy.skill_ids[0])
    resources.append(duplicate)
    expected_first = min(
        (
            item
            for item in resources
            if item.provenance["skill_id"] == policy.skill_ids[0]
        ),
        key=lambda item: str(item.resource_id),
    )
    resolved = resolve_required_skill_resources(
        signature_constraints=updated.constraints,
        resources=resources,
        requested_modes=["PROCEDURAL_GUIDANCE"],
    )
    assert len(resolved) == len(policy.skill_ids)
    assert resolved[0] == expected_first.resource_id


def test_required_playbook_skills_refuse_wrong_pack_revision() -> None:
    updated, policy = apply_engineering_playbook(
        task(), signature_spec("feature-implementation")
    )
    assert policy is not None
    resources = [
        qualified_skill_resource(skill_id, revision="stale-revision")
        for skill_id in policy.skill_ids
    ]
    with pytest.raises(DdeError) as caught:
        resolve_required_skill_resources(
            signature_constraints=updated.constraints,
            resources=resources,
            requested_modes=["PROCEDURAL_GUIDANCE"],
        )
    assert caught.value.error_code == "VEKL_RESOURCE_INELIGIBLE"


def test_hook_policy_materialization_never_invents_an_executable_action() -> None:
    with pytest.raises(DdeError) as caught:
        materialize_hook_ir("hook.scope-guard", matcher={"tool": "Edit|Write"})
    assert caught.value.error_code == "VEKL_HOOK_INVALID"

    hook = materialize_hook_ir(
        "hook.post-edit-fast-check",
        matcher={"tool": "Edit|Write"},
        command=["python3", "-m", "ruff", "check", "."],
        filesystem_scopes=["src/**"],
    )
    assert hook.command == ["python3", "-m", "ruff", "check", "."]
    assert hook.capability_id is None


def test_claude_skill_is_delivery_artifact_without_auto_activation_or_tool_grants() -> (
    None
):
    artifact = compile_claude_skill(SKILLS["feature-delivery"])
    assert artifact.relative_path == ".claude/skills/feature-delivery/SKILL.md"
    assert artifact.content.startswith("---\nname: feature-delivery\n")
    assert "disable-model-invocation: true" in artifact.content
    assert "allowed-tools:" not in artifact.content
    assert "Project Truth" in artifact.content


def test_claude_instruction_compiler_marks_generated_non_truth_artifact() -> None:
    rendered = compile_claude_instruction_ir(instruction())
    assert rendered.startswith("# DDE-generated Claude instructions")
    assert "compiled delivery artifact, not Project Truth" in rendered
    assert "truth-hash" in rendered
    assert "Do not alter protected acceptance tests." in rendered
    assert "vekl:skill@1#abc" in rendered


def test_claude_hook_compiler_maps_only_concrete_semantics_preserving_commands() -> (
    None
):
    hook = HookIR(
        hook_id="fast-check",
        hook_class="post_mutation",
        event="after_tool_use",
        matcher={"tool": "Edit|Write"},
        command=["python3", "tools/check style.py"],
        capability_id=None,
        filesystem_scopes=[],
        network_scopes=[],
        secret_scopes=[],
        timeout_seconds=45,
        failure_policy="BLOCK",
        evidence_types=["command_result"],
    )
    settings = compile_claude_hook_settings([hook])
    post = settings["hooks"]
    assert isinstance(post, dict)
    group = post["PostToolUse"]
    assert isinstance(group, list)
    assert group[0]["matcher"] == "Edit|Write"
    handler = group[0]["hooks"][0]
    assert handler["type"] == "command"
    assert handler["timeout"] == 45
    assert handler["command"] == "python3 'tools/check style.py'"

    capability_hook = hook.model_copy(
        update={"command": None, "capability_id": "capability.run_local_process"}
    )
    with pytest.raises(DdeError):
        compile_claude_hook_settings([capability_hook])

    unsupported = hook.model_copy(update={"event": "before_compact_or_pause"})
    with pytest.raises(DdeError):
        compile_claude_hook_settings([unsupported])

    stop_hook = hook.model_copy(update={"event": "before_stop", "matcher": {}})
    task_complete_hook = hook.model_copy(
        update={"event": "before_task_complete", "matcher": {}}
    )
    global_settings = compile_claude_hook_settings([stop_hook, task_complete_hook])
    global_hooks = global_settings["hooks"]
    assert isinstance(global_hooks, dict)
    assert "matcher" not in global_hooks["Stop"][0]
    assert "matcher" not in global_hooks["TaskCompleted"][0]


def test_completion_gate_checker_requires_verifier_evidence() -> None:
    policy = build_orchestrator_policy(task(), "feature-implementation")
    missing = evaluate_completion_gates(
        policy,
        satisfied_gate_ids=("gate.scope-integrity",),
        evidence_refs=(),
    )
    assert missing.complete is False
    assert "gate.evidence-required" in missing.missing_gate_ids
    assert "gate.requirement-coverage" in missing.missing_gate_ids

    complete = evaluate_completion_gates(
        policy,
        satisfied_gate_ids=policy.completion_gate_ids,
        evidence_refs=("verification:123",),
    )
    assert complete.complete is True
    assert complete.missing_gate_ids == ()
    assert complete.evidence_refs == ("verification:123",)
