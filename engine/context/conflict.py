"""Chapter 5.6 conflict adjudication.

Real, structural (not semantic) rank<=6 contradiction detection over what
the authority retriever (Chapter 5.2, `engine.context.retrievers.authority`)
actually resolved from Project Truth for this `compile()` call. Two rules,
both mechanically verifiable without a model call (Chapter 9.6: no new
dependency, and AGENTS.md forbids handing model-generated code a
long-lived credential -- `engine.context` never makes one):

1. ``overlapping_accepted_edrs`` -- two independently **accepted** EDRs
   (rank 4, Chapter 2.2) name the same requirement slug in
   ``affected_requirement_slugs`` without either superseding the other.
   Two governance decisions that both claim authority over the same
   requirement, with neither reconciled against the other, is exactly
   "two items of authority... contradict each other" (Chapter 5.6) -- the
   DCE is not entitled to guess which one a worker should follow.
2. ``superseded_item_still_authoritative`` -- a resolved Requirement or
   EDR's ``supersedes_id`` names another item **also resolved into this
   same package**. The predecessor is stale by construction (its
   successor exists and was retrieved for the same task), yet both would
   otherwise be handed to the worker as live authority.

Rank-9/10 material (donor evidence, model hypotheses) never conflicts
(Chapter 5.6, second paragraph) -- this module only ever inspects
`AuthorityResult`, which is exclusively rank 3/4
(`AUTHORITY_RANK_REQUIREMENT`/`AUTHORITY_RANK_EDR`), so nothing here can
promote low-authority material into a blocking conflict.

**Flagged Stage 1 divergence.** Genuine semantic contradiction -- two
sources making textually opposite claims without any structural marker
connecting them -- is out of reach without a model call this module
deliberately does not make. This is a real, if partial, implementation of
the rank<=6 contradiction rule, not the full universe of contradictions
Chapter 5.6 could in principle name; see `docs/planning/mission-numbering-
note.md` for how this interacts with EDR-0003's deferred
`contradiction_rate` promotion gate.
"""

from __future__ import annotations

from engine.context.model import DetectedConflict
from engine.context.retrievers.authority import AuthorityResult
from engine.contracts.edr import Edr
from engine.contracts.requirement import Requirement

CONTRADICTION_AUTHORITY_RANK_CEILING = 6  # Chapter 5.6: "authority rank <= 6"


def _edr_key(edr: Edr) -> str:
    return f"edr:{edr.slug}"


def _requirement_key(requirement: Requirement) -> str:
    return f"requirement:{requirement.slug}"


def _supersession_reconciles(first: Edr, second: Edr) -> bool:
    return first.supersedes_id == second.edr_id or second.supersedes_id == first.edr_id


def _overlapping_accepted_edrs(
    edrs: list[Edr], authority_rank: int
) -> list[DetectedConflict]:
    accepted = [edr for edr in edrs if edr.status == "accepted"]
    conflicts: list[DetectedConflict] = []
    for index, first in enumerate(accepted):
        for second in accepted[index + 1 :]:
            if _supersession_reconciles(first, second):
                continue
            shared = sorted(
                set(first.affected_requirement_slugs)
                & set(second.affected_requirement_slugs)
            )
            if not shared:
                continue
            conflicts.append(
                DetectedConflict(
                    item_a_key=_edr_key(first),
                    item_a_authority_rank=authority_rank,
                    item_b_key=_edr_key(second),
                    item_b_authority_rank=authority_rank,
                    contradiction_type="overlapping_accepted_edrs",
                    affected_success_criteria=tuple(shared),
                )
            )
    return conflicts


def _superseded_requirement_pairs(
    requirements: list[Requirement], authority_rank: int
) -> list[DetectedConflict]:
    by_id = {requirement.requirement_id: requirement for requirement in requirements}
    conflicts: list[DetectedConflict] = []
    for requirement in requirements:
        if requirement.supersedes_id is None:
            continue
        predecessor = by_id.get(requirement.supersedes_id)
        if predecessor is None:
            continue
        conflicts.append(
            DetectedConflict(
                item_a_key=_requirement_key(predecessor),
                item_a_authority_rank=authority_rank,
                item_b_key=_requirement_key(requirement),
                item_b_authority_rank=authority_rank,
                contradiction_type="superseded_item_still_authoritative",
                affected_success_criteria=tuple(predecessor.acceptance_conditions),
            )
        )
    return conflicts


def _superseded_edr_pairs(
    edrs: list[Edr], authority_rank: int
) -> list[DetectedConflict]:
    by_id = {edr.edr_id: edr for edr in edrs}
    conflicts: list[DetectedConflict] = []
    for edr in edrs:
        if edr.supersedes_id is None:
            continue
        predecessor = by_id.get(edr.supersedes_id)
        if predecessor is None:
            continue
        conflicts.append(
            DetectedConflict(
                item_a_key=_edr_key(predecessor),
                item_a_authority_rank=authority_rank,
                item_b_key=_edr_key(edr),
                item_b_authority_rank=authority_rank,
                contradiction_type="superseded_item_still_authoritative",
                affected_success_criteria=tuple(predecessor.affected_requirement_slugs),
            )
        )
    return conflicts


def detect_conflicts(
    authority: AuthorityResult,
    *,
    requirement_authority_rank: int,
    edr_authority_rank: int,
) -> list[DetectedConflict]:
    """Chapter 5.6 entry point: every rank<=6 contradiction this Stage 1
    slice can detect among what `authority.retrieve()` resolved for one
    `compile()` call. Pure and deterministic -- no I/O, no model call."""
    conflicts: list[DetectedConflict] = []
    conflicts.extend(
        _overlapping_accepted_edrs(authority.resolved_edrs, edr_authority_rank)
    )
    conflicts.extend(
        _superseded_requirement_pairs(
            authority.resolved_requirements, requirement_authority_rank
        )
    )
    conflicts.extend(_superseded_edr_pairs(authority.resolved_edrs, edr_authority_rank))
    return conflicts
