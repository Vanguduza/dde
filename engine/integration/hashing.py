"""`DiffGateReport.request_hash` -- canonical-JSON-then-SHA-256, mirroring
`engine.recovery.hashing.effect_request_hash`. Identifies one evaluation of
one proposal's actual `(base, proposed)` diff for `CommandLedger`.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def gate_request_hash(
    *,
    proposal_id: UUID,
    base_revision: str,
    proposed_revision: str,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "proposal_id": str(proposal_id),
                "base_revision": base_revision,
                "proposed_revision": proposed_revision,
            }
        )
    )
