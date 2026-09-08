"""Smallest-sufficient, provenance-bearing VEKL context compilation."""

from __future__ import annotations

from dataclasses import dataclass

from engine.contracts.vekl_activation_manifest import VEKLActivationManifest
from engine.contracts.vekl_resource import VEKLResource
from engine.core.errors import BudgetExhaustedError, DdeError
from engine.core.hashing import canonical_json, sha256_hex


@dataclass(frozen=True)
class KnowledgeItem:
    resource_id: str
    revision: str
    content_hash: str
    source_trust: str
    activation_mode: str
    excerpt: str

    @property
    def estimated_tokens(self) -> int:
        return max(1, len(self.excerpt) // 4)


@dataclass(frozen=True)
class VEKLContextCapsule:
    manifest_id: str
    project_truth_hash: str
    truth_constraints: dict[str, object]
    stack_fingerprint_hash: str
    stack_facts: dict[str, object]
    items: tuple[KnowledgeItem, ...]
    conflicts: tuple[str, ...]
    selection_reasons: tuple[str, ...]
    freshness_state: dict[str, object]
    tool_contracts: tuple[dict[str, object], ...]
    verifier_obligations: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    estimated_tokens: int
    capsule_hash: str


class VEKLKnowledgeCompiler:
    def compile(
        self,
        *,
        manifest: VEKLActivationManifest,
        resources: list[VEKLResource],
        truth_constraints: dict[str, object],
        token_budget: int,
        stack_facts: dict[str, object] | None = None,
        task_verifiers: tuple[str, ...] = (),
    ) -> VEKLContextCapsule:
        by_id = {str(resource.resource_id): resource for resource in resources}
        stack = dict(stack_facts or {})
        selected: list[KnowledgeItem] = []
        provenance: list[str] = []
        verifiers: list[str] = list(task_verifiers)
        conflicts: list[str] = []
        reasons: list[str] = []
        tool_contracts: list[dict[str, object]] = []
        # Project Truth and deterministic stack facts are protected VEKL authority.
        # Their cost is paid before optional resource excerpts are admitted.
        used = max(
            1, len(canonical_json({"truth": truth_constraints, "stack": stack})) // 4
        )
        if used > token_budget:
            raise BudgetExhaustedError(
                "VEKL context budget cannot fit Project Truth and exact stack facts",
                details={"budget_tokens": token_budget, "required_tokens": used},
            )
        executable_kinds = {
            "TOOL",
            "CLI",
            "PLUGIN",
            "MCP_SERVER",
            "LSP_SERVER",
            "HOOK",
            "LOOP",
            "TEST_ORACLE",
        }
        for binding in manifest.selected_resources:
            resource_id = str(binding.get("resource_id", ""))
            resource = by_id.get(resource_id)
            if resource is None:
                raise DdeError(
                    "VEKL_MANIFEST_INVALID",
                    "activation manifest references a missing resource",
                    details={"resource_id": resource_id},
                )
            if resource.content_hash != binding.get(
                "content_hash"
            ) or resource.revision != binding.get("revision"):
                raise DdeError(
                    "VEKL_MANIFEST_INVALID",
                    "activation manifest resource pin no longer matches",
                    details={"resource_id": resource_id},
                )
            item = KnowledgeItem(
                resource_id=resource_id,
                revision=resource.revision,
                content_hash=resource.content_hash,
                source_trust=resource.source_trust,
                activation_mode=str(binding.get("activation_mode")),
                excerpt=resource.content_excerpt,
            )
            reason = str(binding.get("reason") or "selected")
            mandatory = bool(binding.get("mandatory")) or resource.source_trust in {
                "S1_NORMATIVE",
                "S2_FIRST_PARTY",
            }
            if used + item.estimated_tokens > token_budget:
                if mandatory:
                    raise BudgetExhaustedError(
                        "VEKL context budget cannot fit mandatory authority",
                        details={
                            "budget_tokens": token_budget,
                            "required_tokens": used + item.estimated_tokens,
                            "resource_id": resource_id,
                        },
                    )
                continue
            selected.append(item)
            used += item.estimated_tokens
            reasons.append(f"{resource_id}:{reason}")
            provenance.append(
                f"vekl:{resource_id}@{resource.revision}#{resource.content_hash}"
            )
            verifiers.extend(resource.required_verifiers)
            if bool(resource.freshness.get("stale")):
                conflicts.append(f"{resource_id}:stale")
            caveats = resource.provenance.get("caveats")
            if isinstance(caveats, list):
                conflicts.extend(f"{resource_id}:{str(caveat)}" for caveat in caveats)
            if resource.resource_kind in executable_kinds:
                tool_contracts.append(
                    {
                        "resource_id": resource_id,
                        "kind": resource.resource_kind,
                        "activation_mode": str(binding.get("activation_mode")),
                        "required_capabilities": list(resource.required_capabilities),
                        "filesystem_scopes": list(resource.filesystem_scopes),
                        "network_scopes": list(resource.network_scopes),
                        "secret_scopes": list(resource.secret_scopes),
                        "sandbox_requirements": dict(resource.sandbox_requirements),
                        "side_effect_class": resource.side_effect_class,
                    }
                )
        payload = {
            "manifest_id": str(manifest.manifest_id),
            "truth": truth_constraints,
            "stack": stack,
            "items": [item.__dict__ for item in selected],
            "selection_reasons": reasons,
            "freshness": manifest.freshness_state,
            "tool_contracts": tool_contracts,
            "conflicts": sorted(set(conflicts)),
            "verifiers": sorted(set(verifiers)),
            "provenance": provenance,
        }
        capsule_hash = sha256_hex(canonical_json(payload))
        return VEKLContextCapsule(
            manifest_id=str(manifest.manifest_id),
            project_truth_hash=manifest.project_truth_hash,
            truth_constraints=dict(truth_constraints),
            stack_fingerprint_hash=manifest.stack_fingerprint_hash,
            stack_facts=stack,
            items=tuple(selected),
            conflicts=tuple(sorted(set(conflicts))),
            selection_reasons=tuple(reasons),
            freshness_state=dict(manifest.freshness_state),
            tool_contracts=tuple(tool_contracts),
            verifier_obligations=tuple(sorted(set(verifiers))),
            provenance_refs=tuple(provenance),
            estimated_tokens=used,
            capsule_hash=capsule_hash,
        )
