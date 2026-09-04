"""DDE-069 design provider contract and registry.

`DesignGateway` is provider-neutral by construction: the studio's semantics
depend on this protocol, never on one vendor's shape. A provider is
*certified* only when a real transport for it is registered; an
uncertified provider reports why and the gateway refuses.

The refusal matters more than the abstraction. FRONTEND_STUDIO_REV3
section 23 is explicit that DDE must never silently substitute a generic
code-generation prompt and call it `/design`. So there is no fallback path
here at all: `resolve` either returns a certified provider or raises. A
provider that cannot be reached produces a typed unavailable state in the
UI, which is a worse user experience and a correct one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from engine.core.errors import DdeError
from engine.studio.design.context import DesignEditContext


class ProviderState(StrEnum):
    CERTIFIED = "CERTIFIED"
    """A real transport is registered and authenticated."""

    NOT_CERTIFIED = "NOT_CERTIFIED"
    """The adapter exists but no certified transport is registered in this
    build. Distinct from unavailable: nothing is broken, the integration is
    simply not present."""

    AUTH_REQUIRED = "AUTH_REQUIRED"
    """Transport exists; the operator has not authenticated."""

    UNAVAILABLE = "UNAVAILABLE"
    """Transport exists and is authenticated but cannot be reached."""


@dataclass(frozen=True)
class DesignProviderStatus:
    """What the `/design` control renders itself from."""

    provider_id: str
    display_name: str
    state: ProviderState
    detail: str
    version: str | None = None
    capabilities: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.state is ProviderState.CERTIFIED


@dataclass(frozen=True)
class DesignRequest:
    """A design ask, already reduced to allowlisted context."""

    context: DesignEditContext
    direction_count: int
    instruction: str
    prior_artifact_hash: str | None = None


@dataclass(frozen=True)
class ProviderArtifact:
    """One normalized direction returned by a provider."""

    direction_label: str
    content: dict[str, object]
    provider_version: str


class DesignProvider(Protocol):
    """What any design provider must offer.

    Note what is absent: no method takes a free-form prompt string that
    reaches the model unmediated, and none returns code. A provider returns
    normalized design artifacts, which become code only through Try live's
    isolated candidate.
    """

    @property
    def provider_id(self) -> str: ...

    async def status(self) -> DesignProviderStatus: ...

    async def generate(
        self, request: DesignRequest
    ) -> tuple[ProviderArtifact, ...]: ...


class DesignProviderRegistry:
    """Holds the providers this build knows about."""

    def __init__(self, providers: tuple[DesignProvider, ...] = ()) -> None:
        self._providers = {item.provider_id: item for item in providers}

    def register(self, provider: DesignProvider) -> None:
        self._providers[provider.provider_id] = provider

    def known(self) -> tuple[DesignProvider, ...]:
        return tuple(self._providers.values())

    async def statuses(self) -> tuple[DesignProviderStatus, ...]:
        return tuple([await item.status() for item in self._providers.values()])

    async def resolve(self, provider_id: str) -> DesignProvider:
        """Return a certified provider, or refuse.

        There is deliberately no fallback. Substituting a different
        provider, or a generic code-generation prompt, would make
        `/design` a label rather than a capability.
        """
        provider = self._providers.get(provider_id)
        if provider is None:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "unknown design provider",
                retryable=False,
                details={
                    "provider_id": provider_id,
                    "known": sorted(self._providers),
                },
            )
        status = await provider.status()
        if not status.usable:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "design provider is not usable",
                retryable=status.state is ProviderState.UNAVAILABLE,
                details={
                    "provider_id": provider_id,
                    "state": status.state.value,
                    "detail": status.detail,
                },
            )
        return provider


class ClaudeDesignProvider:
    """Claude as the first certified design provider (section 23).

    The adapter and its contract exist; the *transport* does not. Rev 3
    prefers a certified direct Claude Design MCP/OAuth transport, and
    allows a certified Claude Code `/design` WorkerSession transport as an
    alternative. Neither is registered in this build, so this provider
    reports `NOT_CERTIFIED` and the gateway refuses.

    It deliberately does not fall back to `capability.claude_code_invoke`.
    That capability grants arbitrary development execution against a
    human's own seat and keeps its mandatory per-invocation approval for
    that reason (EDR-0001 Path A, EDR-0017); driving `/design` through it
    would be a generic code-generation prompt wearing a design label, which
    section 23 forbids by name.
    """

    provider_id = "claude-design"

    def __init__(self, transport: DesignProvider | None = None) -> None:
        self._transport = transport

    async def status(self) -> DesignProviderStatus:
        if self._transport is None:
            return DesignProviderStatus(
                provider_id=self.provider_id,
                display_name="Claude Design",
                state=ProviderState.NOT_CERTIFIED,
                detail=(
                    "No certified Claude Design transport is registered. Rev 3 "
                    "requires a structured transport (direct MCP/OAuth, or a "
                    "certified Claude Code /design WorkerSession); driving "
                    "this through capability.claude_code_invoke would be a "
                    "generic code-generation prompt labelled /design, which "
                    "FRONTEND_STUDIO_REV3 section 23 forbids."
                ),
            )
        return await self._transport.status()

    async def generate(self, request: DesignRequest) -> tuple[ProviderArtifact, ...]:
        if self._transport is None:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "no certified Claude Design transport is registered",
                retryable=False,
                details={"provider_id": self.provider_id},
            )
        return await self._transport.generate(request)


def default_registry() -> DesignProviderRegistry:
    """The providers this build ships. Claude is first and uncertified."""
    return DesignProviderRegistry((ClaudeDesignProvider(),))
