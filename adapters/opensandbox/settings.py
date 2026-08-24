"""`DDE_OPENSANDBOX_*` settings — env fallback for Alibaba OpenSandbox.

Preferred operator UX is DDE Studio Settings paste → Credential Broker
capture (`engine.capabilities.broker.capture.StaticSecretCaptureService`):
the raw API key is hashed instantly and stored only behind the broker
seam. Env vars (`DDE_OPENSANDBOX_API_KEY` / `OPEN_SANDBOX_API_KEY`) remain
the headless fallback. This module never logs `api_key`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from engine.core.errors import DdeError

OPENSANDBOX_ISOLATION_TIERS = frozenset({"runc", "gvisor", "kata", "firecracker"})


@dataclass(frozen=True)
class OpenSandboxSettings:
    """Operator-facing OpenSandbox connection and default create policy."""

    enabled: bool
    domain: str
    api_key: str | None
    protocol: str
    default_image: str
    use_server_proxy: bool
    request_timeout_seconds: float
    egress_default_action: str
    egress_allow: tuple[str, ...]
    credential_proxy_enabled: bool
    isolation_tier: str | None

    def connection_kwargs(self) -> dict[str, object]:
        """Keyword args suitable for `opensandbox.config.ConnectionConfig`."""
        if not self.domain.strip():
            raise DdeError(
                "POLICY_DENIED",
                "DDE_OPENSANDBOX_DOMAIN must be set when OpenSandbox is used",
            )
        kwargs: dict[str, object] = {
            "domain": self.domain.strip(),
            "protocol": self.protocol,
            "use_server_proxy": self.use_server_proxy,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return kwargs


def _truthy(raw: str | None, *, default: bool = False) -> bool:
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_allowlist(raw: str | None) -> tuple[str, ...]:
    if raw is None or raw.strip() == "":
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def load_opensandbox_settings(
    environ: dict[str, str] | None = None,
) -> OpenSandboxSettings:
    """Load settings from `DDE_OPENSANDBOX_*`, with SDK-native aliases as fallback."""
    env = environ if environ is not None else dict(os.environ)
    domain = env.get("DDE_OPENSANDBOX_DOMAIN") or env.get("OPEN_SANDBOX_DOMAIN") or ""
    api_key = env.get("DDE_OPENSANDBOX_API_KEY") or env.get("OPEN_SANDBOX_API_KEY")
    if api_key is not None and api_key.strip() == "":
        api_key = None
    tier_raw = (env.get("DDE_OPENSANDBOX_ISOLATION_TIER") or "").strip().lower()
    isolation_tier = tier_raw or None
    if isolation_tier is not None and isolation_tier not in OPENSANDBOX_ISOLATION_TIERS:
        raise DdeError(
            "POLICY_DENIED",
            "DDE_OPENSANDBOX_ISOLATION_TIER must be one of "
            f"{sorted(OPENSANDBOX_ISOLATION_TIERS)}",
            details={"value": tier_raw},
        )
    protocol = (env.get("DDE_OPENSANDBOX_PROTOCOL") or "http").strip().lower()
    if protocol not in {"http", "https"}:
        raise DdeError(
            "POLICY_DENIED",
            "DDE_OPENSANDBOX_PROTOCOL must be http or https",
            details={"value": protocol},
        )
    timeout_raw = env.get("DDE_OPENSANDBOX_REQUEST_TIMEOUT_SECONDS") or "30"
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise DdeError(
            "POLICY_DENIED",
            "DDE_OPENSANDBOX_REQUEST_TIMEOUT_SECONDS must be a number",
            details={"value": timeout_raw},
        ) from exc
    if timeout <= 0:
        raise DdeError(
            "POLICY_DENIED",
            "DDE_OPENSANDBOX_REQUEST_TIMEOUT_SECONDS must be positive",
            details={"value": timeout},
        )
    return OpenSandboxSettings(
        enabled=_truthy(env.get("DDE_OPENSANDBOX_ENABLED"), default=False),
        domain=domain,
        api_key=api_key,
        protocol=protocol,
        default_image=(env.get("DDE_OPENSANDBOX_DEFAULT_IMAGE") or "ubuntu").strip(),
        use_server_proxy=_truthy(
            env.get("DDE_OPENSANDBOX_USE_SERVER_PROXY"), default=False
        ),
        request_timeout_seconds=timeout,
        egress_default_action=(
            env.get("DDE_OPENSANDBOX_EGRESS_DEFAULT_ACTION") or "deny"
        ).strip(),
        egress_allow=_parse_allowlist(env.get("DDE_OPENSANDBOX_EGRESS_ALLOW")),
        credential_proxy_enabled=_truthy(
            env.get("DDE_OPENSANDBOX_CREDENTIAL_PROXY"), default=True
        ),
        isolation_tier=isolation_tier,
    )


@lru_cache
def cached_opensandbox_settings() -> OpenSandboxSettings:
    return load_opensandbox_settings()


def require_opensandbox_enabled(
    settings: OpenSandboxSettings | None = None,
) -> OpenSandboxSettings:
    """Fail closed unless the operator explicitly enabled OpenSandbox."""
    active = settings if settings is not None else load_opensandbox_settings()
    if not active.enabled:
        raise DdeError(
            "POLICY_DENIED",
            "OpenSandbox backend is disabled; set DDE_OPENSANDBOX_ENABLED=true "
            "and DDE_OPENSANDBOX_DOMAIN after EDR-0011 substrate wiring admits it",
            details={"enabled": False, "deferred": "EDR-0011-substrate"},
        )
    if not active.domain.strip():
        raise DdeError(
            "POLICY_DENIED",
            "OpenSandbox is enabled but DDE_OPENSANDBOX_DOMAIN is empty",
        )
    return active
