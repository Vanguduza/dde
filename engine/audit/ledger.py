"""Hash-chained audit ledger (Chapter 3.7).

`AuditService` (`engine.audit.service`) is the production writer, backed by
PostgreSQL. `AuditLedger` and `AuditStore` below are an in-memory test double
only — they never touch a database and must not be used as a production
store. `audit_entry_hash` is the shared, pure hash function both
implementations use so the chain is computed identically either way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from engine.contracts.audit_event import AuditEvent
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7


def audit_entry_hash(
    *,
    prev_hash: str | None,
    audit_event_id: UUID,
    event_type: str,
    payload: dict[str, object],
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "prev_hash": prev_hash,
                "audit_event_id": str(audit_event_id),
                "event_type": event_type,
                "payload": payload,
            }
        )
    )


@dataclass
class AuditStore:
    entries: dict[UUID, AuditEvent] = field(default_factory=dict)

    def for_tenant(self, tenant_id: UUID) -> list[AuditEvent]:
        rows = [item for item in self.entries.values() if item.tenant_id == tenant_id]
        return sorted(rows, key=lambda item: item.sequence)


class AuditLedger:
    def __init__(self, store: AuditStore, clock: Clock | None = None) -> None:
        self._store = store
        self._clock = clock or SystemClock()

    def append(
        self,
        *,
        tenant_id: UUID,
        event_type: str,
        payload: dict[str, object],
        project_id: UUID | None = None,
    ) -> AuditEvent:
        chain = self._store.for_tenant(tenant_id)
        prev = chain[-1] if chain else None
        now = self._clock.now()
        audit_event_id = uuid7()
        prev_hash = None if prev is None else prev.entry_hash
        record = AuditEvent(
            audit_event_id=audit_event_id,
            tenant_id=tenant_id,
            project_id=project_id,
            event_type=event_type,
            sequence=1 if prev is None else prev.sequence + 1,
            prev_hash=prev_hash,
            entry_hash=audit_entry_hash(
                prev_hash=prev_hash,
                audit_event_id=audit_event_id,
                event_type=event_type,
                payload=payload,
            ),
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        self._store.entries[record.audit_event_id] = record
        return record

    def verify_chain(self, tenant_id: UUID) -> None:
        prev_hash: str | None = None
        for entry in self._store.for_tenant(tenant_id):
            expected = audit_entry_hash(
                prev_hash=prev_hash,
                audit_event_id=entry.audit_event_id,
                event_type=entry.event_type,
                payload=entry.payload,
            )
            if entry.prev_hash != prev_hash or entry.entry_hash != expected:
                raise DdeError(
                    "POLICY_DENIED",
                    "Audit ledger hash chain is broken",
                    details={"audit_event_id": str(entry.audit_event_id)},
                )
            prev_hash = entry.entry_hash
