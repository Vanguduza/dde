"""Authority retriever (Chapter 5.2): requirements and EDRs already in
Postgres via `engine.truth`. Reads only — `engine.truth.repository`'s
existing `get_requirement_by_slug`/`get_edr_by_slug` are the sole readers
this module calls, per Chapter 3.8 ("Nothing except `engine.truth`
writes to Project Truth tables"; reading through its own repository is
not a second requirements reader).

Task carries one ref-list field (`requirement_refs`) for both Requirement
and EDR identity — there is no dedicated `edr_refs` column yet. This
retriever resolves each ref by trying a Requirement lookup first, then an
EDR lookup, which is a **flagged Stage 1 divergence**: a future mission
that adds a dedicated `edr_refs` column to `Task` should remove this
dual-lookup behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.model import (
    AUTHORITY_RANK_EDR,
    AUTHORITY_RANK_REQUIREMENT,
    ContextItem,
)
from engine.contracts.edr import Edr
from engine.contracts.requirement import Requirement
from engine.truth.repository import TruthRepository


@dataclass(frozen=True)
class AuthorityResult:
    items: list[ContextItem]
    resolved_requirements: list[Requirement]
    resolved_edrs: list[Edr]
    unresolved_refs: list[str]


def _requirement_item(requirement: Requirement, rank: int) -> ContextItem:
    content = (
        f"{requirement.slug} ({requirement.status}): {requirement.statement}\n"
        f"Constraints: {'; '.join(requirement.constraints) or 'none'}\n"
        f"Acceptance conditions: {'; '.join(requirement.acceptance_conditions)}"
    )
    return ContextItem(
        retriever="authority",
        key=f"requirement:{requirement.slug}",
        categories=("authoritative_requirements",),
        authority_rank=AUTHORITY_RANK_REQUIREMENT,
        rank_in_retriever=rank,
        relevance=1.0,
        write_scope_match=False,
        content=content,
        source_path=None,
    )


def _edr_item(edr: Edr, rank: int) -> ContextItem:
    content = (
        f"{edr.slug} ({edr.status}): {edr.decision}\n"
        f"Rationale: {edr.rationale}\n"
        f"Consequences: {'; '.join(edr.consequences) or 'none'}"
    )
    return ContextItem(
        retriever="authority",
        key=f"edr:{edr.slug}",
        categories=("applicable_domain_rules",),
        authority_rank=AUTHORITY_RANK_EDR,
        rank_in_retriever=rank,
        relevance=1.0,
        write_scope_match=False,
        content=content,
        source_path=None,
    )


async def retrieve(
    connection: AsyncConnection,
    *,
    project_id: UUID,
    requirement_refs: tuple[str, ...],
    repository: TruthRepository | None = None,
) -> AuthorityResult:
    repo = repository or TruthRepository()
    items: list[ContextItem] = []
    resolved_requirements: list[Requirement] = []
    resolved_edrs: list[Edr] = []
    unresolved_refs: list[str] = []
    rank = 1
    for slug in requirement_refs:
        requirement = await repo.get_requirement_by_slug(connection, project_id, slug)
        if requirement is not None:
            resolved_requirements.append(requirement)
            items.append(_requirement_item(requirement, rank))
            rank += 1
            continue
        edr = await repo.get_edr_by_slug(connection, project_id, slug)
        if edr is not None:
            resolved_edrs.append(edr)
            items.append(_edr_item(edr, rank))
            rank += 1
            continue
        unresolved_refs.append(slug)
    return AuthorityResult(
        items=items,
        resolved_requirements=resolved_requirements,
        resolved_edrs=resolved_edrs,
        unresolved_refs=unresolved_refs,
    )
