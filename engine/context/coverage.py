"""Chapter 5.8 coverage contract, computed from what the pipeline
actually retrieved and actually assembled — never a hardcoded status.

Two categories have no dedicated Stage 1 source table (`applicable_domain
_rules`/"approved business rules" rank 5, `architecture_constraints`/
"approved architecture" rank 6 — Chapter 3.3's Stage 1 table set creates
neither). `applicable_domain_rules` uses accepted EDRs as the nearest
available governance artifact; `architecture_constraints` uses lexical
hits against `AGENTS.md`/`docs/blueprint/**`. Both are flagged Stage 1
substitutions, not fabricated answers — when a task declares nothing
those sources can speak to, the category is `satisfied` (vacuously,
nothing was required); when it does and nothing was found, it is
genuinely `missing`.
"""

from __future__ import annotations

from engine.context.model import (
    AssembledContext,
    ContextItem,
    CoverageReport,
    DiscoveryResult,
    FusedItem,
)
from engine.context.repo import SECURITY_KEYWORDS, touches_scope
from engine.context.retrievers.authority import AuthorityResult
from engine.contracts.task import Task


def _is_security_relevant(task: Task) -> bool:
    text = " ".join([task.title, task.intent, *task.success_criteria]).lower()
    return any(keyword in text for keyword in SECURITY_KEYWORDS)


def _category_status(
    category: str,
    included_items: list[ContextItem],
    all_fused_items: list[ContextItem],
) -> tuple[str, list[str]]:
    found_post = any(category in item.categories for item in included_items)
    if found_post:
        return "satisfied", []
    found_pre = any(category in item.categories for item in all_fused_items)
    if found_pre:
        return "partial", [
            f"Evidence for {category} was retrieved but evicted under the "
            "context budget"
        ]
    return "missing", [
        f"No {category} evidence was retrieved for this task "
        "(Stage 1 has no dedicated source for this category)"
    ]


def compute_coverage(
    task: Task,
    discovery: DiscoveryResult,
    authority_result: AuthorityResult,
    fused_items: list[FusedItem],
    assembled: AssembledContext,
) -> CoverageReport:
    included_items = [fused.item for fused in assembled.included]
    all_fused_items = [fused.item for fused in fused_items]
    questions: list[str] = []

    resolved_by_slug = {
        requirement.slug: requirement
        for requirement in authority_result.resolved_requirements
    }
    edr_by_slug = {edr.slug: edr for edr in authority_result.resolved_edrs}

    requirement_targets = [
        ref for ref in task.requirement_refs if ref not in edr_by_slug
    ]
    if not requirement_targets:
        authoritative_requirements = "satisfied"
    else:
        found = [
            resolved_by_slug[ref]
            for ref in requirement_targets
            if ref in resolved_by_slug
        ]
        approved = [item for item in found if item.status == "approved"]
        if not found:
            authoritative_requirements = "missing"
        elif len(approved) == len(requirement_targets):
            authoritative_requirements = "satisfied"
        else:
            authoritative_requirements = "partial"
    for ref in requirement_targets:
        if ref not in resolved_by_slug:
            questions.append(
                f"Requirement reference '{ref}' could not be resolved "
                "against Project Truth"
            )
        elif resolved_by_slug[ref].status != "approved":
            questions.append(
                f"Requirement reference '{ref}' resolved but is not yet "
                f"approved (status={resolved_by_slug[ref].status})"
            )

    edr_like_targets = [
        ref
        for ref in task.requirement_refs
        if ref in edr_by_slug or ref.upper().startswith("EDR-")
    ]
    if not edr_like_targets:
        applicable_domain_rules = "satisfied"
    else:
        found_edrs = [
            edr_by_slug[ref] for ref in edr_like_targets if ref in edr_by_slug
        ]
        accepted = [edr for edr in found_edrs if edr.status == "accepted"]
        if not found_edrs:
            applicable_domain_rules = "missing"
        elif len(accepted) == len(edr_like_targets):
            applicable_domain_rules = "satisfied"
        else:
            applicable_domain_rules = "partial"
    for ref in edr_like_targets:
        if ref not in edr_by_slug:
            questions.append(
                f"EDR reference '{ref}' could not be resolved against Project Truth"
            )
        elif edr_by_slug[ref].status != "accepted":
            questions.append(
                f"EDR reference '{ref}' resolved but is not yet accepted "
                f"(status={edr_by_slug[ref].status})"
            )

    write_scope = task.expected_write_scope
    if not write_scope:
        impacted_code_and_deps = "satisfied"
    else:
        covered = [
            scope
            for scope in write_scope
            if any(
                item.source_path is not None
                and touches_scope(item.source_path, (scope,))
                for item in included_items
            )
        ]
        if len(covered) == len(write_scope):
            impacted_code_and_deps = "satisfied"
        elif covered:
            impacted_code_and_deps = "partial"
        else:
            impacted_code_and_deps = "missing"
        for scope in write_scope:
            if scope not in covered:
                questions.append(
                    f"No retrieved evidence covers declared write scope '{scope}'"
                )

    architecture_constraints, architecture_questions = _category_status(
        "architecture_constraints", included_items, all_fused_items
    )
    questions.extend(architecture_questions)

    if _is_security_relevant(task):
        security_constraints, security_questions = _category_status(
            "security_constraints", included_items, all_fused_items
        )
        questions.extend(security_questions)
    else:
        security_constraints = "satisfied"

    if task.success_criteria:
        verification_obligations = "satisfied"
    else:
        verification_obligations = "missing"
        questions.append("Task declares no success criteria to verify against")

    for path in discovery.unresolved_paths:
        questions.append(
            f"expected_read_scope entry '{path}' does not exist in the "
            "repository working tree"
        )

    return CoverageReport(
        authoritative_requirements=authoritative_requirements,
        applicable_domain_rules=applicable_domain_rules,
        impacted_code_and_deps=impacted_code_and_deps,
        architecture_constraints=architecture_constraints,
        security_constraints=security_constraints,
        verification_obligations=verification_obligations,
        known_unresolved_questions=tuple(questions),
    )
