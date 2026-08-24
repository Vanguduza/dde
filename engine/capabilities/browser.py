"""Chapter 9 browser capability contract — no vendor SDK.

Playwright (and any other browser backend) lives in `adapters/playwright/**`.
This module is the typed seam `engine.verification` and worker adapters
call so `engine.core` never imports a browser runtime (AGENTS.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BrowserProbeSpec:
    """One deterministic page probe.

    `url` is the page to open. `expect_text`, when set, must appear in the
    rendered `body.inner_text` for the probe to pass. Empty expect_text
    means "navigation succeeded."
    """

    url: str
    expect_text: str | None = None


@dataclass(frozen=True)
class BrowserProbeResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool


class BrowserCapability(Protocol):
    """T1-brokered browser execution. Callers must hold an active
    `capability.browser` lease before invoking `probe` — this protocol does
    not grant authority."""

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult: ...
