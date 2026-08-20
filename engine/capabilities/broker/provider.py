"""Chapter 14.3's `CredentialProvider` contract -- "Providers sit behind a
`CredentialProvider` contract so no core logic couples to one secret
manager." -- plus the one real implementation this mission builds against.

**`LocalSecretProvider`.** Chapter 14.3's preference order ends with "static
secret behind the broker"; this is that tier, made real rather than
fabricated: `secrets.token_urlsafe` (stdlib, cryptographically secure,
Chapter 9.6 -- no new dependency justified when the standard library already
solves this) mints a genuine, high-entropy, short-lived bearer value on
every call. There is no separate external system for this provider to hold
state in, so `revoke()` is a documented no-op at the provider layer --
`engine.capabilities.broker.service.CredentialBrokerService` is what
"always invalidates locally" (14.3) by transitioning the owning
`CredentialHandle` row, which is the real, durable, checked invalidation
this mission proves. A future real provider (e.g. a cloud IAM API) would
give `revoke()` an actual network call to make; `LocalSecretProvider`
correctly has none.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CredentialScope:
    """The Chapter 14.3 binding fields a provider may use to shape what it
    issues. `LocalSecretProvider` ignores all of them -- a bare random
    token needs no scope-specific shaping -- but a real provider (e.g. one
    minting a scoped cloud IAM token) would key its own request on these."""

    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    lease_id: UUID
    capability_id: str
    resource_scope: dict[str, object]


@dataclass(frozen=True)
class ProviderIssuedCredential:
    """`secret_value` is handed to the broker's caller exactly once and is
    never passed back into this contract again. `provider_ref` is an opaque,
    non-secret, provider-side identifier `revoke()` can use to invalidate
    the specific issued credential at the provider -- `None` where a
    provider (like `LocalSecretProvider`) holds no separate provider-side
    state to reference."""

    secret_value: str
    provider_ref: str | None


class CredentialProvider(Protocol):
    """Chapter 14.3's provider contract. `provider_id` is a stable, non-secret
    identifier persisted on every `CredentialHandle` this provider issues."""

    provider_id: str

    def issue(self, scope: CredentialScope) -> ProviderIssuedCredential:
        """Mint a new, real short-lived secret value. Never returns the
        same value twice."""

    def revoke(self, provider_ref: str | None) -> None:
        """Invalidate at the provider "where semantics permit" (14.3) --
        a no-op is a valid, honest implementation when a provider has no
        separate revocable state of its own."""


class LocalSecretProvider:
    """This mission's one real, working provider -- see module docstring."""

    provider_id = "local_secret"

    def issue(self, scope: CredentialScope) -> ProviderIssuedCredential:
        del scope  # unused: a bare local secret needs no scope shaping
        return ProviderIssuedCredential(
            secret_value=secrets.token_urlsafe(32), provider_ref=None
        )

    def revoke(self, provider_ref: str | None) -> None:
        del provider_ref  # no external state to quarantine -- see docstring
        return None
