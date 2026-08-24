"""Alibaba OpenSandbox adapter configuration (EDR-0011 Option B donor).

Vendor SDK (`opensandbox`) may be imported only from this package
(`adapters/opensandbox/**`), never from `engine/core/**` (AGENTS.md).

Preferred credential UX: Studio Settings paste → broker capture.
Env `DDE_OPENSANDBOX_*` remains the headless fallback.
"""

from adapters.opensandbox.settings import (
    OpenSandboxSettings,
    load_opensandbox_settings,
    require_opensandbox_enabled,
)

__all__ = [
    "OpenSandboxSettings",
    "load_opensandbox_settings",
    "require_opensandbox_enabled",
]
