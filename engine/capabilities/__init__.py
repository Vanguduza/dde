"""Capability registry, leases, proxy and credential broker (Chapter 9, 14).

DDE-016 built the registry: `CapabilityDescriptor` (9.1), the Chapter 9.3
side-effect taxonomy enforced as a real enum, and this module's lifecycle
(`ACTIVE -> DEPRECATED -> RETIRED`). DDE-017 adds `CapabilityLease` (9.2)
and its Chapter 7.2 T1 "brokered" enforcement guard (`lease_service.
CapabilityLeaseService.require_active`), wired into the real Stage 1 side
effects that need it (`engine.workers.scripted_adapter.ScriptedWorkerAdapter`,
`engine.workspaces.service.WorkspaceService.snapshot`). T2 containment (7.2)
and the Credential Broker (14.3) remain later, separately scoped missions --
see `engine.capabilities.service`/`engine.capabilities.lease_service`'s
module docstrings for the exact deferral lists."""
