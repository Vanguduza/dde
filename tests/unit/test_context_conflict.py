"""Chapter 5.6 conflict adjudication: structural rank<=6 contradiction
detection over what the authority retriever resolved."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.context.conflict import (
    CONTRADICTION_AUTHORITY_RANK_CEILING,
    detect_conflicts,
)
from engine.context.model import AUTHORITY_RANK_EDR, AUTHORITY_RANK_REQUIREMENT
from engine.context.retrievers.authority import AuthorityResult
from engine.contracts.edr import Edr
from engine.contracts.requirement import Requirement
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _edr(
    *,
    slug: str,
    status: str = "accepted",
    affected_requirement_slugs: list[str] | None = None,
    supersedes_id: object | None = None,
    edr_id: object | None = None,
) -> Edr:
    now = _now()
    return Edr(
        edr_id=edr_id or uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        slug=slug,
        context="ctx",
        alternatives=["a", "b"],
        decision="decide",
        rationale="because",
        consequences=["consequence"],
        affected_requirement_slugs=affected_requirement_slugs or [],
        status=status,  # type: ignore[arg-type]
        supersedes_id=supersedes_id,  # type: ignore[arg-type]
        decided_by_principal=None,
        decided_at=None,
        created_at=now,
        updated_at=now,
    )


def _requirement(
    *,
    slug: str,
    status: str = "approved",
    acceptance_conditions: list[str] | None = None,
    supersedes_id: object | None = None,
    requirement_id: object | None = None,
) -> Requirement:
    now = _now()
    return Requirement(
        requirement_id=requirement_id or uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        slug=slug,
        statement="do the thing",
        constraints=[],
        acceptance_conditions=acceptance_conditions or ["it works"],
        status=status,  # type: ignore[arg-type]
        supersedes_id=supersedes_id,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
    )


def _authority(
    *, requirements: list[Requirement] | None = None, edrs: list[Edr] | None = None
) -> AuthorityResult:
    return AuthorityResult(
        items=[],
        resolved_requirements=requirements or [],
        resolved_edrs=edrs or [],
        unresolved_refs=[],
    )


def test_no_conflict_when_edrs_do_not_share_affected_requirements() -> None:
    edr_a = _edr(slug="EDR-1", affected_requirement_slugs=["REQ-1"])
    edr_b = _edr(slug="EDR-2", affected_requirement_slugs=["REQ-2"])

    conflicts = detect_conflicts(
        _authority(edrs=[edr_a, edr_b]),
        requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
        edr_authority_rank=AUTHORITY_RANK_EDR,
    )

    assert conflicts == []


def test_overlapping_accepted_edrs_is_a_rank_le_6_conflict() -> None:
    edr_a = _edr(slug="EDR-1", affected_requirement_slugs=["REQ-1"])
    edr_b = _edr(slug="EDR-2", affected_requirement_slugs=["REQ-1", "REQ-2"])

    conflicts = detect_conflicts(
        _authority(edrs=[edr_a, edr_b]),
        requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
        edr_authority_rank=AUTHORITY_RANK_EDR,
    )

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.contradiction_type == "overlapping_accepted_edrs"
    assert conflict.item_a_key == "edr:EDR-1"
    assert conflict.item_b_key == "edr:EDR-2"
    assert conflict.affected_success_criteria == ("REQ-1",)
    assert conflict.item_a_authority_rank <= CONTRADICTION_AUTHORITY_RANK_CEILING
    assert conflict.item_b_authority_rank <= CONTRADICTION_AUTHORITY_RANK_CEILING


def test_no_conflict_when_one_edr_is_not_accepted() -> None:
    edr_a = _edr(slug="EDR-1", status="proposed", affected_requirement_slugs=["REQ-1"])
    edr_b = _edr(slug="EDR-2", status="accepted", affected_requirement_slugs=["REQ-1"])

    conflicts = detect_conflicts(
        _authority(edrs=[edr_a, edr_b]),
        requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
        edr_authority_rank=AUTHORITY_RANK_EDR,
    )

    assert conflicts == []


def test_supersession_reconciled_pair_is_not_double_counted_as_overlap() -> None:
    """A supersession relationship between two EDRs that share an
    `affected_requirement_slugs` entry is never *also* flagged as an
    unreconciled `overlapping_accepted_edrs` contradiction -- but the
    predecessor being resolved into the same package as its own
    successor is still a real, distinct `superseded_item_still_
    authoritative` conflict (Chapter 5.6's second rule), so exactly one
    conflict of that type is expected, not zero and not two."""
    predecessor_id = uuid7()
    edr_a = _edr(
        slug="EDR-1", edr_id=predecessor_id, affected_requirement_slugs=["REQ-1"]
    )
    edr_b = _edr(
        slug="EDR-2", affected_requirement_slugs=["REQ-1"], supersedes_id=predecessor_id
    )

    conflicts = detect_conflicts(
        _authority(edrs=[edr_a, edr_b]),
        requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
        edr_authority_rank=AUTHORITY_RANK_EDR,
    )

    assert len(conflicts) == 1
    assert conflicts[0].contradiction_type == "superseded_item_still_authoritative"


def test_superseded_requirement_still_resolved_is_a_conflict() -> None:
    predecessor_id = uuid7()
    predecessor = _requirement(
        slug="REQ-OLD",
        requirement_id=predecessor_id,
        status="superseded",
        acceptance_conditions=["old behaviour holds"],
    )
    successor = _requirement(slug="REQ-NEW", supersedes_id=predecessor_id)

    conflicts = detect_conflicts(
        _authority(requirements=[predecessor, successor]),
        requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
        edr_authority_rank=AUTHORITY_RANK_EDR,
    )

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.contradiction_type == "superseded_item_still_authoritative"
    assert conflict.item_a_key == "requirement:REQ-OLD"
    assert conflict.item_b_key == "requirement:REQ-NEW"
    assert conflict.affected_success_criteria == ("old behaviour holds",)


def test_superseded_edr_still_resolved_is_a_conflict() -> None:
    predecessor_id = uuid7()
    predecessor = _edr(
        slug="EDR-OLD",
        edr_id=predecessor_id,
        status="superseded",
        affected_requirement_slugs=["REQ-1"],
    )
    successor = _edr(slug="EDR-NEW", supersedes_id=predecessor_id)

    conflicts = detect_conflicts(
        _authority(edrs=[predecessor, successor]),
        requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
        edr_authority_rank=AUTHORITY_RANK_EDR,
    )

    assert len(conflicts) == 1
    assert conflicts[0].contradiction_type == "superseded_item_still_authoritative"
    assert conflicts[0].item_a_key == "edr:EDR-OLD"
    assert conflicts[0].item_b_key == "edr:EDR-NEW"


def test_rank_9_10_material_is_never_inspected_by_this_module() -> None:
    """Chapter 5.6: "Conflicts between rank-9/10 items... are not
    conflicts". This module only ever reads `AuthorityResult`, which is
    exclusively rank 3/4 -- there is no code path here that can even see
    donor/model-hypothesis material, let alone flag it."""
    edr_a = _edr(slug="EDR-1", affected_requirement_slugs=["REQ-1"])
    edr_b = _edr(slug="EDR-2", affected_requirement_slugs=["REQ-1"])

    conflicts = detect_conflicts(
        _authority(edrs=[edr_a, edr_b]),
        requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
        edr_authority_rank=AUTHORITY_RANK_EDR,
    )

    assert all(
        conflict.item_a_authority_rank <= CONTRADICTION_AUTHORITY_RANK_CEILING
        and conflict.item_b_authority_rank <= CONTRADICTION_AUTHORITY_RANK_CEILING
        for conflict in conflicts
    )
