"""Provider-neutral engineering playbook distilled into Production VEKL.

The upstream material that informed this pack is Anthropic's public Claude Code
prompt library, best-practices, Skills, hooks and subagent documentation as observed
on 2026-09-08.  This module does *not* install Claude configuration, grant egress, or
make provider documentation Project Truth.  It turns the reusable engineering
patterns into DDE-owned, content-addressed procedural resources and deterministic
execution policy that can be selected only through the ordinary VEKL activation law.

Provider-specific materialization belongs under ``adapters/**``.  In particular,
Claude Code's own automatic Skill selection is deliberately not an authority here:
DDE chooses VEKL resources, binds them into an ActivationManifest, and the harness
receives only that selected guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from engine.contracts.acceptance_oracle import AcceptanceOracle
from engine.contracts.hook_ir import HookIR
from engine.contracts.task import Task
from engine.contracts.vekl_resource import VEKLResource
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.vekl.models import TaskSignatureSpec, VEKLResourceSpec

PlanPolicy = Literal["DIRECT", "CONDITIONAL", "REQUIRED"]
ContextPolicy = Literal["MAIN", "ISOLATED_RESEARCH", "FRESH_IMPLEMENTATION"]
ReviewPolicy = Literal["NONE", "RISK_BASED", "ALWAYS"]
ParallelismPolicy = Literal["SERIAL", "INDEPENDENT_READS", "DISJOINT_WORKTREES_ONLY"]

MAX_ENGINEERING_PLAYBOOK_SKILLS = 3

PACK_ID = "dde.engineering-playbook.anthropic-patterns"
PACK_REVISION = "2026-09-08.1"
PACK_SOURCE_SNAPSHOT = "2026-09-08"

UPSTREAM_PROMPT_LIBRARY = "https://code.claude.com/docs/en/prompt-library"
UPSTREAM_BEST_PRACTICES = "https://code.claude.com/docs/en/best-practices"
UPSTREAM_SKILLS = "https://code.claude.com/docs/en/skills"
UPSTREAM_HOOKS = "https://code.claude.com/docs/en/hooks-guide"
UPSTREAM_SUBAGENTS = "https://code.claude.com/docs/en/sub-agents"
UPSTREAM_COMMON_WORKFLOWS = "https://code.claude.com/docs/en/common-workflows"
UPSTREAM_SOURCES = (
    UPSTREAM_PROMPT_LIBRARY,
    UPSTREAM_BEST_PRACTICES,
    UPSTREAM_SKILLS,
    UPSTREAM_HOOKS,
    UPSTREAM_SUBAGENTS,
    UPSTREAM_COMMON_WORKFLOWS,
)


@dataclass(frozen=True)
class EngineeringSkillDefinition:
    """DDE-owned procedural guidance that can materialize as a VEKL SKILL."""

    skill_id: str
    title: str
    description: str
    guidance: tuple[str, ...]
    archetypes: tuple[str, ...]
    read_only: bool = False
    source_refs: tuple[str, ...] = UPSTREAM_SOURCES

    @property
    def body(self) -> str:
        return "\n".join(self.guidance)

    @property
    def content_hash(self) -> str:
        return sha256_hex(
            canonical_json(
                {
                    "pack_id": PACK_ID,
                    "revision": PACK_REVISION,
                    "skill_id": self.skill_id,
                    "title": self.title,
                    "description": self.description,
                    "guidance": list(self.guidance),
                    "source_refs": list(self.source_refs),
                }
            )
        )

    def to_resource_spec(self) -> VEKLResourceSpec:
        """Return a no-egress, non-executable VEKL resource candidate.

        The resource is a DDE-authored paraphrase.  Upstream URLs are provenance
        pointers only; ``source_uri`` remains null so registering this pack cannot
        silently create network authority.  Normal VEKL lifecycle qualification is
        still required before the resource can be activated.
        """

        estimated_tokens = max(1, len(self.body) // 4)
        return VEKLResourceSpec(
            resource_kind="SKILL",
            title=self.title,
            publisher="DDE",
            source_uri=None,
            revision=PACK_REVISION,
            content_hash=self.content_hash,
            source_trust="S2_FIRST_PARTY",
            reuse_class="OPEN_REUSE",
            activation_modes=["PROCEDURAL_GUIDANCE"],
            license_ids=["DDE_PROJECT"],
            provenance={
                "source": PACK_ID,
                "skill_id": self.skill_id,
                "purpose": f"engineering_skill:{self.skill_id}",
                "hash_verified": True,
                "offline_pin_available": True,
                "upstream_sources": list(self.source_refs),
                "upstream_snapshot": PACK_SOURCE_SNAPSHOT,
                "derivation": "DDE-authored provider-neutral paraphrase",
                "activation_authority": "VEKLActivationManifest",
                "caveats": [
                    "upstream provider guidance is advisory",
                    "Project Truth and DDE policy always outrank this skill",
                ],
            },
            required_capabilities=[],
            filesystem_scopes=[],
            network_scopes=[],
            secret_scopes=[],
            sandbox_requirements={},
            side_effect_class="PURE_READ",
            required_verifiers=[],
            stack_constraints={},
            truth_constraints={},
            freshness={"stale": False, "snapshot": PACK_SOURCE_SNAPSHOT},
            budget={"tokens": estimated_tokens},
            content_excerpt=self.body,
        )


@dataclass(frozen=True)
class VerificationGateDefinition:
    """A completion obligation, not a second AcceptanceOracle authority."""

    gate_id: str
    description: str
    blocking: bool
    evidence_kinds: tuple[str, ...]


@dataclass(frozen=True)
class HookPolicyDefinition:
    """Harness-neutral hook intent; executable commands are materialized later."""

    hook_id: str
    hook_class: str
    event: str
    description: str
    failure_policy: Literal["BLOCK", "WARN", "ESCALATE"]
    evidence_types: tuple[str, ...]


@dataclass(frozen=True)
class TaskArchetypeDefinition:
    """VEKL engineering archetype layered over the canonical DDE Task class."""

    archetype_id: str
    title: str
    compatible_task_classes: tuple[str, ...]
    primary_skill_ids: tuple[str, ...]
    gate_ids: tuple[str, ...]
    hook_ids: tuple[str, ...]
    plan_policy: PlanPolicy
    context_policy: ContextPolicy
    review_policy: ReviewPolicy
    parallelism_policy: ParallelismPolicy


@dataclass(frozen=True)
class CompletionGateDecision:
    """Result of checking DDE verifier/oracle gate attestations."""

    complete: bool
    required_gate_ids: tuple[str, ...]
    satisfied_gate_ids: tuple[str, ...]
    missing_gate_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class OrchestratorExecutionPolicy:
    """Deterministic policy compiled from Task + selected engineering archetype."""

    archetype_id: str
    plan_required: bool
    fresh_start_required: bool
    fresh_reviewer_required: bool
    investigation_context: ContextPolicy
    parallelism_policy: ParallelismPolicy
    max_correction_failures_before_restart: int
    completion_gate_ids: tuple[str, ...]
    skill_ids: tuple[str, ...]
    hook_ids: tuple[str, ...]
    require_evidence: bool = True
    prohibit_scope_thinning: bool = True
    prohibit_verifier_tampering: bool = True
    authority: str = "NON_AUTHORITATIVE_ENGINEERING_GUIDANCE"
    canon_wins: bool = True
    may_change_architecture: bool = False
    may_advance_gate: bool = False
    may_access_secrets: bool = False
    max_skill_count: int = MAX_ENGINEERING_PLAYBOOK_SKILLS

    def as_dict(self) -> dict[str, object]:
        return {
            "archetype_id": self.archetype_id,
            "plan_required": self.plan_required,
            "fresh_start_required": self.fresh_start_required,
            "fresh_reviewer_required": self.fresh_reviewer_required,
            "investigation_context": self.investigation_context,
            "parallelism_policy": self.parallelism_policy,
            "max_correction_failures_before_restart": (
                self.max_correction_failures_before_restart
            ),
            "completion_gate_ids": list(self.completion_gate_ids),
            "skill_ids": list(self.skill_ids),
            "hook_ids": list(self.hook_ids),
            "require_evidence": self.require_evidence,
            "prohibit_scope_thinning": self.prohibit_scope_thinning,
            "prohibit_verifier_tampering": self.prohibit_verifier_tampering,
            "authority": self.authority,
            "canon_wins": self.canon_wins,
            "may_change_architecture": self.may_change_architecture,
            "may_advance_gate": self.may_advance_gate,
            "may_access_secrets": self.may_access_secrets,
            "max_skill_count": self.max_skill_count,
        }


SKILLS: dict[str, EngineeringSkillDefinition] = {
    "repo-orientation": EngineeringSkillDefinition(
        skill_id="repo-orientation",
        title="Repository orientation",
        description="Understand an unfamiliar target repository without changing it.",
        archetypes=("orientation",),
        read_only=True,
        guidance=(
            (
                "Start broad: identify Project Truth, entry points, manifests, "
                "tests, and major modules."
            ),
            (
                "Narrow only after the architecture map is evidence-backed by "
                "real files and symbols."
            ),
            (
                "Trace one representative end-to-end path before drawing "
                "architectural conclusions."
            ),
            (
                "Return file/symbol references, boundaries, invariants, unknowns, "
                "and the smallest next read set."
            ),
            "Do not edit, install dependencies, or turn discovery into implementation.",
        ),
    ),
    "locate-behavior": EngineeringSkillDefinition(
        skill_id="locate-behavior",
        title="Locate and trace behavior",
        description=(
            "Find where a behavior is owned and trace its production call path."
        ),
        archetypes=("orientation", "incident-triage", "compile-runtime-debug"),
        read_only=True,
        guidance=(
            (
                "Search by the concrete symptom, API, event, symbol, error "
                "signature, and observable output."
            ),
            (
                "Trace callers, writers, readers, state transitions, and tests "
                "instead of stopping at the first match."
            ),
            "Use history only when current code cannot explain why the shape exists.",
            (
                "Report the owning boundary and evidence; separate proven facts "
                "from hypotheses."
            ),
        ),
    ),
    "feature-specification": EngineeringSkillDefinition(
        skill_id="feature-specification",
        title="Feature specification",
        description=(
            "Turn an incomplete feature request into an "
            "implementable, verifiable contract."
        ),
        archetypes=("feature-implementation", "ui-visual-delivery"),
        read_only=True,
        guidance=(
            (
                "Resolve hard ambiguities before coding; do not invent missing "
                "product decisions."
            ),
            (
                "Bind scope to requirement/feature refs, existing interfaces, "
                "data/state boundaries, and reference patterns."
            ),
            (
                "Name what is explicitly out of scope and the failure/edge cases "
                "that materially affect correctness."
            ),
            (
                "Finish with observable end-to-end verification criteria and the "
                "evidence each criterion requires."
            ),
            (
                "Escalate unresolved authority questions as decisions rather than "
                "burying assumptions in code."
            ),
        ),
    ),
    "feature-delivery": EngineeringSkillDefinition(
        skill_id="feature-delivery",
        title="Feature delivery",
        description=(
            "Implement a feature from Project Truth through executable verification."
        ),
        archetypes=("feature-implementation",),
        guidance=(
            (
                "Describe and preserve the outcome, constraints, and acceptance "
                "evidence; do not micromanage file edits."
            ),
            (
                "Explore and plan first when the task is uncertain, multi-file, "
                "cross-module, high-risk, or unfamiliar."
            ),
            (
                "Match proven repository patterns before introducing a new "
                "abstraction or dependency."
            ),
            (
                "Implement the smallest complete vertical slice, then run focused "
                "checks and applicable broader regression checks."
            ),
            (
                "Do not claim completion from code inspection; attach runnable "
                "evidence for every acceptance criterion."
            ),
        ),
    ),
    "bug-root-cause": EngineeringSkillDefinition(
        skill_id="bug-root-cause",
        title="Root-cause bug repair",
        description=(
            "Reproduce a defect, fix its cause, and prove the regression is closed."
        ),
        archetypes=("compile-runtime-debug", "incident-triage"),
        guidance=(
            (
                "Capture the exact symptom, error/log/artifact, environment, and "
                "whether reproduction is deterministic."
            ),
            (
                "Create or identify a failing check that reproduces the defect "
                "before changing production behavior when feasible."
            ),
            (
                "Trace to the root cause; do not suppress errors, weaken tests, "
                "or mask the symptom."
            ),
            (
                "Make the narrowest complete fix and add regression coverage for "
                "the failing case and relevant edge cases."
            ),
            (
                "Run the reproducer plus affected regression checks and preserve "
                "the outputs as evidence."
            ),
        ),
    ),
    "behavior-preserving-refactor": EngineeringSkillDefinition(
        skill_id="behavior-preserving-refactor",
        title="Behavior-preserving refactor",
        description=(
            "Improve structure while mechanically preserving "
            "externally observable behavior."
        ),
        archetypes=("refactor",),
        guidance=(
            (
                "Capture a green behavioral baseline and define the behavior that "
                "must remain invariant."
            ),
            (
                "Refactor in small reviewable increments using existing patterns "
                "unless Project Truth requires a change."
            ),
            (
                "Do not combine cleanup with feature changes, dependency "
                "upgrades, or acceptance weakening."
            ),
            (
                "Run focused equivalence/regression checks after each meaningful "
                "increment and the broader applicable suite at the end."
            ),
            (
                "Treat any behavior delta as a feature/decision change requiring "
                "separate authority."
            ),
        ),
    ),
    "test-expansion": EngineeringSkillDefinition(
        skill_id="test-expansion",
        title="Test expansion",
        description=(
            "Add meaningful coverage that follows existing test "
            "patterns and checks behavior."
        ),
        archetypes=("testing",),
        guidance=(
            (
                "Identify the behavior or risk that is currently unproven; do not "
                "chase coverage percentage alone."
            ),
            (
                "Follow existing fixture, naming, isolation, and assertion "
                "patterns unless they are themselves the defect."
            ),
            (
                "Cover the happy path, meaningful boundary/negative cases, and "
                "the reported regression where applicable."
            ),
            (
                "Prefer observable outputs and state over implementation-detail "
                "assertions."
            ),
            (
                "Run the new tests first, then the affected suite, and report "
                "evidence rather than saying tests should pass."
            ),
        ),
    ),
    "documentation-update": EngineeringSkillDefinition(
        skill_id="documentation-update",
        title="Implementation-backed documentation",
        description=(
            "Update target-product docs so they describe verified "
            "behavior without overclaiming."
        ),
        archetypes=("documentation",),
        guidance=(
            (
                "Read the implementation, contracts, and verification evidence "
                "before changing documentation."
            ),
            (
                "Document the supported path, constraints, failure modes, and "
                "examples that can actually be exercised."
            ),
            (
                "Do not turn plans, placeholders, or provider marketing language "
                "into claims of implemented behavior."
            ),
            (
                "Run documentation checks and validate commands/examples when a "
                "deterministic verifier exists."
            ),
        ),
    ),
    "ui-visual-verification": EngineeringSkillDefinition(
        skill_id="ui-visual-verification",
        title="UI delivery with visual verification",
        description=(
            "Implement UI against a visual/product reference and "
            "verify the live product."
        ),
        archetypes=("ui-visual-delivery",),
        guidance=(
            (
                "Bind the change to the promoted design/reference, required "
                "states, breakpoints, tokens, and accessibility constraints."
            ),
            (
                "Implement in the real product runtime; prototype or artboard "
                "output is not implementation evidence."
            ),
            (
                "Capture the live result at required viewports and compare "
                "structure, spacing, clipping, focus, contrast, and interaction "
                "states."
            ),
            (
                "Use visual critique only after deterministic "
                "functional/accessibility checks; subjective polish cannot "
                "override hard failures."
            ),
            (
                "Iterate through a bounded repair loop and stop only on verifier "
                "evidence or explicit escalation."
            ),
        ),
    ),
    "schema-migration": EngineeringSkillDefinition(
        skill_id="schema-migration",
        title="Schema and data migration",
        description=(
            "Deliver a migration with compatibility, "
            "rollback/recovery, and schema verification."
        ),
        archetypes=("migration",),
        guidance=(
            (
                "Read current schema, data access paths, deployment order, "
                "compatibility window, and existing migration conventions first."
            ),
            (
                "Write the forward migration and an explicit rollback/recovery "
                "strategy before treating the change as safe."
            ),
            (
                "Exercise the migration against an appropriate disposable "
                "environment and verify the resulting schema/data invariants."
            ),
            "Test old/new compatibility where rolling deployment can overlap versions.",
            (
                "Never mark a migration complete from generated SQL alone when "
                "the required live/reversible gate is unavailable."
            ),
        ),
    ),
    "security-remediation": EngineeringSkillDefinition(
        skill_id="security-remediation",
        title="Security remediation",
        description=(
            "Remediate a concrete security finding without broadening "
            "authority or hiding evidence."
        ),
        archetypes=("dependency-security-remediation",),
        guidance=(
            (
                "Bind the work to the exact advisory/finding, affected "
                "version/path, threat model, and required security verifier."
            ),
            (
                "Prefer the smallest compatible upgrade or code fix; do not move "
                "lockfiles to latest without qualification."
            ),
            (
                "Preserve capability, filesystem, network, secret, tenant, and "
                "data-egress boundaries while repairing the issue."
            ),
            (
                "Run the relevant security scan plus functional regression checks "
                "and retain before/after evidence."
            ),
            (
                "Use an independent fresh-context review for material auth, "
                "secret, boundary, or supply-chain changes."
            ),
        ),
    ),
    "performance-target": EngineeringSkillDefinition(
        skill_id="performance-target",
        title="Measured performance improvement",
        description=(
            "Improve a named performance metric against a measurable threshold."
        ),
        archetypes=("performance",),
        guidance=(
            (
                "Record a reproducible baseline, workload, environment, metric, "
                "and target threshold before optimizing."
            ),
            (
                "Profile the bottleneck; do not optimize by intuition when "
                "measurement is available."
            ),
            "Change one causal area at a time and preserve functional correctness.",
            (
                "Re-run the benchmark under comparable conditions and report both "
                "target metric and regressions."
            ),
        ),
    ),
    "observability-delivery": EngineeringSkillDefinition(
        skill_id="observability-delivery",
        title="Observability delivery",
        description=(
            "Add diagnostics that prove useful state without leaking "
            "secrets or private data."
        ),
        archetypes=("observability",),
        guidance=(
            (
                "Define the operational question the telemetry must answer and "
                "the failure/recovery path it supports."
            ),
            (
                "Use existing event/log/metric conventions and stable "
                "identifiers; avoid duplicate truth stores."
            ),
            (
                "Minimize sensitive payloads and preserve tenant/project "
                "boundaries and retention policy."
            ),
            (
                "Verify emission, query/read path, failure behavior, and operator "
                "usefulness in a realistic environment."
            ),
        ),
    ),
    "release-readiness": EngineeringSkillDefinition(
        skill_id="release-readiness",
        title="Release readiness",
        description=(
            "Decide release readiness from required evidence, not "
            "implementation self-report."
        ),
        archetypes=("release",),
        read_only=True,
        guidance=(
            (
                "Enumerate the release's required functional, integration, "
                "security, migration, packaging, and operational gates from "
                "Project Truth."
            ),
            (
                "Resolve each gate to attributable evidence for the exact "
                "candidate revision/environment."
            ),
            "Treat unavailable mandatory evidence as unavailable, never as pass.",
            (
                "Report blocking gaps, residual risk, rollback/recovery "
                "readiness, and the highest truthful realization state."
            ),
            (
                "Do not certify based on worker assertions, green unit tests "
                "alone, or stale evidence from an invalidated dependency."
            ),
        ),
    ),
    "bulk-migration-pilot": EngineeringSkillDefinition(
        skill_id="bulk-migration-pilot",
        title="Pilot-first bulk migration",
        description="Pilot a repetitive migration before bounded parallel fan-out.",
        archetypes=("bulk-migration",),
        guidance=(
            (
                "Inventory the exact target set and define a machine-readable "
                "per-item success/failure result."
            ),
            (
                "Run a small representative pilot first and refine the recipe "
                "from observed failures before broad fan-out."
            ),
            (
                "Parallelize only independent items with disjoint write "
                "ownership/worktrees and bounded tool/capability scopes."
            ),
            (
                "Aggregate per-item evidence, retry only safe/idempotent "
                "failures, and run a final repository-wide verifier."
            ),
        ),
    ),
    "adversarial-review": EngineeringSkillDefinition(
        skill_id="adversarial-review",
        title="Fresh-context adversarial review",
        description=(
            "Independently inspect a diff against criteria and report "
            "correctness gaps only."
        ),
        archetypes=(
            "feature-implementation",
            "ui-visual-delivery",
            "migration",
            "dependency-security-remediation",
            "release",
            "performance",
            "refactor",
        ),
        read_only=True,
        guidance=(
            (
                "Review in a fresh isolated context using the diff, "
                "requirements/plan, and acceptance criteria as primary inputs."
            ),
            (
                "Try to falsify correctness, requirement coverage, edge-case "
                "handling, security boundaries, and scope integrity."
            ),
            (
                "Report concrete gaps with evidence; do not reward or repeat the "
                "implementer's reasoning."
            ),
            (
                "Do not manufacture style preferences or speculative abstractions "
                "as blockers."
            ),
            (
                "Separate blocking correctness findings from optional "
                "maintainability suggestions."
            ),
        ),
    ),
}


GATES: dict[str, VerificationGateDefinition] = {
    "gate.scope-integrity": VerificationGateDefinition(
        "gate.scope-integrity",
        "Changed files/effects stay within declared task/change-packet scope.",
        True,
        ("diff_gate_report", "staging_manifest"),
    ),
    "gate.evidence-required": VerificationGateDefinition(
        "gate.evidence-required",
        "Completion claims are backed by attributable verifier outputs.",
        True,
        ("verification_run", "evidence"),
    ),
    "gate.regression": VerificationGateDefinition(
        "gate.regression",
        (
            "Applicable focused and broader regression checks pass for the exact "
            "candidate."
        ),
        True,
        ("test", "build", "invariant"),
    ),
    "gate.requirement-coverage": VerificationGateDefinition(
        "gate.requirement-coverage",
        (
            "Each applicable requirement/acceptance criterion has implementation "
            "and evidence."
        ),
        True,
        ("acceptance_oracle", "verification_run"),
    ),
    "gate.root-cause-reproduction": VerificationGateDefinition(
        "gate.root-cause-reproduction",
        (
            "The original defect is reproduced or otherwise mechanically "
            "characterized, then closed."
        ),
        True,
        ("regression_test", "failure_signature", "verification_run"),
    ),
    "gate.behavior-equivalence": VerificationGateDefinition(
        "gate.behavior-equivalence",
        "A refactor preserves the declared externally observable baseline.",
        True,
        ("baseline", "regression_test", "invariant"),
    ),
    "gate.visual-live": VerificationGateDefinition(
        "gate.visual-live",
        (
            "The real product passes functional, responsive, accessibility, and "
            "visual checks."
        ),
        True,
        ("visual_diff", "silhouette", "visual_critique", "accessibility"),
    ),
    "gate.migration-reversible": VerificationGateDefinition(
        "gate.migration-reversible",
        (
            "Migration forward/compatibility/recovery behavior is exercised in "
            "the required environment."
        ),
        True,
        ("db_assertion", "migration_run", "rollback_or_recovery"),
    ),
    "gate.security": VerificationGateDefinition(
        "gate.security",
        (
            "Applicable security/advisory checks and authority boundaries remain "
            "satisfied."
        ),
        True,
        ("security_scan", "advisory_evidence", "independent_review"),
    ),
    "gate.performance-target": VerificationGateDefinition(
        "gate.performance-target",
        (
            "Measured candidate performance meets the declared target without "
            "correctness regression."
        ),
        True,
        ("benchmark", "baseline", "regression_test"),
    ),
    "gate.fresh-review": VerificationGateDefinition(
        "gate.fresh-review",
        (
            "A fresh-context reviewer independently checks correctness and scope "
            "when policy requires it."
        ),
        True,
        ("independent_review",),
    ),
    "gate.release-certification": VerificationGateDefinition(
        "gate.release-certification",
        (
            "All mandatory release gates are evidence-backed for the exact "
            "release candidate."
        ),
        True,
        ("capability_certification", "release_evidence"),
    ),
}


HOOK_POLICIES: dict[str, HookPolicyDefinition] = {
    "hook.scope-guard": HookPolicyDefinition(
        "hook.scope-guard",
        "pre_mutation",
        "before_tool_use",
        "Block writes/effects outside the Task/ChangePacket declared scope.",
        "BLOCK",
        ("scope_decision",),
    ),
    "hook.protected-verifier-guard": HookPolicyDefinition(
        "hook.protected-verifier-guard",
        "pre_mutation",
        "before_tool_use",
        "Block implementation workers from mutating protected verifier/oracle truth.",
        "BLOCK",
        ("scope_decision", "test_scope_assessment"),
    ),
    "hook.post-edit-fast-check": HookPolicyDefinition(
        "hook.post-edit-fast-check",
        "post_mutation",
        "after_tool_use",
        "Run the stack-qualified fast formatter/lint/type check after relevant edits.",
        "BLOCK",
        ("command_result",),
    ),
    "hook.working-tree-audit": HookPolicyDefinition(
        "hook.working-tree-audit",
        "completion",
        "before_stop",
        (
            "Scan the complete working tree so shell-written and untracked files "
            "cannot evade scope review."
        ),
        "BLOCK",
        ("diff_gate_report",),
    ),
    "hook.completion-gate": HookPolicyDefinition(
        "hook.completion-gate",
        "completion",
        "before_task_complete",
        (
            "Refuse task completion while blocking verification obligations lack "
            "valid evidence."
        ),
        "BLOCK",
        ("verification_run", "evidence_validity"),
    ),
    "hook.context-checkpoint": HookPolicyDefinition(
        "hook.context-checkpoint",
        "continuation",
        "before_compact_or_pause",
        (
            "Persist/reinject protected Project Truth, plan, current state, and "
            "do-not-repeat facts at context boundaries."
        ),
        "BLOCK",
        ("continuation_package",),
    ),
    "hook.external-effect-approval": HookPolicyDefinition(
        "hook.external-effect-approval",
        "pre_effect",
        "before_tool_use",
        (
            "Require ordinary DDE approval/capability/external-effect journaling "
            "before risky external effects."
        ),
        "BLOCK",
        ("capability_lease", "external_effect"),
    ),
}


ARCHETYPES: dict[str, TaskArchetypeDefinition] = {
    "orientation": TaskArchetypeDefinition(
        "orientation",
        "Repository orientation",
        ("discovery",),
        ("repo-orientation", "locate-behavior"),
        ("gate.evidence-required",),
        ("hook.context-checkpoint",),
        "DIRECT",
        "ISOLATED_RESEARCH",
        "NONE",
        "INDEPENDENT_READS",
    ),
    "feature-implementation": TaskArchetypeDefinition(
        "feature-implementation",
        "Feature implementation",
        ("specification", "implementation", "integration"),
        ("feature-specification", "feature-delivery"),
        ("gate.requirement-coverage", "gate.regression"),
        (
            "hook.scope-guard",
            "hook.post-edit-fast-check",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "CONDITIONAL",
        "MAIN",
        "RISK_BASED",
        "SERIAL",
    ),
    "ui-visual-delivery": TaskArchetypeDefinition(
        "ui-visual-delivery",
        "UI and visual delivery",
        ("specification", "implementation", "integration", "verification"),
        ("feature-specification", "ui-visual-verification"),
        ("gate.requirement-coverage", "gate.visual-live", "gate.regression"),
        (
            "hook.scope-guard",
            "hook.post-edit-fast-check",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "CONDITIONAL",
        "MAIN",
        "RISK_BASED",
        "SERIAL",
    ),
    "compile-runtime-debug": TaskArchetypeDefinition(
        "compile-runtime-debug",
        "Compile/runtime debug",
        ("discovery", "repair", "implementation", "verification"),
        ("locate-behavior", "bug-root-cause"),
        ("gate.root-cause-reproduction", "gate.regression"),
        ("hook.scope-guard", "hook.working-tree-audit", "hook.completion-gate"),
        "CONDITIONAL",
        "ISOLATED_RESEARCH",
        "RISK_BASED",
        "SERIAL",
    ),
    "incident-triage": TaskArchetypeDefinition(
        "incident-triage",
        "Incident triage and repair",
        ("discovery", "repair", "decision", "implementation", "verification"),
        ("locate-behavior", "bug-root-cause"),
        ("gate.root-cause-reproduction", "gate.regression"),
        (
            "hook.scope-guard",
            "hook.external-effect-approval",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "REQUIRED",
        "ISOLATED_RESEARCH",
        "RISK_BASED",
        "SERIAL",
    ),
    "refactor": TaskArchetypeDefinition(
        "refactor",
        "Behavior-preserving refactor",
        ("implementation", "integration", "verification"),
        ("behavior-preserving-refactor",),
        ("gate.behavior-equivalence", "gate.regression"),
        (
            "hook.scope-guard",
            "hook.post-edit-fast-check",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "CONDITIONAL",
        "MAIN",
        "RISK_BASED",
        "SERIAL",
    ),
    "testing": TaskArchetypeDefinition(
        "testing",
        "Testing and verification",
        ("verification", "implementation"),
        ("test-expansion",),
        ("gate.regression",),
        (
            "hook.scope-guard",
            "hook.protected-verifier-guard",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "DIRECT",
        "MAIN",
        "NONE",
        "SERIAL",
    ),
    "documentation": TaskArchetypeDefinition(
        "documentation",
        "Documentation",
        ("documentation",),
        ("documentation-update",),
        ("gate.requirement-coverage",),
        ("hook.scope-guard", "hook.working-tree-audit", "hook.completion-gate"),
        "DIRECT",
        "MAIN",
        "NONE",
        "SERIAL",
    ),
    "migration": TaskArchetypeDefinition(
        "migration",
        "Schema/data migration",
        ("specification", "implementation", "integration", "verification"),
        ("schema-migration",),
        ("gate.migration-reversible", "gate.regression", "gate.fresh-review"),
        (
            "hook.scope-guard",
            "hook.external-effect-approval",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "REQUIRED",
        "MAIN",
        "ALWAYS",
        "SERIAL",
    ),
    "dependency-security-remediation": TaskArchetypeDefinition(
        "dependency-security-remediation",
        "Dependency/security remediation",
        (
            "discovery",
            "decision",
            "implementation",
            "integration",
            "verification",
            "repair",
        ),
        ("security-remediation",),
        ("gate.security", "gate.regression", "gate.fresh-review"),
        (
            "hook.scope-guard",
            "hook.external-effect-approval",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "REQUIRED",
        "MAIN",
        "ALWAYS",
        "SERIAL",
    ),
    "performance": TaskArchetypeDefinition(
        "performance",
        "Performance improvement",
        ("discovery", "implementation", "verification"),
        ("performance-target",),
        ("gate.performance-target", "gate.regression"),
        ("hook.scope-guard", "hook.working-tree-audit", "hook.completion-gate"),
        "CONDITIONAL",
        "ISOLATED_RESEARCH",
        "RISK_BASED",
        "SERIAL",
    ),
    "observability": TaskArchetypeDefinition(
        "observability",
        "Observability implementation",
        ("specification", "implementation", "integration", "verification"),
        ("observability-delivery",),
        ("gate.requirement-coverage", "gate.regression"),
        (
            "hook.scope-guard",
            "hook.external-effect-approval",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "CONDITIONAL",
        "MAIN",
        "RISK_BASED",
        "SERIAL",
    ),
    "release": TaskArchetypeDefinition(
        "release",
        "Release readiness",
        ("verification", "decision", "integration"),
        ("release-readiness",),
        ("gate.release-certification", "gate.fresh-review"),
        ("hook.external-effect-approval", "hook.completion-gate"),
        "REQUIRED",
        "FRESH_IMPLEMENTATION",
        "ALWAYS",
        "SERIAL",
    ),
    "bulk-migration": TaskArchetypeDefinition(
        "bulk-migration",
        "Pilot-first bulk migration",
        ("implementation", "integration", "verification"),
        ("bulk-migration-pilot",),
        ("gate.scope-integrity", "gate.regression", "gate.fresh-review"),
        (
            "hook.scope-guard",
            "hook.post-edit-fast-check",
            "hook.working-tree-audit",
            "hook.completion-gate",
        ),
        "REQUIRED",
        "FRESH_IMPLEMENTATION",
        "ALWAYS",
        "DISJOINT_WORKTREES_ONLY",
    ),
}

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_BLAST_ORDER = {"none": 0, "local": 1, "module": 2, "cross_module": 3, "systemic": 4}


def get_archetype(archetype_id: str) -> TaskArchetypeDefinition:
    try:
        return ARCHETYPES[archetype_id]
    except KeyError as exc:
        raise DdeError(
            "VEKL_TASK_ARCHETYPE_INVALID",
            "unknown VEKL engineering task archetype",
            details={"archetype_id": archetype_id, "allowed": sorted(ARCHETYPES)},
        ) from exc


def validate_archetype_for_task(
    task: Task, archetype_id: str
) -> TaskArchetypeDefinition:
    archetype = get_archetype(archetype_id)
    if task.task_class not in archetype.compatible_task_classes:
        raise DdeError(
            "VEKL_TASK_ARCHETYPE_INVALID",
            "engineering task archetype is incompatible with canonical Task.task_class",
            details={
                "archetype_id": archetype_id,
                "task_class": task.task_class,
                "compatible_task_classes": list(archetype.compatible_task_classes),
            },
        )
    return archetype


def _plan_required(task: Task, archetype: TaskArchetypeDefinition) -> bool:
    if archetype.plan_policy == "REQUIRED":
        return True
    if archetype.plan_policy == "DIRECT":
        return False
    return (
        _RISK_ORDER[task.risk_class] >= _RISK_ORDER["high"]
        or _BLAST_ORDER[task.blast_radius] >= _BLAST_ORDER["cross_module"]
        or task.estimated_effort == "l"
    )


def _review_required(
    task: Task, archetype: TaskArchetypeDefinition, *, unattended: bool
) -> bool:
    if archetype.review_policy == "ALWAYS":
        return True
    if archetype.review_policy == "NONE":
        return False
    return (
        unattended
        or _RISK_ORDER[task.risk_class] >= _RISK_ORDER["high"]
        or _BLAST_ORDER[task.blast_radius] >= _BLAST_ORDER["cross_module"]
    )


def build_orchestrator_policy(
    task: Task,
    archetype_id: str,
    *,
    correction_failures: int = 0,
    unattended: bool = False,
) -> OrchestratorExecutionPolicy:
    """Compile task-specific execution policy without provider/model heuristics."""

    if correction_failures < 0:
        raise ValueError("correction_failures must be non-negative")
    archetype = validate_archetype_for_task(task, archetype_id)
    gates = ["gate.evidence-required"]
    if task.task_class not in {"discovery", "decision"}:
        gates.append("gate.scope-integrity")
    gates.extend(archetype.gate_ids)
    fresh_reviewer = _review_required(task, archetype, unattended=unattended)
    if fresh_reviewer:
        gates.append("gate.fresh-review")
    skill_ids = list(archetype.primary_skill_ids)
    if fresh_reviewer and "adversarial-review" not in skill_ids:
        skill_ids.append("adversarial-review")
    skill_ids = list(dict.fromkeys(skill_ids))
    if len(skill_ids) > MAX_ENGINEERING_PLAYBOOK_SKILLS:
        raise DdeError(
            "VEKL_SKILL_BUDGET_EXCEEDED",
            "engineering archetype exceeds the minimal Skill activation budget",
            details={
                "archetype_id": archetype.archetype_id,
                "skill_ids": skill_ids,
                "max_skill_count": MAX_ENGINEERING_PLAYBOOK_SKILLS,
            },
        )
    return OrchestratorExecutionPolicy(
        archetype_id=archetype.archetype_id,
        plan_required=_plan_required(task, archetype),
        fresh_start_required=correction_failures >= 2,
        fresh_reviewer_required=fresh_reviewer,
        investigation_context=archetype.context_policy,
        parallelism_policy=archetype.parallelism_policy,
        max_correction_failures_before_restart=2,
        completion_gate_ids=tuple(dict.fromkeys(gates)),
        skill_ids=tuple(skill_ids),
        hook_ids=tuple(dict.fromkeys(archetype.hook_ids)),
    )


def orchestrator_policy_from_constraints(
    task: Task, constraints: dict[str, object]
) -> OrchestratorExecutionPolicy | None:
    """Strictly reconstruct a persisted DDE engineering policy.

    The TaskSignature is authoritative for the selected playbook revision, but JSON
    constraints are still validated before execution/verification consumes them.
    Unknown resources, gates, hooks, enum values or weakened guard-capsule fields fail
    closed instead of being interpreted permissively.
    """

    raw = constraints.get("engineering_playbook")
    if raw is None:
        return None
    pack = constraints.get("engineering_playbook_pack")
    if not isinstance(raw, dict) or not isinstance(pack, dict):
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "engineering playbook policy/pack binding must be objects",
        )
    if pack.get("pack_id") != PACK_ID or pack.get("revision") != PACK_REVISION:
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "engineering playbook pack binding is not the current qualified revision",
            details={
                "pack_id": pack.get("pack_id"),
                "revision": pack.get("revision"),
                "expected_revision": PACK_REVISION,
            },
        )
    archetype_id = raw.get("archetype_id")
    if not isinstance(archetype_id, str):
        raise DdeError("VEKL_MANIFEST_INVALID", "engineering archetype is missing")
    validate_archetype_for_task(task, archetype_id)
    if constraints.get("engineering_archetype") != archetype_id:
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "TaskSignature engineering archetype and policy disagree",
        )

    def _bool(name: str, expected: bool | None = None) -> bool:
        value = raw.get(name)
        if not isinstance(value, bool):
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                f"engineering policy {name} must be boolean",
            )
        if expected is not None and value is not expected:
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                f"engineering policy guard {name} was weakened",
            )
        return value

    def _strings(name: str, allowed: set[str]) -> tuple[str, ...]:
        value = raw.get(name)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                f"engineering policy {name} must be a string list",
            )
        items = tuple(dict.fromkeys(value))
        unknown = sorted(set(items) - allowed)
        if unknown:
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                f"engineering policy {name} contains unknown identifiers",
                details={"unknown": unknown},
            )
        return items

    context_policy = raw.get("investigation_context")
    parallelism_policy = raw.get("parallelism_policy")
    if context_policy not in {"MAIN", "ISOLATED_RESEARCH", "FRESH_IMPLEMENTATION"}:
        raise DdeError("VEKL_MANIFEST_INVALID", "invalid investigation context policy")
    if parallelism_policy not in {
        "SERIAL",
        "INDEPENDENT_READS",
        "DISJOINT_WORKTREES_ONLY",
    }:
        raise DdeError("VEKL_MANIFEST_INVALID", "invalid parallelism policy")
    correction_limit = raw.get("max_correction_failures_before_restart")
    if not isinstance(correction_limit, int) or isinstance(correction_limit, bool):
        raise DdeError("VEKL_MANIFEST_INVALID", "invalid correction failure limit")
    if correction_limit != 2:
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "engineering correction restart limit differs from qualified policy",
        )
    max_skill_count = raw.get("max_skill_count")
    if max_skill_count != MAX_ENGINEERING_PLAYBOOK_SKILLS:
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "engineering Skill activation ceiling differs from qualified policy",
        )
    if raw.get("authority") != "NON_AUTHORITATIVE_ENGINEERING_GUIDANCE":
        raise DdeError(
            "VEKL_MANIFEST_INVALID", "engineering guidance authority drifted"
        )
    skill_ids = _strings("skill_ids", set(SKILLS))
    if len(skill_ids) > MAX_ENGINEERING_PLAYBOOK_SKILLS:
        raise DdeError("VEKL_SKILL_BUDGET_EXCEEDED", "too many engineering Skills")
    gate_ids = _strings("completion_gate_ids", set(GATES))
    hook_ids = _strings("hook_ids", set(HOOK_POLICIES))
    fresh_reviewer = _bool("fresh_reviewer_required")
    if fresh_reviewer and "adversarial-review" not in skill_ids:
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "fresh-review policy is missing the adversarial-review Skill",
        )
    if fresh_reviewer and "gate.fresh-review" not in gate_ids:
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "fresh-review policy is missing its completion gate",
        )
    return OrchestratorExecutionPolicy(
        archetype_id=archetype_id,
        plan_required=_bool("plan_required"),
        fresh_start_required=_bool("fresh_start_required"),
        fresh_reviewer_required=fresh_reviewer,
        investigation_context=context_policy,
        parallelism_policy=parallelism_policy,
        max_correction_failures_before_restart=correction_limit,
        completion_gate_ids=gate_ids,
        skill_ids=skill_ids,
        hook_ids=hook_ids,
        require_evidence=_bool("require_evidence", True),
        prohibit_scope_thinning=_bool("prohibit_scope_thinning", True),
        prohibit_verifier_tampering=_bool("prohibit_verifier_tampering", True),
        authority="NON_AUTHORITATIVE_ENGINEERING_GUIDANCE",
        canon_wins=_bool("canon_wins", True),
        may_change_architecture=_bool("may_change_architecture", False),
        may_advance_gate=_bool("may_advance_gate", False),
        may_access_secrets=_bool("may_access_secrets", False),
        max_skill_count=MAX_ENGINEERING_PLAYBOOK_SKILLS,
    )


def derive_satisfied_completion_gates(
    policy: OrchestratorExecutionPolicy,
    *,
    task: Task,
    oracle: AcceptanceOracle,
    verification_status: str,
    evidence_refs: tuple[str, ...],
    guardrail_clean: bool,
    prototype_clean: bool,
) -> tuple[str, ...]:
    """Map real AcceptanceOracle evidence onto playbook completion obligations.

    This function never upgrades a non-PASSED oracle result. Specialized gates use
    existing typed evidence bindings and explicit reference conventions rather than
    worker prose. Missing specialized proof therefore remains missing/fail-closed.
    """

    if verification_status != "PASSED":
        return ()
    bindings = [
        item.evidence_binding
        for item in (*oracle.observable_outcomes, *oracle.negative_cases)
    ]
    kinds = {item.kind for item in bindings}
    refs = {item.ref.lower() for item in bindings}

    def has_ref(*prefixes: str) -> bool:
        return any(any(ref.startswith(prefix) for prefix in prefixes) for ref in refs)

    satisfied: list[str] = []
    if evidence_refs:
        satisfied.append("gate.evidence-required")
    if guardrail_clean and prototype_clean:
        satisfied.append("gate.scope-integrity")
    if (
        oracle.task_id == task.task_id
        and set(task.requirement_refs).issubset(set(oracle.requirement_refs))
        and set(task.feature_refs).issubset(set(oracle.feature_refs))
    ):
        satisfied.append("gate.requirement-coverage")
    if kinds.intersection({"test", "invariant"}):
        satisfied.append("gate.regression")
    if kinds.intersection({"test", "invariant"}) and has_ref(
        "regression:", "reproducer:"
    ):
        satisfied.append("gate.root-cause-reproduction")
    if kinds.intersection({"test", "invariant"}) and has_ref(
        "baseline:", "equivalence:"
    ):
        satisfied.append("gate.behavior-equivalence")
    if kinds.intersection({"visual_diff", "silhouette", "visual_critique"}) and any(
        item.kind in {"test", "api_probe", "invariant"}
        and item.ref.lower().startswith("accessibility:")
        for item in bindings
    ):
        satisfied.append("gate.visual-live")
    if (
        "db_assertion" in kinds
        and has_ref("migration:forward")
        and has_ref("migration:rollback", "migration:recovery")
    ):
        satisfied.append("gate.migration-reversible")
    if "security_scan" in kinds:
        satisfied.append("gate.security")
    if any(
        item.kind in {"test", "api_probe"} and item.ref.lower().startswith("benchmark:")
        for item in bindings
    ):
        satisfied.append("gate.performance-target")
    if any(
        item.kind in {"judge", "human"}
        and (item.independence or "").lower()
        in {"fresh_context", "independent_fresh_context"}
        for item in bindings
    ):
        satisfied.append("gate.fresh-review")
    if has_ref("release:certification") and has_ref("release:rollback"):
        satisfied.append("gate.release-certification")
    return tuple(
        gate_id
        for gate_id in dict.fromkeys(satisfied)
        if gate_id in policy.completion_gate_ids
    )


def evaluate_completion_gates(
    policy: OrchestratorExecutionPolicy,
    *,
    satisfied_gate_ids: tuple[str, ...],
    evidence_refs: tuple[str, ...],
) -> CompletionGateDecision:
    """Fail closed over gate attestations produced by existing verification authority.

    This function does not grade code and does not mint evidence. It only checks that
    every policy-required gate has already been satisfied by the ordinary
    AcceptanceOracle/VerificationRun/Evidence path and that attributable evidence is
    present before an orchestrator may count the task as complete.
    """

    required = tuple(dict.fromkeys(policy.completion_gate_ids))
    unknown = tuple(gate_id for gate_id in required if gate_id not in GATES)
    if unknown:
        raise DdeError(
            "VEKL_GATE_INVALID",
            "engineering policy references unknown verification gates",
            details={"gate_ids": list(unknown)},
        )
    satisfied = tuple(
        gate_id for gate_id in dict.fromkeys(satisfied_gate_ids) if gate_id in required
    )
    missing = tuple(gate_id for gate_id in required if gate_id not in satisfied)
    if policy.require_evidence and not evidence_refs:
        missing = tuple(dict.fromkeys((*missing, "gate.evidence-required")))
    return CompletionGateDecision(
        complete=not missing,
        required_gate_ids=required,
        satisfied_gate_ids=satisfied,
        missing_gate_ids=missing,
        evidence_refs=tuple(evidence_refs),
    )


def resolve_required_skill_resources(
    *,
    signature_constraints: dict[str, object],
    resources: list[VEKLResource],
    requested_modes: list[str],
) -> tuple[UUID, ...]:
    """Resolve exact playbook Skill resources required by a TaskSignature.

    Archetype selection is not advisory metadata: when the TaskSignature binds an
    engineering playbook, every selected Skill must resolve to the exact DDE pack
    revision and must be activated as ``PROCEDURAL_GUIDANCE``.  This helper performs
    only identity/mode binding. The ordinary VEKL eligibility pass still decides
    lifecycle qualification, provenance, budget, scope, freshness and revocation.
    """

    playbook_policy = signature_constraints.get("engineering_playbook", {})
    playbook_pack = signature_constraints.get("engineering_playbook_pack", {})
    if playbook_policy and not isinstance(playbook_policy, dict):
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "engineering playbook policy must be an object",
        )
    if playbook_pack and not isinstance(playbook_pack, dict):
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "engineering playbook pack binding must be an object",
        )
    if not isinstance(playbook_policy, dict):
        return ()
    raw_skill_ids = playbook_policy.get("skill_ids", [])
    if not isinstance(raw_skill_ids, list) or not all(
        isinstance(item, str) for item in raw_skill_ids
    ):
        raise DdeError(
            "VEKL_MANIFEST_INVALID",
            "engineering playbook skill_ids must be a string list",
        )
    skill_ids = list(dict.fromkeys(raw_skill_ids))
    if not skill_ids:
        return ()
    if "PROCEDURAL_GUIDANCE" not in requested_modes:
        raise DdeError(
            "VEKL_RESOURCE_INELIGIBLE",
            "engineering playbook requires PROCEDURAL_GUIDANCE activation",
            details={"skill_ids": skill_ids},
        )
    expected_revision = PACK_REVISION
    if isinstance(playbook_pack, dict) and playbook_pack.get("revision") is not None:
        expected_revision = str(playbook_pack["revision"])
    required: list[UUID] = []
    missing: dict[str, list[str]] = {}
    for skill_id in skill_ids:
        matches = [
            resource
            for resource in resources
            if resource.resource_kind == "SKILL"
            and resource.revision == expected_revision
            and resource.provenance.get("source") == PACK_ID
            and resource.provenance.get("skill_id") == skill_id
        ]
        if not matches:
            missing[skill_id] = ["RESOURCE_NOT_FOUND"]
            continue
        required.append(
            min(matches, key=lambda item: str(item.resource_id)).resource_id
        )
    if missing:
        raise DdeError(
            "VEKL_RESOURCE_INELIGIBLE",
            "required engineering playbook Skills are not installed",
            details={"skills": missing, "revision": expected_revision},
        )
    return tuple(required)


def apply_engineering_playbook(
    task: Task,
    spec: TaskSignatureSpec,
    *,
    correction_failures: int = 0,
    unattended: bool = False,
) -> tuple[TaskSignatureSpec, OrchestratorExecutionPolicy | None]:
    """Bind an explicitly selected archetype into the existing TaskSignature.

    No classifier guesses the archetype.  If the caller does not select one, the
    signature is unchanged.  When selected, the resulting policy is persisted inside
    the existing ``constraints`` JSON rather than minting a second task identity or
    adding a parallel planning store.
    """

    reserved = {
        "engineering_archetype",
        "engineering_execution_mode",
        "engineering_playbook",
        "engineering_playbook_pack",
    }
    if spec.engineering_archetype is None:
        forbidden = sorted(reserved.intersection(spec.constraints))
        if forbidden:
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                "caller cannot inject reserved engineering-playbook constraints",
                details={"reserved_keys": forbidden},
            )
        return spec, None
    policy = build_orchestrator_policy(
        task,
        spec.engineering_archetype,
        correction_failures=correction_failures,
        unattended=unattended,
    )
    constraints = dict(spec.constraints)
    constraints["engineering_archetype"] = policy.archetype_id
    constraints["engineering_execution_mode"] = (
        "UNATTENDED" if unattended else "ATTENDED"
    )
    constraints["engineering_playbook"] = policy.as_dict()
    constraints["engineering_playbook_pack"] = {
        "pack_id": PACK_ID,
        "revision": PACK_REVISION,
        "source_snapshot": PACK_SOURCE_SNAPSHOT,
    }
    return spec.model_copy(update={"constraints": constraints}), policy


def skill_resource_specs(
    skill_ids: tuple[str, ...] | None = None,
) -> list[VEKLResourceSpec]:
    """Materialize selected DDE Skills as VEKL resource candidates."""

    selected = skill_ids or tuple(SKILLS)
    unknown = sorted(set(selected) - set(SKILLS))
    if unknown:
        raise DdeError(
            "VEKL_SKILL_UNKNOWN",
            "unknown engineering skill requested",
            details={"skill_ids": unknown},
        )
    return [SKILLS[skill_id].to_resource_spec() for skill_id in selected]


def validate_playbook_resource_candidate(resource: VEKLResource) -> str:
    """Prove a persisted local Skill is the exact DDE-authored pack artifact.

    This is intentionally stricter than ordinary first-party metadata trust. The
    engineering playbook can be reference-qualified without an external fetch only
    because DDE can deterministically reconstruct the expected resource from source
    code and compare every authority-bearing field. Any drift, executable scope,
    provider URI, injection finding, or stale revision fails closed.

    Returns the canonical ``skill_id`` when the candidate is exact.
    """

    source = resource.provenance.get("source")
    skill_id = resource.provenance.get("skill_id")
    if source != PACK_ID or not isinstance(skill_id, str) or skill_id not in SKILLS:
        raise DdeError(
            "VEKL_PLAYBOOK_RESOURCE_INVALID",
            "resource is not an exact DDE engineering-playbook Skill",
            details={"resource_id": str(resource.resource_id)},
        )
    expected = SKILLS[skill_id].to_resource_spec()
    expected_fields = expected.model_dump(mode="json")
    actual_fields = {
        key: value
        for key, value in resource.model_dump(mode="json").items()
        if key in expected_fields
    }
    mismatches = sorted(
        key
        for key, expected_value in expected_fields.items()
        if actual_fields.get(key) != expected_value
    )
    if resource.injection_findings:
        mismatches.append("injection_findings")
    if resource.lifecycle_state in {"DEPRECATED", "REVOKED"}:
        mismatches.append("lifecycle_state")
    if mismatches:
        raise DdeError(
            "VEKL_PLAYBOOK_RESOURCE_INVALID",
            "DDE engineering-playbook Skill candidate differs from the pinned pack",
            details={
                "resource_id": str(resource.resource_id),
                "skill_id": skill_id,
                "revision": resource.revision,
                "expected_revision": PACK_REVISION,
                "mismatches": sorted(set(mismatches)),
            },
        )
    return skill_id


def materialize_hook_ir(
    hook_id: str,
    *,
    matcher: dict[str, object],
    command: list[str] | None = None,
    capability_id: str | None = None,
    filesystem_scopes: list[str] | None = None,
    network_scopes: list[str] | None = None,
    secret_scopes: list[str] | None = None,
    timeout_seconds: int = 30,
) -> HookIR:
    """Create a concrete HookIR only after a deterministic action is supplied."""

    try:
        policy = HOOK_POLICIES[hook_id]
    except KeyError as exc:
        raise DdeError(
            "VEKL_HOOK_INVALID",
            "unknown engineering hook policy",
            details={"hook_id": hook_id, "allowed": sorted(HOOK_POLICIES)},
        ) from exc
    if (command is None) == (capability_id is None):
        raise DdeError(
            "VEKL_HOOK_INVALID",
            "hook materialization requires exactly one command or DDE capability",
            details={"hook_id": hook_id},
        )
    return HookIR(
        hook_id=hook_id,
        hook_class=policy.hook_class,
        event=policy.event,
        matcher=matcher,
        command=command,
        capability_id=capability_id,
        filesystem_scopes=list(filesystem_scopes or []),
        network_scopes=list(network_scopes or []),
        secret_scopes=list(secret_scopes or []),
        timeout_seconds=timeout_seconds,
        failure_policy=policy.failure_policy,
        evidence_types=list(policy.evidence_types),
    )
