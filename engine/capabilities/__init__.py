"""Capability registry, leases, proxy and credential broker (Chapter 9, 14).

DDE-016 builds the registry only: `CapabilityDescriptor` (9.1), the Chapter
9.3 side-effect taxonomy enforced as a real enum, and this module's
lifecycle (`ACTIVE -> DEPRECATED -> RETIRED`). Leases (9.2), the T1 gateway/
T2 containment (7.2), and the Credential Broker (14.3) are later, separately
scoped missions -- see `engine.capabilities.service`'s module docstring for
the exact deferral list."""
