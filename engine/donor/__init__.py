"""Donor subsystem public API with cycle-safe lazy re-exports.

Network discovery/fan-out is DDE-066 (EDR-0015) via DonorDiscoveryService.
Human pin-by-URI and taint persistence stay on DonorLabService /
DonorTaintService. Imports are deliberately lazy so importing a leaf module such
as ``engine.donor.taint`` does not initialize discovery/execution/integration.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from engine.donor.discovery_service import (
        DonorDiscoveryService as DonorDiscoveryService,
    )
    from engine.donor.discovery_service import (
        SearchQuery as SearchQuery,
    )
    from engine.donor.service import (
        DonorLabService as DonorLabService,
    )
    from engine.donor.service import (
        IngestResult as IngestResult,
    )
    from engine.donor.taint import DonorTaintService as DonorTaintService

_EXPORTS = {
    "DonorDiscoveryService": (
        "engine.donor.discovery_service",
        "DonorDiscoveryService",
    ),
    "SearchQuery": ("engine.donor.discovery_service", "SearchQuery"),
    "DonorLabService": ("engine.donor.service", "DonorLabService"),
    "IngestResult": ("engine.donor.service", "IngestResult"),
    "DonorTaintService": ("engine.donor.taint", "DonorTaintService"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> object:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    value = cast(object, getattr(import_module(module_name), attr_name))
    globals()[name] = value
    return value
