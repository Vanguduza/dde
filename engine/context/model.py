"""Internal value objects for context compilation (Chapter 5).

None of these are wire contracts — `schemas/objects/context_package.json`
is the only durable contract this module owns (Chapter 3.8). Everything
here is the in-process shape retrievers, fusion, assembly and coverage
pass between each other during one `ContextService.compile()` call.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

# Chapter 2.2 authority ranks used by the Stage 1 retrievers. PRD (rank 2)
# and approved architecture/business rules (ranks 5-6) have no Stage 1
# table and are never assigned here.
AUTHORITY_RANK_REQUIREMENT = 3
AUTHORITY_RANK_EDR = 4
AUTHORITY_RANK_CODE = 8  # "Verified implementation and evidence" — nearest
# applicable rank for retrieved repository content; the blueprint's
# retriever table lists code retrievers as free/cheap cost, not a
# precedence rank, so this is a Stage 1 mapping decision, not a blueprint
# value.

CoverageStatus = str  # "satisfied" | "partial" | "missing"


@dataclass(frozen=True)
class DiscoveryResult:
    """Chapter 5.1 Discovery step output: a Task's explicit refs resolved
    against Project Truth identity and this repository's working tree."""

    requirement_refs: tuple[str, ...]
    feature_refs: tuple[str, ...]
    expected_read_scope: tuple[str, ...]
    expected_write_scope: tuple[str, ...]
    resolved_paths: tuple[str, ...]
    unresolved_paths: tuple[str, ...]


@dataclass(frozen=True)
class ContextItem:
    """One piece of ranked evidence returned by a single Stage 1 retriever
    (Chapter 5.2). `key` is the identity fusion merges duplicates on —
    two retrievers surfacing the same file/requirement/EDR merge into one
    fused item rather than being counted twice."""

    retriever: str
    key: str
    categories: tuple[str, ...]
    authority_rank: int
    rank_in_retriever: int
    relevance: float
    write_scope_match: bool
    content: str
    source_path: str | None

    @property
    def token_estimate(self) -> int:
        """~4 characters per token — a documented Stage 1 approximation;
        no tokenizer dependency exists in this project (Chapter 9.6)."""
        return max(1, len(self.content) // 4)


@dataclass(frozen=True)
class FusedItem:
    """A `ContextItem` after Chapter 5.3 reciprocal rank fusion, carrying
    its fused score and which retrievers contributed to it."""

    item: ContextItem
    fused_score: float
    contributing_retrievers: tuple[str, ...]


@dataclass(frozen=True)
class AssembledContext:
    """Chapter 5.7 output: the final, budget-assembled item set plus a log
    of what was evicted, in priority order, to get there."""

    included: tuple[FusedItem, ...]
    evicted: tuple[FusedItem, ...]
    total_tokens: int


@dataclass(frozen=True)
class ContextBudgetExceeded:
    """Chapter 5.7: returned, never raised, when the un-evictable evidence
    alone exceeds `context_budget` — "a decomposition failure, not a
    context failure". No `context_packages` row is written for this
    result."""

    task_id: UUID
    budget_tokens: int
    required_tokens: int
    unevictable_tokens: int


@dataclass(frozen=True)
class CoverageReport:
    """Chapter 5.8 coverage contract."""

    authoritative_requirements: CoverageStatus
    applicable_domain_rules: CoverageStatus
    impacted_code_and_deps: CoverageStatus
    architecture_constraints: CoverageStatus
    security_constraints: CoverageStatus
    verification_obligations: CoverageStatus
    known_unresolved_questions: tuple[str, ...]

    def required_statuses(self) -> dict[str, CoverageStatus]:
        return {
            "authoritative_requirements": self.authoritative_requirements,
            "applicable_domain_rules": self.applicable_domain_rules,
            "impacted_code_and_deps": self.impacted_code_and_deps,
            "architecture_constraints": self.architecture_constraints,
            "security_constraints": self.security_constraints,
            "verification_obligations": self.verification_obligations,
        }

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = dict(self.required_statuses())
        payload["known_unresolved_questions"] = list(self.known_unresolved_questions)
        return payload


@dataclass(frozen=True)
class DetectedConflict:
    """Chapter 5.6: one rank<=6 contradiction found between two items of
    authority the DCE resolved for the same package. Naming both items
    plus the contradiction type and affected success criteria is the
    blueprint's own `ContextConflict` shape; this is the in-process value
    before it is persisted as a durable `ContextConflict` row."""

    item_a_key: str
    item_a_authority_rank: int
    item_b_key: str
    item_b_authority_rank: int
    contradiction_type: str
    affected_success_criteria: tuple[str, ...]


@dataclass(frozen=True)
class CriticTriggerResult:
    """Chapter 5.9: whether the Context Critic fires this compile() call,
    which of the five trigger conditions held, and the real (Stage 1
    proxy) confidence signal that fed the last of them."""

    triggered: bool
    reasons: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class CriticOutcome:
    """Chapter 5.9: what the critic did once triggered. It may only
    request additional retrieval (`reassembled` carries the recovered
    `AssembledContext`) or raise a Context Finding (`reassembled` is
    `None`) -- it can never alter Project Truth and never approves its
    own request."""

    action: str
    reassembled: AssembledContext | None
    outcome_summary: str
    cost_tokens_estimate: int
