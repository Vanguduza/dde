"""Chapter 3.10 immutable-definition hashing for ContextPackage.

`assembly_hash` is computed over the package's definition — what task it
is for and what evidence it actually assembled — and excludes every
lifecycle/identity column (`package_id`, `version`, `status`,
`created_at`, `updated_at`): recompiling identical inputs must produce an
identical hash even though `package_id`/`version` are always fresh.
"""

from __future__ import annotations

from uuid import UUID

from engine.context.model import FusedItem
from engine.core.hashing import canonical_json, sha256_hex


def assembly_hash(
    *,
    task_id: UUID,
    tenant_id: UUID,
    project_id: UUID,
    mission_id: UUID,
    index_version: str,
    index_lag_commits: int,
    coverage: dict[str, object],
    included_items: tuple[FusedItem, ...],
) -> str:
    item_entries = sorted(
        (
            {
                "retriever": fused.item.retriever,
                "key": fused.item.key,
                "categories": sorted(fused.item.categories),
                "authority_rank": fused.item.authority_rank,
                "content_hash": sha256_hex(fused.item.content),
            }
            for fused in included_items
        ),
        key=lambda entry: (str(entry["retriever"]), str(entry["key"])),
    )
    payload = {
        "task_id": str(task_id),
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "mission_id": str(mission_id),
        "index_version": index_version,
        "index_lag_commits": index_lag_commits,
        "coverage": coverage,
        "items": item_entries,
    }
    return sha256_hex(canonical_json(payload))
