"""Research packet completeness and the advisory boundary.

A packet is not complete because one model answered. Completion requires every
required dimension covered plus source identity, provenance, evidence,
contradiction status, freshness, relevance, qualification and graph compilation.
Packets may regress, and a regression is reportable rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.errors import DdeError

#: Actions research may never take, however strong its findings.
FORBIDDEN_RESEARCH_ACTIONS = frozenset(
    {
        "REORDER_TASK_GRAPH",
        "CREATE_IMPLEMENTATION_TASK",
        "AMEND_PROJECT_TRUTH",
        "EXPAND_PRODUCT_SCOPE",
        "CHANGE_PROGRAMME_PRIORITY",
    }
)


@dataclass(frozen=True, slots=True)
class PacketState:
    unit_revision: str
    required_dimensions: tuple[str, ...]
    covered_dimensions: tuple[str, ...]
    has_source_identity: bool
    has_provenance: bool
    has_evidence: bool
    contradictions_resolved: bool
    is_fresh: bool
    is_relevant: bool
    qualification_complete: bool
    graph_compiled: bool
    capsule_compiled: bool


@dataclass(frozen=True, slots=True)
class Completeness:
    complete: bool
    activation_eligible: bool
    missing: tuple[str, ...]


def assess(packet: PacketState) -> Completeness:
    """Every gap is named, so a stalled packet explains itself."""
    missing: list[str] = []
    uncovered = [
        dimension
        for dimension in packet.required_dimensions
        if dimension not in packet.covered_dimensions
    ]
    if uncovered:
        missing.append(f"dimensions:{','.join(uncovered)}")
    for flag, label in (
        (packet.has_source_identity, "source_identity"),
        (packet.has_provenance, "provenance"),
        (packet.has_evidence, "evidence"),
        (packet.contradictions_resolved, "contradiction_status"),
        (packet.is_fresh, "freshness"),
        (packet.is_relevant, "relevance"),
        (packet.qualification_complete, "qualification"),
        (packet.graph_compiled, "graph_compile"),
    ):
        if not flag:
            missing.append(label)
    complete = not missing
    return Completeness(
        complete=complete,
        activation_eligible=complete and packet.capsule_compiled,
        missing=tuple(missing),
    )


def regressed(previous: Completeness, current: Completeness) -> bool:
    """A packet that loses completeness or eligibility has regressed."""
    return (previous.complete and not current.complete) or (
        previous.activation_eligible and not current.activation_eligible
    )


def require_advisory_only(action: str) -> None:
    """Research prepares knowledge; it never steers the programme."""
    if action in FORBIDDEN_RESEARCH_ACTIONS:
        raise DdeError(
            "POLICY_DENIED",
            f"ahead-of-work research may not {action.lower().replace('_', ' ')}",
            retryable=False,
            details={"action": action},
        )
