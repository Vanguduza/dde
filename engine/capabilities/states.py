"""`CapabilityDescriptor.lifecycle_status`'s real state machine -- see
`engine.capabilities.taxonomy`'s module docstring for why these three values
(not a chapter-literal enum) were chosen. A descriptor is born `ACTIVE`;
registering a new version of the same `capability_id` moves the previous
`ACTIVE` row to `DEPRECATED` (Chapter 3.10: "a material change creates a new
version ... it never overwrites" -- superseding, not editing); either state
can be explicitly `retire()`-d. `RETIRED` is terminal: once withdrawn from
the catalog, a descriptor version never returns to service."""

from __future__ import annotations

from typing import Final

LIFECYCLE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "ACTIVE": frozenset({"DEPRECATED", "RETIRED"}),
    "DEPRECATED": frozenset({"RETIRED"}),
    "RETIRED": frozenset(),
}
