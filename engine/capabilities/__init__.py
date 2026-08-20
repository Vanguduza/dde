"""Capability registry, leases, proxy and credential broker (Chapter 9, 14).

DDE-016 built the registry: `CapabilityDescriptor` (9.1), the Chapter 9.3
side-effect taxonomy enforced as a real enum, and this module's lifecycle
(`ACTIVE -> DEPRECATED -> RETIRED`). DDE-017 adds `CapabilityLease` (9.2)
and its Chapter 7.2 T1 "brokered" enforcement guard (`lease_service.
CapabilityLeaseService.require_active`), wired into the real Stage 1 side
effects that need it (`engine.workers.scripted_adapter.ScriptedWorkerAdapter`,
`engine.workspaces.service.WorkspaceService.snapshot`). DDE-018 investigates
Chapter 7.2 T2 containment and finds none of Stage 1's real capabilities need
it, and closes a real ambient-environment-variable credential leak in
`engine.environments.backends.local_process.LocalProcessBackend`. DDE-019
adds the Credential Broker (14.3): `engine.capabilities.broker` -- see that
subpackage's module docstring for the full scope determination and design
choices, and `engine.capabilities.service`/`engine.capabilities.lease_service`'s
own module docstrings for what each of those two missions still defers."""
