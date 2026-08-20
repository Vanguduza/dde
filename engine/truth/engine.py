"""Project Truth constitution, requirements and EDR writes."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from engine.contracts.edr import Edr
from engine.contracts.product_constitution_version import ProductConstitutionVersion
from engine.contracts.requirement import Requirement
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7

REQUIRED_CONSTITUTION_HEADINGS = (
    "## Purpose",
    "## Target users",
    "## Non-negotiable constraints",
    "## Core workflows",
    "## UX principles",
    "## Security principles",
    "## Architecture principles",
    "## Explicit exclusions",
    "## Governance rules",
)


@dataclass
class TruthStore:
    constitutions: dict[UUID, ProductConstitutionVersion] = field(default_factory=dict)
    requirements: dict[UUID, Requirement] = field(default_factory=dict)
    edrs: dict[UUID, Edr] = field(default_factory=dict)

    def requirements_for_project(self, project_id: UUID) -> list[Requirement]:
        return [
            item for item in self.requirements.values() if item.project_id == project_id
        ]

    def edrs_for_project(self, project_id: UUID) -> list[Edr]:
        return [item for item in self.edrs.values() if item.project_id == project_id]

    def active_constitution(
        self, project_id: UUID
    ) -> ProductConstitutionVersion | None:
        active = [
            item
            for item in self.constitutions.values()
            if item.project_id == project_id and item.status == "active"
        ]
        if not active:
            return None
        return max(active, key=lambda item: item.version)


class TruthEngine:
    """In-memory test double for Project Truth writes.

    The production writer is `engine.truth.service.TruthService`, which persists
    to PostgreSQL inside one transaction per Chapter 3.5. This class never
    touches a database and exists only so other in-memory modules (missions,
    planning, governance) can be exercised in unit tests without one.
    """

    def __init__(self, store: TruthStore, clock: Clock | None = None) -> None:
        self._store = store
        self._clock = clock or SystemClock()

    def publish_constitution(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        body_markdown: str,
    ) -> ProductConstitutionVersion:
        missing = [
            heading
            for heading in REQUIRED_CONSTITUTION_HEADINGS
            if heading not in body_markdown
        ]
        if missing:
            raise DdeError(
                "POLICY_DENIED",
                "Product Constitution is missing required Chapter 2.4 headings",
                details={"missing": missing},
            )
        current = self._store.active_constitution(project_id)
        now = self._clock.now()
        if current is not None:
            self._store.constitutions[current.version_id] = current.model_copy(
                update={"status": "superseded", "updated_at": now}
            )
        version = 1 if current is None else current.version + 1
        record = ProductConstitutionVersion(
            version_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            version=version,
            status="active",
            body_markdown=body_markdown,
            content_hash=sha256_hex(body_markdown),
            supersedes_id=None if current is None else current.version_id,
            created_at=now,
            updated_at=now,
        )
        self._store.constitutions[record.version_id] = record
        return record

    def draft_requirement(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        statement: str,
        constraints: list[str],
        acceptance_conditions: list[str],
        supersedes_id: UUID | None = None,
    ) -> Requirement:
        self._assert_slug_free(project_id, slug)
        if not statement.strip():
            raise DdeError("POLICY_DENIED", "Requirement statement must be testable")
        if not acceptance_conditions:
            raise DdeError(
                "POLICY_DENIED",
                "Requirement must declare acceptance conditions",
            )
        now = self._clock.now()
        record = Requirement(
            requirement_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            slug=slug,
            statement=statement,
            constraints=constraints,
            acceptance_conditions=acceptance_conditions,
            status="draft",
            supersedes_id=supersedes_id,
            created_at=now,
            updated_at=now,
        )
        self._store.requirements[record.requirement_id] = record
        return record

    def approve_requirement(self, requirement_id: UUID) -> Requirement:
        record = self._require_requirement(requirement_id)
        if record.status not in {"draft", "approved"}:
            raise DdeError(
                "VERSION_CONFLICT",
                "Only draft requirements can be approved",
                details={"status": record.status},
            )
        if record.status == "approved":
            return record
        updated = record.model_copy(
            update={"status": "approved", "updated_at": self._clock.now()}
        )
        if updated.supersedes_id is not None:
            prior = self._require_requirement(updated.supersedes_id)
            self._store.requirements[prior.requirement_id] = prior.model_copy(
                update={"status": "superseded", "updated_at": updated.updated_at}
            )
        self._store.requirements[requirement_id] = updated
        return updated

    def retire_requirement(self, requirement_id: UUID) -> Requirement:
        record = self._require_requirement(requirement_id)
        if record.status == "draft":
            raise DdeError(
                "VERSION_CONFLICT",
                "Draft requirements are withdrawn by non-approval, not retired",
            )
        updated = record.model_copy(
            update={"status": "retired", "updated_at": self._clock.now()}
        )
        self._store.requirements[requirement_id] = updated
        return updated

    def propose_edr(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        context: str,
        alternatives: list[str],
        decision: str,
        rationale: str,
        consequences: list[str],
        affected_requirement_slugs: list[str],
        supersedes_id: UUID | None = None,
    ) -> Edr:
        self._assert_edr_slug_free(project_id, slug)
        if not alternatives:
            raise DdeError("POLICY_DENIED", "EDR must record alternatives")
        now = self._clock.now()
        record = Edr(
            edr_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            slug=slug,
            context=context,
            alternatives=alternatives,
            decision=decision,
            rationale=rationale,
            consequences=consequences,
            affected_requirement_slugs=affected_requirement_slugs,
            status="proposed",
            supersedes_id=supersedes_id,
            created_at=now,
            updated_at=now,
        )
        self._store.edrs[record.edr_id] = record
        return record

    def accept_edr(self, edr_id: UUID, decided_by_principal: UUID) -> Edr:
        record = self._require_edr(edr_id)
        if record.status == "accepted":
            return record
        if record.status != "proposed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Only proposed EDRs can be accepted",
                details={"status": record.status},
            )
        now = self._clock.now()
        if record.supersedes_id is not None:
            prior = self._require_edr(record.supersedes_id)
            if prior.status != "accepted":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "An EDR may only supersede an accepted EDR",
                )
            self._rewrite_edr_status(prior, "superseded", now)
        accepted = record.model_copy(
            update={
                "status": "accepted",
                "decided_by_principal": decided_by_principal,
                "decided_at": now,
                "updated_at": now,
            }
        )
        self._store.edrs[edr_id] = accepted
        return accepted

    def reject_edr(self, edr_id: UUID, decided_by_principal: UUID) -> Edr:
        record = self._require_edr(edr_id)
        if record.status != "proposed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Only proposed EDRs can be rejected",
                details={"status": record.status},
            )
        now = self._clock.now()
        updated = record.model_copy(
            update={
                "status": "rejected",
                "decided_by_principal": decided_by_principal,
                "decided_at": now,
                "updated_at": now,
            }
        )
        self._store.edrs[edr_id] = updated
        return updated

    def rewrite_accepted_edr(self, edr_id: UUID, decision: str) -> Edr:
        """Forbidden path — accepted EDRs are immutable (Chapter 2.4)."""
        record = self._require_edr(edr_id)
        if record.status in {"accepted", "superseded"}:
            raise DdeError(
                "POLICY_DENIED",
                "Accepted EDRs are superseded, never rewritten",
                details={"edr_id": str(edr_id)},
            )
        updated = record.model_copy(
            update={"decision": decision, "updated_at": self._clock.now()}
        )
        self._store.edrs[edr_id] = updated
        return updated

    def approved_requirement_slugs(self, project_id: UUID) -> list[str]:
        return [
            item.slug
            for item in self._store.requirements_for_project(project_id)
            if item.status == "approved"
        ]

    def _rewrite_edr_status(self, record: Edr, status: str, now: object) -> None:
        self._store.edrs[record.edr_id] = record.model_copy(
            update={"status": status, "updated_at": now}
        )

    def _require_requirement(self, requirement_id: UUID) -> Requirement:
        record = self._store.requirements.get(requirement_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown requirement")
        return record

    def _require_edr(self, edr_id: UUID) -> Edr:
        record = self._store.edrs.get(edr_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown EDR")
        return record

    def _assert_slug_free(self, project_id: UUID, slug: str) -> None:
        for item in self._store.requirements_for_project(project_id):
            if item.slug == slug:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Requirement slug is immutable and already used",
                    details={"slug": slug},
                )

    def _assert_edr_slug_free(self, project_id: UUID, slug: str) -> None:
        for item in self._store.edrs_for_project(project_id):
            if item.slug == slug:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "EDR slug is immutable and already used",
                    details={"slug": slug},
                )
