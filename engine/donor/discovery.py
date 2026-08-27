"""Allowlist + prepare-before-fetch primitive (DDE-066 / EDR-0015).

`search_uri` is the synchronous ordering seam: admit, journal prepare,
then fetch. Production journaling is `DonorDiscoveryService.search`
(`engine.donor.discovery_service`), which calls `ExternalEffectService.prepare`
before the injected transport. This module does not import httpx.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from engine.donor.allowlist import assert_uri_admitted
from engine.donor.grouping import (
    Classifier,
    DiscoveryHit,
    FeatureCategory,
    GroupedDonorResults,
    group_discovery_hits,
)


@dataclass
class OrderedJournal:
    """Test/production seam: record prepare-before-fetch ordering."""

    events: list[str] = field(default_factory=list)

    def prepare(self, uri: str, idempotency_key: str) -> None:
        del idempotency_key
        self.events.append(f"prepare:{uri}")


PrepareFn = Callable[[str, str], None]
FetchFn = Callable[[str], str]


def search_uri(
    *,
    uri: str,
    idempotency_key: str,
    prepare: PrepareFn,
    fetch: FetchFn,
) -> str:
    """One outbound query: allowlist, journal, then fetch."""
    assert_uri_admitted(uri)
    prepare(uri, idempotency_key)
    return fetch(uri)


def assemble_inventory(
    *,
    prd_id: str,
    features: tuple[FeatureCategory, ...],
    hits: tuple[DiscoveryHit, ...],
    classifier: Classifier | None = None,
) -> GroupedDonorResults:
    return group_discovery_hits(
        prd_id=prd_id,
        features=features,
        hits=hits,
        classifier=classifier,
    )
